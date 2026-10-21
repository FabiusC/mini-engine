"""Specification coverage through the same registry used by the DAG."""

import json
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from tableau_engine.core.operation_registry import get_interface
from tableau_engine.core.pipeline_runner import PipelineRunner


def execute(operation: str, *frames: pd.DataFrame, **parameters) -> pd.DataFrame:
	return get_interface(operation).execute(operation, frames, **parameters)


@pytest.mark.parametrize("create", [False, True])
@pytest.mark.parametrize(
	"operation, source, parameters, expected",
	[
		("lower", [" Ab "], {}, [" ab "]),
		("upper", [" Ab "], {}, [" AB "]),
		("trim", [" Ab "], {}, ["Ab"]),
		("ltrim", [" Ab "], {}, ["Ab "]),
		("rtrim", [" Ab "], {}, [" Ab"]),
		("substring", ["abcde"], {"start": 1, "length": 2}, ["bc"]),
		("replace", ["a.b"], {"old_text": ".", "new_text": "-"}, ["a-b"]),
		("split", ["a::b"], {"delimiter": "::", "index": 1}, ["b"]),
		("concat", ["a"], {"columns": ["value", "other"], "separator": "-"}, ["a-2"]),
		("ceiling", [-1.2], {}, [-1]),
		("floor", [-1.2], {}, [-2]),
		("round", [1.234], {"decimals": 2}, [1.23]),
		("abs", [-1.2], {}, [1.2]),
		("arithmetic", [3], {"column_a": "value", "operator": "+", "column_b_or_value": 2}, [5]),
		("date_parser", ["2024/02/29"], {"date_format": "%Y/%m/%d"}, [pd.Timestamp("2024-02-29")]),
		("date_add", ["2024-01-31"], {"unit": "months", "amount": 1}, [pd.Timestamp("2024-02-29")]),
		("date_sub", ["2024-02-29"], {"unit": "years", "amount": 1}, [pd.Timestamp("2023-02-28")]),
		("extract_date_part", ["2024-02-29"], {"part": "weekday"}, [3]),
		("coalesce", [None], {"default_value": "missing"}, ["missing"]),
		("ifnull", [""], {"default_value": "missing"}, ["missing"]),
		("conditional_map", [3], {"condition_func": {"operator": ">", "value": 2}, "true_value": "yes", "false_value": "no"}, ["yes"]),
		("change_data_type", ["3"], {"target_type": "int"}, [3]),
	],
)
def test_transformations_support_both_output_modes(
	operation, source, parameters, expected, create,
) -> None:
	frame = pd.DataFrame({"value": source, "other": [2]}, index=[7])
	before = frame.copy(deep=True)
	arguments = {} if operation in ("arithmetic", "concat") else {"column": "value"}
	result = execute(
		operation, frame, **arguments, **parameters, create_new_column=create,
	)
	target = "value_processed" if create else "value"
	assert result[target].tolist() == expected
	assert result.index.tolist() == [7]
	assert_frame_equal(frame, before)
	if create:
		assert result["value"].tolist() == source


@pytest.mark.parametrize("operation", ["lower", "upper", "trim", "ltrim", "rtrim", "substring", "replace", "split"])
def test_text_operations_preserve_nulls(operation) -> None:
	parameters = {
		"substring": {"start": -2, "length": 1},
		"replace": {"old_text": "a", "new_text": "z"},
		"split": {"delimiter": "-", "index": 8},
	}.get(operation, {})
	result = execute(operation, pd.DataFrame({"v": [None, "abc"]}), column="v", **parameters)
	assert pd.isna(result["v"].iloc[0])
	if operation == "substring":
		assert result["v"].iloc[1] == "b"
	if operation == "split":
		assert pd.isna(result["v"].iloc[1])


def test_output_name_validation_and_collision_policy() -> None:
	frame = pd.DataFrame({"v": ["a"], "v_processed": [1], "v_processed_1": [2]})
	result = execute("upper", frame, column="v", create_new_column=True)
	assert result["v_processed_2"].tolist() == ["A"]
	result = execute("upper", frame, column="v", create_new_column=True, new_column_name="custom")
	assert result["custom"].tolist() == ["A"]
	for parameters in (
		{"create_new_column": True, "new_column_name": "v"},
		{"create_new_column": False, "new_column_name": "new"},
		{"create_new_column": True, "new_column_name": ""},
		{"create_new_column": "false"},
		{"create_new_column": False, "new_column": True},
	):
		with pytest.raises(ValueError):
			execute("upper", frame, column="v", **parameters)


