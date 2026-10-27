"""Execute native artifacts and notebooks; no broker or Kubernetes cluster is needed."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from engine.codegen import build_artifact
from engine.codegen.registry import EMITTERS
from engine.core.pipeline_runner import PipelineRunner
from engine.ir import build_plan
from engine.ir.catalog import compatibility_matrix
from engine.ir.expressions import parse_expression


def node(operation, parameters, inputs=1, name="op"):
	return {
		"id": name, "operation": {"name": operation}, "parameters": parameters,
		"input_ports": [{"id": f"{name}_{index}", "ordinal": index} for index in range(inputs)],
		"output_ports": [{"id": f"{name}_out", "ordinal": 0}],
	}


def pipeline(operation, parameters, inputs=1):
	return {"nodes": [node(operation, parameters, inputs)], "edges": []}


def module_for(tmp_path, dag, framework, notebook=False):
	if framework != "pandas":
		pytest.importorskip(framework)
	directory = tmp_path / "artifact"
	manifest = build_artifact(dag, directory, pipeline_id="native", pipeline_version="1", framework=framework, notebook=notebook)
	spec = importlib.util.spec_from_file_location("native_pipeline", directory / "main.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	source = (directory / "main.py").read_text()
	assert "from engine" not in source
	assert "import engine" not in source
	if framework != "pandas":
		assert "import pandas" not in source
	return module, manifest


@pytest.fixture(scope="module")
def spark():
	pytest.importorskip("pyspark")
	from pyspark.sql import SparkSession
	os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
	session = SparkSession.builder.master("local[1]").appName("mini-engine-tests").config(
		"spark.ui.enabled", "false",
	).config("spark.sql.shuffle.partitions", "1").getOrCreate()
	yield session
	session.stop()


def native_frame(framework, values, spark=None):
	if framework == "polars":
		import polars as pl
		return pl.DataFrame(values)
	if framework == "pyarrow":
		import pyarrow as pa
		return pa.table(values)
	return spark.createDataFrame(list(zip(*values.values())), list(values))


def records(frame, framework):
	if framework == "polars":
		return frame.to_dicts()
	if framework == "pyarrow":
		return frame.to_pylist()
	return [row.asDict() for row in frame.collect()]


@pytest.mark.parametrize("framework", ["polars", "pyarrow", "pyspark"])
@pytest.mark.parametrize("operation,parameters", [
	("add_column", {"column_name": "new", "value": 7}),
	("drop_column", {"column": "text"}),
	("rename_column", {"column": "text", "new_name": "name"}),
	("filter", {"column": "id", "operator": ">", "value": 1}),
	("filter", {"column": "text", "operator": "contains", "value": "a"}),
	("limit", {"limit": 2}),
	("sort", {"column": "id", "direction": "desc"}),
])
def test_native_core_matches_pandas(tmp_path, framework, operation, parameters, request):
	session = request.getfixturevalue("spark") if framework == "pyspark" else None
	values = {"id": [1, 2, 3], "text": ["a", "b", "ca"]}
	dag = pipeline(operation, parameters)
	module, manifest = module_for(tmp_path, dag, framework)
	result = records(module.run({"op_0": native_frame(framework, values, session)})["op"], framework)
	reference = PipelineRunner(dag).run({"op_0": pd.DataFrame(values)})["op"].to_dict("records")
	assert result == reference
	assert manifest["target"]["framework"] == framework
	assert manifest["execution"]["command"][0] == ("spark-submit" if framework == "pyspark" else "python")


@pytest.mark.parametrize("framework", ["polars", "pyarrow", "pyspark"])
@pytest.mark.parametrize("file_type", ["csv", "parquet"])
def test_native_io_roundtrip(tmp_path, framework, file_type, request):
	session = request.getfixturevalue("spark") if framework == "pyspark" else None
	frame = native_frame(framework, {"id": [1, 2], "text": ["a", "b"]}, session)
	path = tmp_path / f"data.{file_type}"
	write = pipeline("output", {"destination_type": file_type, "output_path": str(path)})
	module, _ = module_for(tmp_path, write, framework)
	assert records(module.run({"op_0": frame})["op"], framework) == [{"id": 1, "text": "a"}, {"id": 2, "text": "b"}]
	read = pipeline("input", {"source_type": file_type, "filepath_or_connection": str(path)}, 0)
	source = EMITTERS[framework]().emit(build_plan(read, framework=framework))
	namespace = {}
	exec(compile(source, "<native-reader>", "exec"), namespace)
	assert sorted(records(namespace["run"]()["op"], framework), key=lambda row: row["id"]) == [
		{"id": 1, "text": "a"}, {"id": 2, "text": "b"},
	]


@pytest.mark.parametrize("framework", ["polars", "pyarrow", "pyspark"])
@pytest.mark.parametrize("match_type", ["auto", "manual"])
def test_native_union(tmp_path, framework, match_type, request):
	session = request.getfixturevalue("spark") if framework == "pyspark" else None
	dag = pipeline("union", {"match_type": match_type}, 2)
	module, _ = module_for(tmp_path, dag, framework)
	datasources = {
		"op_0": native_frame(framework, {"id": [1], "v": [2]}, session),
		"op_1": native_frame(framework, {"id": [3], "v": [4]}, session),
	}
	assert records(module.run(datasources)["op"], framework) == [{"id": 1, "v": 2}, {"id": 3, "v": 4}]


@pytest.mark.parametrize("framework", ["polars", "pyspark"])
@pytest.mark.parametrize("how", ["inner", "left", "right", "outer"])
def test_native_join_null_keys_and_overlapping_columns(tmp_path, framework, how, request):
	session = request.getfixturevalue("spark") if framework == "pyspark" else None
	dag = pipeline("join", {"how": how, "left_on": "id", "right_on": "id"}, 2)
	module, _ = module_for(tmp_path, dag, framework)
	left, right = {"id": [1, None], "v": ["left", "null"]}, {"id": [2, None], "v": ["right", "null"]}
	if framework == "pyspark":
		# Construct true SQL nulls, not IEEE NaN converted from a pandas float column.
		datasources = {
			"op_0": session.createDataFrame([(1, "left"), (None, "null")], "id long, v string"),
			"op_1": session.createDataFrame([(2, "right"), (None, "null")], "id long, v string"),
		}
	else:
		datasources = {"op_0": native_frame(framework, left), "op_1": native_frame(framework, right)}
	result = records(module.run(datasources)["op"], framework)
	reference = PipelineRunner(dag).run({"op_0": pd.DataFrame(left), "op_1": pd.DataFrame(right)})["op"]
	actual = pd.DataFrame(result)
	actual["id"] = actual["id"].astype("float64")
	assert_frame_equal(actual.sort_values("id").reset_index(drop=True),
		reference.sort_values("id").reset_index(drop=True), check_dtype=False)


@pytest.mark.parametrize("framework", ["polars", "pyspark"])
def test_native_cast_and_date_nodes(tmp_path, framework, request):
	session = request.getfixturevalue("spark") if framework == "pyspark" else None
	dag = pipeline("change_data_type", {"column": "v", "target_type": "int", "create_new_column": True})
	module, _ = module_for(tmp_path, dag, framework)
	result = records(module.run({"op_0": native_frame(framework, {"v": ["1", "2"]}, session)})["op"], framework)
	assert result == [{"v": "1", "v_processed": 1}, {"v": "2", "v_processed": 2}]
	for operation, expected in [("year", 2024), ("month", 2), ("day", 29)]:
		date_dag = pipeline(operation, {"column": "v"})
		source = EMITTERS[framework]().emit(build_plan(date_dag, framework=framework))
		namespace = {}
		exec(compile(source, "<date-script>", "exec"), namespace)
		assert records(namespace["run"]({"op_0": native_frame(framework, {"v": ["2024-02-29"]}, session)})["op"], framework) == [{"v": expected}]


@pytest.mark.parametrize("expression", [
	"__import__('os')", "col('a').__class__", "[x for x in col('a')]",
	"col('a')[0]", "(lambda: 1)()", "open('file')", "a + 1", "col(x)",
	"col('a') < 2 < 3", "abs(value=1)", "1e999",
])
def test_expression_language_rejects_code_injection(expression):
	with pytest.raises(ValueError):
		parse_expression(expression)


@pytest.mark.parametrize("framework", ["pandas", "polars", "pyspark"])
@pytest.mark.parametrize("expression,expected", [
	('col("v") * param("factor") + 1', [3, 5]),
	('upper(col("text"))', ["A", "B"]),
	('col("v") > 1 and col("v") < 3', [False, True]),
	('not (col("v") > 1)', [True, False]),
	('10 if col("v") > 1 else 0', [0, 10]),
	('abs(-col("v"))', [1, 2]),
])
def test_expression_ast_runs_natively(tmp_path, framework, expression, expected, request):
	session = request.getfixturevalue("spark") if framework == "pyspark" else None
	dag = pipeline("fx", {"column_name": "result", "expression": expression})
	module, manifest = module_for(tmp_path, dag, framework)
	values = {"v": [1, 2], "text": ["a", "b"]}
	frame = pd.DataFrame(values) if framework == "pandas" else native_frame(framework, values, session)
	params = {"factor": 2} if "param(" in expression else {}
	result = module.run({"op_0": frame}, params)["op"]
	if framework == "pandas":
		actual = result["result"].tolist()
	else:
		actual = [row["result"] for row in records(result, framework)]
	assert actual == expected
	assert manifest["parameters_schema"]["required"] == list(params)


@pytest.mark.parametrize("operation,parameters", [
	("and", {"column": "v", "sentencia1": "v > 0", "sentencia2": "v < 3", "reemplazar_campo": False, "nombre_nueva_columna": "ok"}),
	("not", {"column": "v", "sentencia1": "v > 0"}),
	("coalesce", {"column": "v", "default_value": 0}),
	("conditional_map", {"column": "v", "condition_func": {"operator": ">", "value": 1}, "true_value": "yes", "false_value": "no"}),
])
def test_legacy_logical_nodes_match_runner(tmp_path, operation, parameters):
	dag = pipeline(operation, parameters)
	module, _ = module_for(tmp_path, dag, "pandas")
	datasources = {"op_0": pd.DataFrame({"v": [None, 1, 2, 3]})}
	assert_frame_equal(module.run(datasources)["op"], PipelineRunner(dag).run(datasources)["op"])


@pytest.mark.parametrize("operation,extra", [
	("date_parser", {"date_format": "%Y-%m-%d"}), ("date_parse", {"date_format": "%Y-%m-%d"}),
	("date_trunc", {"part": "month"}), ("day", {}), ("month", {}), ("year", {}),
	("week", {}), ("quarter", {}), ("iso_quarter", {}), ("iso_week", {}),
	("iso_week_day", {}), ("iso_year", {}), ("date_add", {"unit": "months", "amount": 1}),
	("date_sub", {"unit": "days", "amount": 1}), ("date_diff", {"end_column": "end"}),
	("date_name", {"part": "month"}), ("extract_date_part", {"part": "year"}),
])
def test_date_helpers_match_runner(tmp_path, operation, extra):
	parameters = {("start_column" if operation == "date_diff" else "column"): "v", **extra}
	dag = pipeline(operation, parameters)
	module, _ = module_for(tmp_path, dag, "pandas")
	datasources = {"op_0": pd.DataFrame({"v": ["2024-01-31", "2024-02-29"], "end": ["2025-01-31", "2024-03-29"]})}
	assert_frame_equal(module.run(datasources)["op"], PipelineRunner(dag).run(datasources)["op"])


def test_notebook_is_valid_deterministic_and_executable(tmp_path):
	nbformat = pytest.importorskip("nbformat")
	NotebookClient = pytest.importorskip("nbclient").NotebookClient
	source_path = tmp_path / "source.csv"
	pd.DataFrame({"v": [1, 2]}).to_csv(source_path, index=False)
	dag = pipeline("read_csv", {"filepath": str(source_path)}, 0)
	_, manifest = module_for(tmp_path, dag, "polars", notebook=True)
	path = tmp_path / "artifact/pipeline.ipynb"
	notebook = nbformat.read(path, as_version=4)
	nbformat.validate(notebook)
	NotebookClient(notebook, timeout=60, kernel_name="python3").execute()
	assert notebook.cells[-1].execution_count == 3
	assert len(manifest["files"]) == 2
	second = tmp_path / "second"
	build_artifact(dag, second, pipeline_id="native", pipeline_version="1", framework="polars", notebook=True)
	assert path.read_bytes() == (second / "pipeline.ipynb").read_bytes()


def test_matrix_and_destination_constraints_are_enforced():
	matrix = compatibility_matrix()
	assert all(matrix["read_csv"].values())
	assert not matrix["fx"]["pyarrow"]
	assert matrix["logical"] == {"pandas": True, "polars": False, "pyarrow": False, "pyspark": False}
	for framework in ("polars", "pyarrow", "pyspark"):
		for operation, params in [
			("input", {"source_type": "sql", "filepath_or_connection": "sqlite://", "table_or_sheet": "x"}),
			("output", {"destination_type": "csv", "output_path": "x", "write_mode": "append"}),
			("write_csv", {"filepath": "x", "index": True}),
		]:
			with pytest.raises(ValueError):
				build_plan(pipeline(operation, params, 0 if operation == "input" else 1), framework=framework)
	for framework in ("polars", "pyspark"):
		with pytest.raises(ValueError, match="identical"):
			build_plan(pipeline("join", {"left_on": "a", "right_on": "b"}, 2), framework=framework)
		with pytest.raises(ValueError, match="unsupported"):
			build_plan(pipeline("pivot", {"pivot_type": "rows_to_columns", "index_cols": ["id"], "target_col": "a", "values_col": "b"}), framework=framework)


def test_runtime_target_constraints_cannot_be_bypassed_with_parameters(tmp_path):
	dag = pipeline("output", {"destination_type": {"$param": "format"}, "output_path": "never-created"})
	module, _ = module_for(tmp_path, dag, "polars")
	import polars as pl
	with pytest.raises(ValueError, match="only csv and parquet"):
		module.run({"op_0": pl.DataFrame({"v": [1]})}, {"format": "excel"})
	assert not (tmp_path / "never-created").exists()


@pytest.mark.parametrize("framework", ["polars", "pyarrow", "pyspark"])
def test_native_entrypoint_runs_outside_repository(tmp_path, framework):
	pytest.importorskip(framework)
	input_path = tmp_path / "input.csv"
	pd.DataFrame({"id": [1, 2]}).to_csv(input_path, index=False)
	dag = pipeline("read_csv", {"filepath": str(input_path)}, 0)
	module_for(tmp_path, dag, framework)
	executable = ["spark-submit", "--master", "local[1]"] if framework == "pyspark" else [sys.executable]
	completed = subprocess.run(
		[*executable, str(tmp_path / "artifact/main.py")],
		cwd=tmp_path, env={**os.environ, "PYTHONPATH": "", "SPARK_LOCAL_IP": "127.0.0.1"},
		capture_output=True, text=True, timeout=90, check=True,
	)
	assert json.loads(completed.stdout.strip().splitlines()[-1])["op"] == {"rows": 2, "columns": 1}


def test_compiler_entrypoint_no_longer_runs_pipeline_runner(tmp_path):
	root = Path(__file__).resolve().parents[1]
	subprocess.run([
		sys.executable, "-c",
		"import sys; import main; assert 'engine.core.pipeline_runner' not in sys.modules",
	], cwd=root, check=True)
	subprocess.run([
		sys.executable, str(root / "main.py"), str(root / "dag/pipeline_codegen.json"),
		"--output-dir", str(tmp_path / "artifact"), "--pipeline-id", "orders",
		"--pipeline-version", "3", "--framework", "polars", "--notebook",
	], cwd=tmp_path, capture_output=True, text=True, check=True)
	assert (tmp_path / "artifact/main.py").is_file()
	assert (tmp_path / "artifact/pipeline.ipynb").is_file()
