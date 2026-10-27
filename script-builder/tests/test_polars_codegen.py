import importlib.util
from datetime import datetime
import pytest

from script_builder.codegen import build_artifact
from script_builder.codegen.polars import PolarsEmitter
from script_builder.codegen.pandas import PandasEmitter, _helper_sources
from script_builder.codegen.registry import EMITTERS
from script_builder.ir.catalog import POLARS_OPERATIONS, OPERATIONS, compatibility_matrix
from script_builder.operations.polars import PolarsOperations


def node(operation, parameters, inputs=1, name="op"):
	return {
		"id": name,
		"operation": {"name": operation},
		"parameters": parameters,
		"input_ports": [{"id": f"{name}_{index}", "ordinal": index} for index in range(inputs)],
		"output_ports": [{"id": f"{name}_out", "ordinal": 0}],
	}


def pipeline(operation, parameters, inputs=1):
	return {"nodes": [node(operation, parameters, inputs)], "edges": []}


def compile_module(tmp_path, dag):
	pytest.importorskip("polars")
	directory = tmp_path / f"artifact-{len(list(tmp_path.iterdir()))}"
	build_artifact(
		dag, directory, pipeline_id="polars-test", pipeline_version="1",
		framework="polars",
	)
	spec = importlib.util.spec_from_file_location("polars_pipeline", directory / "main.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	source = (directory / "main.py").read_text()
	assert "import pandas" not in source
	assert "script_builder" not in source
	return module


def test_only_pandas_and_polars_are_registered():
	assert set(EMITTERS) == {"pandas", "polars"}
	assert POLARS_OPERATIONS == set(OPERATIONS)
	assert set(PandasEmitter.implementations) | {"fx"} == set(OPERATIONS)
	assert set(PolarsEmitter.implementations) | {"fx"} == set(OPERATIONS)
	assert all(row == {"pandas": True, "polars": True} for row in compatibility_matrix().values())
	assert all(
		hasattr(PolarsOperations(), "round_column" if name == "round" else name)
		for name in OPERATIONS if name != "fx"
	)


def test_all_polars_operation_helpers_lower_to_standalone_python():
	methods = set(PolarsEmitter.implementations.values())
	for method in methods:
		source = "\n\n".join(_helper_sources({method}))
		compile(
			"import json\nimport re\nfrom datetime import date, datetime\nimport polars as pl\n\n" + source,
			f"<{method[0].__name__}.{method[1]}>",
			"exec",
		)


def test_all_pandas_operation_helpers_lower_to_standalone_python():
	methods = set(PandasEmitter.implementations.values())
	for method in methods:
		source = "\n\n".join(_helper_sources({method}))
		compile(
			"import json\nimport operator\nimport re\nfrom datetime import time\n"
			"import numpy as np\nimport pandas as pd\n"
			"from pandas.api.types import is_bool_dtype\n\n" + source,
			f"<{method[0].__name__}.{method[1]}>",
			"exec",
		)


@pytest.mark.parametrize(
	"operation,parameters,source,expected_column,expected",
	[
		("uppercase", {"column": "text"}, {"text": ["hola", "adios"]}, "text", ["HOLA", "ADIOS"]),
		("arithmetic", {"column_a": "left", "operator": "+", "column_b_or_value": "right"},
		 {"left": [1, 2], "right": [4, 5]}, "left", [5.0, 7.0]),
		("date_add", {"column": "date", "unit": "months", "amount": 1},
		 {"date": ["2024-01-31", "2024-02-29"]}, "date",
		 [datetime(2024, 2, 29), datetime(2024, 3, 29)]),
		("logical", {"operation": "and", "column": "value", "sentencia1": "value > 0",
			"sentencia2": "value < 3"}, {"value": [0, 1, 2, 3]}, "value", [False, True, True, False]),
		("split", {"column": "text", "delimiter": "-", "index": 1},
		 {"text": ["a-b", "c-d"]}, "text_processed", ["b", "d"]),
	],
)
def test_generated_polars_operations(tmp_path, operation, parameters, source, expected_column, expected):
	import polars as pl

	module = compile_module(tmp_path, pipeline(operation, parameters))
	result = module.run({"op_0": pl.DataFrame(source)})["op"]
	assert result[expected_column].to_list() == expected


def test_polars_aggregate_pivot_join_and_io(tmp_path):
	import polars as pl

	data = pl.DataFrame({"group": ["a", "a", "b"], "value": [1, 3, 5]})
	aggregate = compile_module(
		tmp_path,
		pipeline("aggregate", {"group_by": ["group"], "aggregations": {"value": "sum"}}),
	)
	assert aggregate.run({"op_0": data})["op"].to_dicts() == [
		{"group": "a", "value": 4}, {"group": "b", "value": 5},
	]

	pivot = compile_module(
		tmp_path,
		pipeline("pivot", {
			"pivot_type": "columns_to_rows", "index_cols": ["group"],
			"target_col": "field", "values_col": "amount",
		}),
	)
	assert pivot.run({"op_0": data})["op"].height == 3

	left = pl.DataFrame({"left_id": [1], "value": ["left"]})
	right = pl.DataFrame({"right_id": [1], "value": ["right"]})
	join = compile_module(
		tmp_path,
		pipeline("join", {"left_on": "left_id", "right_on": "right_id"}, inputs=2),
	)
	assert join.run({"op_0": left, "op_1": right})["op"].to_dicts() == [{
		"left_id": 1, "value_x": "left", "right_id": 1, "value_y": "right",
	}]

	path = tmp_path / "data.csv"
	writer = compile_module(
		tmp_path, pipeline("output", {"destination_type": "csv", "output_path": str(path)}),
	)
	writer.run({"op_0": data})
	assert pl.read_csv(path).to_dicts() == data.to_dicts()


def test_polars_conversion_logical_and_date_helpers(tmp_path):
	import polars as pl

	conversion = compile_module(
		tmp_path,
		pipeline("make_date", {
			"column_day": "day", "column_month": "month", "column_year": "year",
			"new_column_name": "made_date",
		}),
	)
	frame = pl.DataFrame({"day": [31], "month": [2], "year": [2024]})
	assert conversion.run({"op_0": frame})["op"]["made_date"].to_list() == [
		datetime(2024, 2, 29),
	]

	logical = compile_module(
		tmp_path,
		pipeline("conditional_map", {
			"column": "value", "condition_func": {"operator": ">", "value": 1},
			"true_value": "yes", "false_value": "no",
		}),
	)
	result = logical.run({"op_0": pl.DataFrame({"value": [1, 2]})})["op"]
	assert result["value"].to_list() == ["no", "yes"]

	date_add = compile_module(
		tmp_path,
		pipeline("date_add", {"column": "date", "unit": "months", "amount": 1}),
	)
	dates = date_add.run({"op_0": pl.DataFrame({"date": ["2024-01-31"]})})["op"]
	assert dates["date"].to_list() == [datetime(2024, 2, 29)]


def test_every_catalog_operation_executes_in_generated_polars_script(tmp_path):
	import polars as pl

	source_path = tmp_path / "source.csv"
	data = pl.DataFrame({
		"text": ["a-b", " c ", "ABC"],
		"other_text": ["x", "y", "z"],
		"value": [1, 2, 3],
		"other": [4, 5, 6],
		"column_a": [1, 2, 3],
		"column_b": [2, 4, 6],
		"group": ["a", "a", "b"],
		"amount": [1, 2, 3],
		"date": ["2024-01-31", "2024-02-29", "2024-03-15"],
		"end_date": ["2024-02-01", "2024-03-29", "2024-04-15"],
		"column_day": [1, 2, 3],
		"column_month": [1, 2, 3],
		"column_year": [2024, 2024, 2024],
		"column_hour": [12, 13, 14],
		"column_minute": [30, 31, 32],
		"column_second": [0, 0, 0],
		"time": ["12:30:00", "13:31:00", "14:32:00"],
	})
	data.write_csv(source_path)
	parameters = {
		"read_csv": {"filepath": str(source_path)},
		"write_csv": {"filepath": str(tmp_path / "write.csv")},
		"input": {"source_type": "csv", "filepath_or_connection": str(source_path)},
		"output": {"destination_type": "csv", "output_path": str(tmp_path / "output.csv")},
		"join": {"left_on": "group", "right_on": "group"},
		"union": {},
		"aggregate": {"group_by": ["group"], "aggregations": {"amount": "sum"}},
		"pivot": {
			"pivot_type": "columns_to_rows", "index_cols": ["group"],
			"target_col": "field", "values_col": "measure",
		},
		"date_parser": {"column": "date", "date_format": "%Y-%m-%d"},
		"date_parse": {"column": "date", "date_format": "%Y-%m-%d"},
		"date_trunc": {"column": "date", "part": "month"},
		"date_add": {"column": "date", "unit": "months", "amount": 1},
		"date_sub": {"column": "date", "unit": "days", "amount": 1},
		"date_diff": {"start_column": "date", "end_column": "end_date", "unit": "days"},
		"date_name": {"column": "date", "part": "month"},
		"extract_date_part": {"column": "date", "part": "year"},
		"coalesce": {"column": "value", "default_value": 0},
		"conditional_map": {
			"column": "value", "condition_func": {"operator": ">", "value": 1},
			"true_value": "yes", "false_value": "no",
		},
		"logical": {
			"operation": "and", "column": "value",
			"sentencia1": "value > 0", "sentencia2": "value < 3",
		},
		"fx": {"column_name": "new", "expression": 'col("value") + 1'},
		"make_date": {
			"column_day": "column_day", "column_month": "column_month",
			"column_year": "column_year", "new_column_name": "made_date",
		},
		"make_time": {
			"column_hour": "column_hour", "column_minute": "column_minute",
			"column_second": "column_second", "new_column_name": "made_time",
		},
		"make_date_time": {
			"column_date": "date", "column_hour": "time", "new_column_name": "made_datetime",
		},
		"arithmetic": {
			"column_a": "column_a", "operator": "+", "column_b_or_value": "column_b",
		},
		"max": {"column_a": "column_a", "column_b": "column_b", "new_column_name": "maximum"},
		"min": {"column_a": "column_a", "column_b": "column_b", "new_column_name": "minimum"},
		"substring": {"column": "text", "start": 0, "length": 2},
		"replace": {"column": "text", "old_text": "a", "new_text": "b"},
		"split": {"column": "text", "delimiter": "-", "index": 0},
		"concat_column": {"columns": ["text", "other_text"]},
		"concat_text": {"column_name": "text", "value": "!"},
		"contains": {"column": "text", "search_text": "a"},
		"starts_with": {"column": "text", "search_text": "a"},
		"ends_with": {"column": "text", "search_text": "a"},
		"transform_left": {"column": "text", "limit": 2},
		"transform_right": {"column": "text", "limit": 2},
		"filter": {"column": "value", "operator": ">", "value": 1},
		"limit": {"limit": 2},
		"sort": {"column": "value"},
		"sample": {"sample_type": "head", "fraction_or_count": 2},
		"drop_column": {"column": "other"},
		"rename_column": {"column": "other", "new_name": "renamed"},
		"change_data_type": {"column": "value", "target_type": "str"},
		"add_column": {"column_name": "added", "value": 1},
		"absolute": {"column": "value"},
		"clean_float": {"column": "value"},
		"ceiling": {"column": "value"},
		"floor": {"column": "value"},
		"power": {"column": "value", "value": 2},
		"round": {"column": "value", "decimals": 0},
		"date": {"column": "date"},
		"datetime": {"column": "date"},
		"float": {"column": "value"},
		"int": {"column": "value"},
		"str": {"column": "value"},
		"lowercase": {"column": "text"},
		"uppercase": {"column": "text"},
		"proper": {"column": "text"},
		"propper": {"column": "text"},
		"ltrim": {"column": "text"},
		"rtrim": {"column": "text"},
		"trim": {"column": "text"},
		"length": {"column": "text"},
		"day": {"column": "date"},
		"month": {"column": "date"},
		"year": {"column": "date"},
		"week": {"column": "date"},
		"quarter": {"column": "date"},
		"iso_quarter": {"column": "date"},
		"iso_week": {"column": "date"},
		"iso_week_day": {"column": "date"},
		"iso_year": {"column": "date"},
		"now": {"column": "date"},
		"today": {"column": "date"},
	}
	assert set(parameters) == set(OPERATIONS)
	for operation, operation_parameters in parameters.items():
		input_count = 2 if operation in ("join", "union") else (
			0 if operation in ("read_csv", "input") else 1
		)
		dag = pipeline(operation, operation_parameters, inputs=input_count)
		module = compile_module(tmp_path, dag)
		datasources = {f"op_{index}": data for index in range(input_count)}
		module.run(datasources)


def test_polars_matrix_rejects_removed_frameworks():
	from script_builder.ir import build_plan

	with pytest.raises(ValueError, match="Unsupported target"):
		build_plan(pipeline("read_csv", {"filepath": "x"}, 0), framework="pyarrow")
	with pytest.raises(ValueError, match="Unsupported target"):
		build_plan(pipeline("read_csv", {"filepath": "x"}, 0), framework="pyspark")