def test_split_expands_without_mutation_or_column_overwrites() -> None:
	frame = pd.DataFrame({"v": ["a|b", "c", None]}, index=[9, 4, 2])
	result = execute("split", frame, column="v", delimiter="|", create_new_column=True, new_column_name="part")
	assert result["part_0"].iloc[:2].tolist() == ["a", "c"]
	assert result["part_1"].iloc[0] == "b"
	assert pd.isna(result["part_1"].iloc[1])
	assert result.index.tolist() == [9, 4, 2]
	assert frame.columns.tolist() == ["v"]
	with pytest.raises(ValueError, match="requires create_new_column"):
		execute("split", frame, column="v", delimiter="|")
	with pytest.raises(ValueError, match="already exist"):
		execute("split", result, column="v", delimiter="|", create_new_column=True, new_column_name="part")


@pytest.mark.parametrize("operator, expected", [("+", [6, 8]), ("-", [2, 4]), ("*", [8, 12]), ("/", [2, 3])])
def test_arithmetic_with_columns_and_constants(operator, expected) -> None:
	frame = pd.DataFrame({"a": [4, 6], "b": [2, 2]})
	for operand in ("b", 2):
		result = execute("arithmetic", frame, column_a="a", operator=operator, column_b_or_value=operand)
		assert result["a"].tolist() == expected
	for operand in ("b", 0):
		with pytest.raises(ValueError, match="zero"):
			execute("arithmetic", frame.assign(b=0), column_a="a", operator="/", column_b_or_value=operand)


@pytest.mark.parametrize(
	"operator, value, expected",
	[("==", 2, [1]), ("!=", 2, [0]), (">", 1, [1]), ("<", 2, [0]), (">=", 2, [1]), ("<=", 1, [0]), ("isnull", None, [2])],
)
def test_filter_comparisons(operator, value, expected) -> None:
	frame = pd.DataFrame({"v": pd.Series([1, 2, None], dtype="Int64")})
	result = execute("filter", frame, column="v", operator=operator, value=value)
	assert result.index.tolist() == expected


def test_filter_contains_is_literal_and_isnull_needs_no_value() -> None:
	frame = pd.DataFrame({"v": ["a.b", "abc", None]})
	assert execute("filter", frame, column="v", operator="contains", value=".").index.tolist() == [0]
	assert execute("filter", frame, column="v", operator="isnull").index.tolist() == [2]


def test_null_handling_and_vectorized_condition_callable() -> None:
	frame = pd.DataFrame({"v": [None, "", 0, False, " "]}, index=[4, 5, 6, 7, 8])
	result = execute("coalesce", frame, column="v", default_value="fallback")
	assert result["v"].tolist() == ["fallback", "fallback", 0, False, " "]
	frame = pd.DataFrame({"v": [1, 3, None]}, index=[4, 5, 6])
	result = execute("conditional_map", frame, column="v", condition_func=lambda s: s > 2, true_value="yes", false_value="no")
	assert result["v"].tolist() == ["no", "yes", "no"]
	with pytest.raises(ValueError, match="boolean Series"):
		execute("conditional_map", frame, column="v", condition_func=lambda s: True, true_value=1, false_value=0)
	with pytest.raises(ValueError, match="callable"):
		execute("conditional_map", frame, column="v", condition_func="v > 2", true_value=1, false_value=0)


@pytest.mark.parametrize(
	"unit, expected",
	[("days", [1.5, -1.5]), ("months", [0, 0]), ("years", [0, 0])],
)
def test_date_diff_is_signed_and_preserves_nulls(unit, expected) -> None:
	frame = pd.DataFrame({
		"start": ["2024-01-01 00:00:00", "2024-01-02 12:00:00", None],
		"end": ["2024-01-02 12:00:00", "2024-01-01 00:00:00", None],
	})
	result = execute("date_diff", frame, start_column="start", end_column="end", unit=unit, create_new_column=True)
	assert result["start_processed"].iloc[:2].tolist() == expected
	assert pd.isna(result["start_processed"].iloc[2])


@pytest.mark.parametrize("unit, expected", [("months", [12, -12, 11, 0]), ("years", [1, -1, 0, 0])])
def test_date_diff_counts_complete_calendar_units(unit, expected) -> None:
	frame = pd.DataFrame({
		"start": ["2023-02-28", "2024-02-28", "2023-03-01", "2024-01-31"],
		"end": ["2024-02-28", "2023-02-28", "2024-02-29", "2024-02-29"],
	})
	result = execute("date_diff", frame, start_column="start", end_column="end", unit=unit)
	assert result["start"].tolist() == expected


@pytest.mark.parametrize("part, expected", [("year", 2024), ("month", 2), ("day", 29), ("weekday", 3)])
def test_extract_parts(part, expected) -> None:
	result = execute("extract_date_part", pd.DataFrame({"v": ["2024-02-29", None]}), column="v", part=part)
	assert result["v"].iloc[0] == expected
	assert pd.isna(result["v"].iloc[1])


def test_sample_count_fraction_and_reproducibility() -> None:
	frame = pd.DataFrame({"v": range(20)})
	assert len(execute("sample", frame, sample_type="head", fraction_or_count=0.25)) == 5
	assert len(execute("sample", frame, sample_type="head", fraction_or_count=1)) == 1
	assert len(execute("sample", frame, sample_type="head", fraction_or_count=1.0)) == 20
	assert len(execute("sample", frame, sample_type="random", fraction_or_count=0.25)) == 5
	first = execute("sample", frame, sample_type="random", fraction_or_count=4, random_state=42)
	second = execute("sample", frame, sample_type="random", fraction_or_count=4, random_state=42)
	assert_frame_equal(first, second)
	for value in (-1, 1.5, True):
		with pytest.raises(ValueError):
			execute("sample", frame, sample_type="head", fraction_or_count=value)


@pytest.mark.parametrize("how, rows", [("inner", 1), ("left", 2), ("right", 2), ("outer", 3)])
def test_generic_join(how, rows) -> None:
	left = pd.DataFrame({"id": [1, 2], "a": ["x", "y"]})
	right = pd.DataFrame({"key": [2, 3], "b": ["z", "w"]})
	result = execute("join", left, right, how=how, left_on="id", right_on="key")
	assert len(result) == rows


def test_union_by_name_and_position() -> None:
	left = pd.DataFrame({"a": [1], "b": [2]})
	right = pd.DataFrame({"b": [3], "a": [4]})
	third = pd.DataFrame({"a": [5], "c": [6]})
	result = execute("union", left, right, third, match_type="auto")
	assert result["a"].tolist() == [1, 4, 5]
	assert result.columns.tolist() == ["a", "b", "c"]
	assert execute("union", left, right, match_type="manual")["a"].tolist() == [1, 3]
	with pytest.raises(ValueError, match="same number"):
		execute("union", left, third[["a"]], match_type="manual")
	with pytest.raises(ValueError, match="at least 2"):
		execute("union", left)
	assert right.columns.tolist() == ["b", "a"]


def test_aggregate_and_pivot_roundtrip() -> None:
	frame = pd.DataFrame({"group": ["a", "a", None], "metric": ["x", "y", "x"], "value": [1, 2, 3]})
	result = execute("aggregate", frame, group_by=["group"], aggregations={"value": "sum"})
	assert result["value"].tolist() == [3, 3]
	assert execute("aggregate", frame, group_by=[], aggregations={"value": "sum"})["value"].tolist() == [6]
	wide = execute("pivot", frame.iloc[:2], pivot_type="rows_to_columns", index_cols=["group"], target_col="metric", values_col="value")
	assert wide["x"].tolist() == [1]
	long = execute("pivot", wide, pivot_type="columns_to_rows", index_cols=["group"], target_col="metric", values_col="value")
	assert long["value"].tolist() == [1, 2]
	with pytest.raises(ValueError, match="duplicate"):
		execute("pivot", pd.concat([frame, frame]), pivot_type="rows_to_columns", index_cols=["group"], target_col="metric", values_col="value")


def test_column_management_aliases_and_datetime_type() -> None:
	frame = pd.DataFrame({"a": ["2024-01-01"], "b": [1]})
	assert execute("drop_column", frame, columns=["b"]).columns.tolist() == ["a"]
	assert execute("rename_column", frame, column="a", new_name="date").columns.tolist() == ["date", "b"]
	result = execute("change_data_type", frame, column="a", target_type="datetime", create_new_column=True)
	assert result["a_processed"].iloc[0] == pd.Timestamp("2024-01-01")
	assert frame["a"].iloc[0] == "2024-01-01"


@pytest.mark.parametrize(
	"operation, parameters",
	[
		("arithmetic", {"column_a": "v", "operator": "**", "column_b_or_value": 1}),
		("filter", {"column": "v", "operator": "eval"}),
		("date_add", {"column": "v", "unit": "hours", "amount": 1}),
		("date_sub", {"column": "v", "unit": "days", "amount": 1.5}),
		("date_diff", {"start_column": "v", "end_column": "v", "unit": "unknown"}),
		("extract_date_part", {"column": "v", "part": "unknown"}),
		("substring", {"column": "v", "start": 0, "length": -1}),
		("split", {"column": "v", "delimiter": "", "index": 0}),
		("sample", {"sample_type": "unknown", "fraction_or_count": 1}),
		("pivot", {"pivot_type": "unknown", "index_cols": [], "target_col": "v", "values_col": "v"}),
	],
)
def test_invalid_parameters_raise(operation, parameters) -> None:
	with pytest.raises(ValueError):
		execute(operation, pd.DataFrame({"v": [1]}), **parameters)


@pytest.mark.parametrize("operation", ["date_parser", "date_add", "date_sub", "extract_date_part"])
def test_invalid_dates_raise(operation) -> None:
	parameters = {
		"date_parser": {"date_format": "%Y-%m-%d"},
		"date_add": {"unit": "days", "amount": 1},
		"date_sub": {"unit": "days", "amount": 1},
		"extract_date_part": {"part": "year"},
	}[operation]
	with pytest.raises(ValueError):
		execute(operation, pd.DataFrame({"v": ["not a date"]}), column="v", **parameters)


@pytest.mark.parametrize("format, suffix", [("csv", ".csv"), ("excel", ".xlsx"), ("parquet", ".parquet")])
def test_io_overwrite_append_and_schema_validation(tmp_path, format, suffix) -> None:
	path = tmp_path / "nested" / f"data{suffix}"
	frame = pd.DataFrame({"id": [1, 2], "name": ["niño", "María"]})
	parameters = {"destination_type": format, "output_path": path}
	assert execute("output", frame, **parameters) is frame
	assert_frame_equal(execute("input", source_type=format, filepath_or_connection=path), frame)
	execute("output", frame.iloc[:1], write_mode="append", **parameters)
	assert execute("input", source_type=format, filepath_or_connection=path)["id"].tolist() == [1, 2, 1]
	with pytest.raises(ValueError, match="matching column"):
		execute("output", frame.rename(columns={"id": "key"}), write_mode="append", **parameters)
	execute("output", frame.iloc[:1], **parameters)
	assert execute("input", source_type=format, filepath_or_connection=path)["id"].tolist() == [1]


@pytest.mark.parametrize("format, suffix", [("csv", ".csv"), ("excel", ".xlsx"), ("parquet", ".parquet")])
def test_append_to_missing_file(tmp_path, format, suffix) -> None:
	path = tmp_path / f"data{suffix}"
	frame = pd.DataFrame({"a": [1]})
	execute("output", frame, destination_type=format, output_path=path, write_mode="append")
	assert_frame_equal(execute("input", source_type=format, filepath_or_connection=path), frame)


def test_csv_configuration_and_excel_sheet_preservation(tmp_path) -> None:
	path = tmp_path / "latin.csv"
	frame = pd.DataFrame({"name": ["niño"]})
	execute("output", frame, destination_type="csv", output_path=path, delimiter=";", encoding="latin1")
	execute("output", frame, destination_type="csv", output_path=path, delimiter=";", encoding="latin1", write_mode="append")
	result = execute("input", source_type="csv", filepath_or_connection=path, delimiter=";", encoding="latin1")
	assert result["name"].tolist() == ["niño", "niño"]
	path = tmp_path / "sheets.xlsx"
	with pd.ExcelWriter(path) as writer:
		frame.to_excel(writer, sheet_name="first", index=False)
		frame.to_excel(writer, sheet_name="other", index=False)
	execute("output", frame, destination_type="excel", output_path=path, write_mode="append")
	assert execute("input", source_type="excel", filepath_or_connection=path, table_or_sheet="first")["name"].tolist() == ["niño", "niño"]
	assert_frame_equal(execute("input", source_type="excel", filepath_or_connection=path, table_or_sheet="other"), frame)


def test_csv_append_handles_a_file_without_a_trailing_newline(tmp_path) -> None:
	path = tmp_path / "no-newline.csv"
	path.write_text("id,name\n1,Ana", encoding="utf-8")
	execute("output", pd.DataFrame({"id": [2], "name": ["Luis"]}),
		destination_type="csv", output_path=path, write_mode="append")
	assert pd.read_csv(path)["name"].tolist() == ["Ana", "Luis"]


def test_null_default_preserves_nulls_and_clears_empty_strings() -> None:
	result = execute("coalesce", pd.DataFrame({"v": ["", None, "a"]}), column="v", default_value=None)
	assert result["v"].isna().tolist() == [True, True, False]


def test_sql_input(tmp_path) -> None:
	from sqlalchemy import create_engine

	connection = f"sqlite:///{tmp_path / 'source.db'}"
	engine = create_engine(connection)
	frame = pd.DataFrame({"id": [1, 2]})
	try:
		frame.to_sql("orders", engine, index=False)
		assert_frame_equal(execute("input", source_type="sql", filepath_or_connection=connection, table_or_sheet="orders"), frame)
	finally:
		engine.dispose()
	with pytest.raises(ValueError, match="table_or_sheet"):
		execute("input", source_type="sql", filepath_or_connection=connection)
	runner = PipelineRunner({"nodes": [], "edges": []}, base_dir=tmp_path)
	assert runner._parameters({"id": "sql", "parameters": {"source_type": "sql", "filepath_or_connection": connection}}, {})["filepath_or_connection"] == connection


@pytest.mark.parametrize(
	"operation, parameters",
	[
		("input", {"source_type": "unknown", "filepath_or_connection": "missing"}),
		("output", {"destination_type": "csv", "output_path": "unused", "write_mode": "unknown"}),
		("output", {"destination_type": "unknown", "output_path": "unused"}),
	],
)
def test_invalid_io_configuration(operation, parameters) -> None:
	with pytest.raises(ValueError):
		execute(operation, *([] if operation == "input" else [pd.DataFrame()]), **parameters)


def test_json_dag_supports_variadic_union_and_new_paths(tmp_path: Path) -> None:
	pd.DataFrame({"name": [" alice "]}).to_csv(tmp_path / "in.csv", index=False)
	nodes = [
		("read", "input", [], {"source_type": "csv", "filepath_or_connection": "in.csv"}),
		("trim", "trim", ["trim_in"], {"column": "name", "create_new_column": True}),
		("upper", "upper", ["upper_in"], {"column": "name_processed"}),
		("union", "union", ["union_0", "union_1", "union_2"], {}),
		("write", "output", ["write_in"], {"destination_type": "parquet", "output_path": "out/result.parquet"}),
	]
	pipeline = {
		"nodes": [
			{"id": id, "operation": {"name": op}, "parameters": params,
			 "input_ports": [{"id": port, "ordinal": i} for i, port in reversed(list(enumerate(ports)))],
			 "output_ports": [{"id": f"{id}_out", "ordinal": 0}]}
			for id, op, ports, params in nodes
		],
		"edges": [
			{"id": str(i), "source_node_id": source, "target_node_id": target,
			 "source_output_port_id": f"{source}_out", "target_input_port_id": port}
			for i, (source, target, port) in enumerate([
				("read", "trim", "trim_in"), ("trim", "upper", "upper_in"),
				("read", "union", "union_0"), ("trim", "union", "union_1"),
				("upper", "union", "union_2"), ("union", "write", "write_in"),
			])
		],
	}
	runner = PipelineRunner(json.loads(json.dumps(pipeline)), base_dir=tmp_path)
	result = runner.run()["write"]
	assert len(result) == 3
	assert result["name_processed"].iloc[1:].tolist() == ["alice", "ALICE"]
	assert_frame_equal(pd.read_parquet(tmp_path / "out/result.parquet"), result)
	assert runner.datasource_port_ids == ()
