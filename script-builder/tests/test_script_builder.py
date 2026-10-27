"""Compiler contracts and golden comparisons: generated script vs. the pandas operations called directly."""

import ast
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from script_builder.codegen import PandasEmitter, build_artifact
from script_builder.dag.pipeline_clean import merge_pipeline_clean
from builder_testing import reference_run
from script_builder.ir import build_plan
from script_builder.ir.catalog import ALIASES, OPERATIONS


ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "script-builder" / "src" / "main.py"


def node(name, operation, parameters=None, inputs=1):
	return {
		"id": name,
		"operation": {"name": operation},
		"parameters": {} if parameters is None else parameters,
		"input_ports": [{"id": f"{name}_in_{i}", "ordinal": i} for i in range(inputs)],
		"output_ports": [{"id": f"{name}_out", "ordinal": 0}],
	}


def edge(source, target, ordinal=0):
	return {
		"id": f"{source}_{target}_{ordinal}",
		"source_node_id": source, "source_output_port_id": f"{source}_out",
		"target_node_id": target, "target_input_port_id": f"{target}_in_{ordinal}",
	}


def load_script(path):
	spec = importlib.util.spec_from_file_location("generated_pipeline", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def compile_module(tmp_path, pipeline):
	artifact = tmp_path / "artifact"
	manifest = build_artifact(pipeline, artifact, pipeline_id="test", pipeline_version="1")
	return load_script(artifact / "main.py"), manifest


def test_plan_preserves_port_order_external_bindings_aliases_and_isolation():
	pipeline = {
		"nodes": [
			node("left", "limit", {"limit": 1}),
			node("right", "drop-column", {"columns": ["unused"]}),
			node("join", "left_join", {"left_on": "id", "right_on": "id"}, 2),
		],
		"edges": [edge("right", "join", 1), edge("left", "join", 0)],
	}
	pipeline["nodes"][2]["input_ports"].reverse()
	before = deepcopy(pipeline)
	plan = build_plan(pipeline)
	assert [step.id for step in plan.steps] == ["left", "right", "join"]
	assert plan.steps[1].operation == "drop_column"
	assert plan.steps[2].operation == "join"
	assert plan.steps[2].parameters["how"] == "left"
	assert [binding.node_id for binding in plan.steps[2].inputs] == ["left", "right"]
	assert plan.steps[0].inputs[0].port_id == "left_in_0"
	assert plan.datasource_port_ids == ("left_in_0", "right_in_0")
	assert plan.output_node_ids == ("join",)
	assert pipeline == before
	pipeline["nodes"][0]["parameters"]["limit"] = 99
	assert plan.steps[0].parameters["limit"] == 1
	serialized = plan.to_dict()
	serialized["steps"][0]["parameters"]["limit"] = 99
	assert plan.steps[0].parameters["limit"] == 1
	assert json.loads(json.dumps(serialized)) == serialized


def test_plan_supports_legacy_embedded_nodes_and_disconnected_components():
	left, right = node("a", "limit", {"limit": 1}), node("b", "limit", {"limit": 2})
	connection = {**edge("a", "b"), "source_node": left, "target_node": right}
	assert build_plan({"edges": [connection]}).output_node_ids == ("b",)
	plan = build_plan({"nodes": [right, left], "edges": []})
	assert plan.output_node_ids == ("a", "b")


def test_api_responses_compile_through_cleaner_without_executing_data(tmp_path):
	clean = merge_pipeline_clean(
		{"data": [edge("read", "limit")]},
		{"data": [
			{
				**node("read", "read_csv", inputs=0), "operation_id": "read-op",
				"parameters": [{"name": "filepath", "value": {"$param": "source"}}],
			},
			{
				**node("limit", "limit"), "operation_id": "limit-op",
				"parameters": [{"name": "limit", "value": 2}],
			},
		]},
		{"data": [{"id": "read-op", "name": "read_csv"}, {"id": "limit-op", "name": "limit"}]},
	)
	plan = build_plan(clean)
	assert [step.operation for step in plan.steps] == ["read_csv", "limit"]
	assert plan.runtime_parameters == ("source",)
	manifest = build_artifact(clean, tmp_path / "compiled", pipeline_id="api", pipeline_version="1")
	assert manifest["parameters_schema"]["required"] == ["source"]


@pytest.mark.parametrize("operation,parameters,inputs", [
	("unknown", {}, 1),
	("uppercase", {}, 1),
	("read_csv", {"filepath": "a"}, 1),
	("join", {}, 1),
	("union", {}, 1),
	("limit", {}, 1),
	("limit", {"limit": True}, 1),
	("limit", {"limit": -1}, 1),
	("limit", {"limit": 1, "typo": 2}, 1),
	("sort", {"column": "a", "direction": "sideways"}, 1),
	("drop_column", {}, 1),
	("drop_column", {"column": "a", "columns": ["b"]}, 1),
	("change_data_type", {"column": "a"}, 1),
	("change_data_type", {"column": "a", "new_type": "int", "target_type": "str"}, 1),
	("change_data_type", {"column": "a", "new_type": "int", "new_column_name": "new"}, 1),
	("join", {"left_on": "id"}, 2),
	("join", {"suffixes": ["_x"]}, 2),
	("aggregate", {"group_by": [], "aggregations": {}}, 1),
	("sample", {"sample_type": "random", "fraction_or_count": 1.5}, 1),
	("input", {"source_type": "sql", "filepath_or_connection": "sqlite://"}, 0),
	("add_column", {"column_name": "a", "value": float("nan")}, 1),
	("add_column", {"column_name": "a", "value": Path("not-json")}, 1),
	("limit", {"limit": {"$param": ""}}, 1),
	("limit", {"limit": {"$param": "n", "extra": 1}}, 1),
])
def test_invalid_operation_contracts_fail_before_emission(operation, parameters, inputs):
	with pytest.raises(ValueError):
		build_plan({"nodes": [node("a", operation, parameters, inputs)], "edges": []})


@pytest.mark.parametrize("case", [
	"duplicate-node", "invalid-node", "unknown-node", "source-port", "target-port",
	"wrong-owner", "duplicate-edge", "duplicate-port", "duplicate-ordinal",
	"cycle", "self-cycle", "multiple-outputs", "empty",
])
def test_invalid_graphs_are_rejected(case):
	pipeline = {
		"nodes": [node("a", "limit", {"limit": 1}), node("b", "limit", {"limit": 1})],
		"edges": [edge("a", "b")],
	}
	if case == "duplicate-node":
		pipeline["nodes"].append(deepcopy(pipeline["nodes"][0]))
	elif case == "invalid-node":
		pipeline["nodes"][0]["id"] = None
	elif case == "unknown-node":
		pipeline["edges"][0]["source_node_id"] = "missing"
	elif case == "source-port":
		pipeline["edges"][0]["source_output_port_id"] = "missing"
	elif case == "target-port":
		pipeline["edges"][0]["target_input_port_id"] = "missing"
	elif case == "wrong-owner":
		pipeline["edges"][0]["source_output_port_id"] = "b_out"
	elif case == "duplicate-edge":
		pipeline["edges"].append(deepcopy(pipeline["edges"][0]))
	elif case == "duplicate-port":
		pipeline["nodes"][1]["input_ports"][0]["id"] = "a_in_0"
	elif case == "duplicate-ordinal":
		pipeline["nodes"][1]["input_ports"].append({"id": "extra", "ordinal": 0})
	elif case == "cycle":
		pipeline["edges"].append(edge("b", "a"))
	elif case == "self-cycle":
		pipeline["edges"] = [edge("a", "a")]
	elif case == "multiple-outputs":
		pipeline["nodes"][0]["output_ports"].append({"id": "extra", "ordinal": 1})
	elif case == "empty":
		pipeline = {"nodes": [], "edges": []}
	with pytest.raises(ValueError):
		build_plan(pipeline)


def test_unsupported_target_and_failed_build_do_not_publish(tmp_path):
	pipeline = {"nodes": [node("a", "limit", {"limit": 1})], "edges": []}
	directory = tmp_path / "invalid"
	with pytest.raises(ValueError, match="Unsupported target"):
		build_artifact(pipeline, directory, pipeline_id="a", pipeline_version="1", framework="unknown")
	assert not directory.exists()
	with pytest.raises(ValueError, match="pipeline_id"):
		build_artifact(pipeline, directory, pipeline_id="", pipeline_version="1")
	assert not directory.exists()


@pytest.mark.parametrize("operation,parameters", [
	("add_column", {"column_name": "new", "value": 0}),
	("add_column", {"column_name": "new", "value": None}),
	("drop_column", {"column": "unused"}),
	("drop-column", {"columns": ["unused", "text"]}),
	("rename_column", {"column": "text", "new_name": "renamed"}),
	("rename-column", {"column": "text", "new_name": "renamed"}),
	("change_data_type", {"column": "text", "target_type": "int"}),
	("change-data-type", {"column": "text", "new_type": "int", "create_new_column": True}),
	("change_data_type", {"column": "text", "new_type": "int", "create_new_column": True, "new_column_name": "custom"}),
	("filter", {"column": "id", "operator": ">", "value": 1}),
	("filter", {"column": "group", "operator": "!=", "value": "a"}),
	("filter", {"column": "group", "operator": "isnull"}),
	("filter", {"column": "group", "operator": "contains", "value": "."}),
	("limit", {"limit": 0}),
	("limit", {"limit": 2}),
	("sort", {"column": "id", "direction": "desc"}),
	("sort", {"column": "id", "direction": "des"}),
	("sort", {"column": "id", "direction": "DESC"}),
	("sample", {"sample_type": "head", "fraction_or_count": 0.5}),
	("sample", {"sample_type": "random", "fraction_or_count": 2, "random_state": 42}),
	("sample", {"sample_type": "random", "fraction_or_count": 0.5, "random_state": 42}),
	("aggregate", {"group_by": ["group"], "aggregations": {"id": ["sum", "count"]}}),
	("aggregate", {"group_by": [], "aggregations": {"id": "sum"}}),
])
def test_single_input_operations_match_runner(tmp_path, operation, parameters):
	pipeline = {"nodes": [node("operation", operation, parameters)], "edges": []}
	frame = pd.DataFrame(
		{"id": [2, 1, 3], "group": ["a", None, "a."], "text": ["2", "1", "3"], "unused": [4, 5, 6]},
		index=[8, 2, 5],
	)
	before = frame.copy(deep=True)
	datasources = {"operation_in_0": frame}
	expected = reference_run(pipeline, datasources)
	module, _ = compile_module(tmp_path, pipeline)
	assert_frame_equal(module.run(datasources)["operation"], expected["operation"])
	assert_frame_equal(frame, before)


@pytest.mark.parametrize("operation", ["join", "inner_join", "outer_join", "left_join", "right_join"])
def test_joins_match_runner_with_nulls_suffixes_and_port_order(tmp_path, operation):
	join = node("join", operation, {"left_on": "id", "right_on": "id", "suffixes": ["_l", "_r"]}, 2)
	join["input_ports"].reverse()
	pipeline = {"nodes": [join], "edges": []}
	datasources = {
		"join_in_0": pd.DataFrame({"id": [2, None, 1], "value": ["l2", "null", "l1"]}),
		"join_in_1": pd.DataFrame({"id": [None, 2, 4], "value": ["null", "r2", "r4"]}),
	}
	module, _ = compile_module(tmp_path, pipeline)
	assert_frame_equal(module.run(datasources)["join"], reference_run(pipeline, datasources)["join"])


def test_join_inference_and_errors_match_runner(tmp_path):
	pipeline = {"nodes": [node("join", "join", {}, 2)], "edges": []}
	module, _ = compile_module(tmp_path, pipeline)
	datasources = {
		"join_in_0": pd.DataFrame({"id": [1], "left": [2]}),
		"join_in_1": pd.DataFrame({"id": [1], "right": [3]}),
	}
	assert_frame_equal(module.run(datasources)["join"], reference_run(pipeline, datasources)["join"])
	datasources["join_in_1"]["left"] = 4
	with pytest.raises(ValueError, match="needs join keys"):
		module.run(datasources)


@pytest.mark.parametrize("match_type", ["auto", "manual"])
def test_union_matches_runner(tmp_path, match_type):
	pipeline = {"nodes": [node("union", "union", {"match_type": match_type}, 3)], "edges": []}
	datasources = {
		"union_in_0": pd.DataFrame({"a": [1], "b": [2]}),
		"union_in_1": pd.DataFrame({"b": [3], "a": [4]}),
		"union_in_2": pd.DataFrame({"x": [5], "y": [6]}),
	}
	module, _ = compile_module(tmp_path, pipeline)
	assert_frame_equal(module.run(datasources)["union"], reference_run(pipeline, datasources)["union"])


@pytest.mark.parametrize("pivot_type", ["columns_to_rows", "rows_to_columns"])
def test_pivot_matches_runner(tmp_path, pivot_type):
	pipeline = {"nodes": [node("pivot", "pivot", {
		"pivot_type": pivot_type, "index_cols": ["id"], "target_col": "key", "values_col": "value",
	})], "edges": []}
	frame = pd.DataFrame({"id": [1, 2], "key": ["a", "b"], "value": [10, 20]})
	if pivot_type == "columns_to_rows":
		frame = pd.DataFrame({"id": [1, 2], "a": [10, 20], "b": [30, 40]})
	datasources = {"pivot_in_0": frame}
	module, _ = compile_module(tmp_path, pipeline)
	assert_frame_equal(module.run(datasources)["pivot"], reference_run(pipeline, datasources)["pivot"])


@pytest.mark.parametrize("file_type", ["csv", "excel", "parquet"])
@pytest.mark.parametrize("mode", ["overwrite", "append"])
def test_io_formats_and_append_match_runner(tmp_path, file_type, mode):
	suffix = {"csv": ".csv", "excel": ".xlsx", "parquet": ".parquet"}[file_type]
	source = tmp_path / f"source{suffix}"
	frame = pd.DataFrame({"id": [1, 2], "text": ["café", "niño"]})
	if file_type == "csv":
		frame.to_csv(source, sep=";", encoding="latin1", index=False)
	elif file_type == "excel":
		frame.to_excel(source, index=False)
	else:
		frame.to_parquet(source, index=False)
	pipeline = {
		"nodes": [
			node("read", "input", {
				"source_type": file_type, "filepath_or_connection": str(source),
				"encoding": "latin1", "delimiter": ";",
			}, 0),
			node("write", "output", {
				"destination_type": file_type, "output_path": "out" + suffix,
				"write_mode": mode, "encoding": "latin1", "delimiter": ";",
			}),
		],
		"edges": [edge("read", "write")],
	}
	module, _ = compile_module(tmp_path, pipeline)
	expected_dir, actual_dir = tmp_path / "expected", tmp_path / "actual"
	for _ in range(2):
		reference = reference_run(pipeline, base_dir=expected_dir)
		generated = module.run(base_dir=actual_dir)
		for node_id in reference:
			assert_frame_equal(generated[node_id], reference[node_id])
	from script_builder.operations.pandas.io import IOOperations
	io = IOOperations()
	assert_frame_equal(
		io.input_data(file_type, actual_dir / ("out" + suffix), encoding="latin1", delimiter=";"),
		io.input_data(file_type, expected_dir / ("out" + suffix), encoding="latin1", delimiter=";"),
	)


def test_sql_input_matches_runner_and_does_not_resolve_connection_as_path(tmp_path):
	from sqlalchemy import create_engine
	connection = f"sqlite:///{tmp_path / 'input.db'}"
	engine = create_engine(connection)
	with engine.begin() as conn:
		pd.DataFrame({"id": [1, 2]}).to_sql("orders", conn, index=False)
	engine.dispose()
	pipeline = {"nodes": [node("read", "input", {
		"source_type": "sql", "filepath_or_connection": connection, "table_or_sheet": "orders",
	}, 0)], "edges": []}
	module, _ = compile_module(tmp_path, pipeline)
	assert_frame_equal(
		module.run(base_dir=tmp_path)["read"],
		reference_run(pipeline, base_dir=tmp_path)["read"],
	)


def test_csv_encoding_fallback_and_write_index_match_runner(tmp_path):
	pd.DataFrame({"text": ["café"]}).to_csv(tmp_path / "source.csv", encoding="latin1", index=False)
	pipeline = {
		"nodes": [
			node("read", "read_csv", {"filepath": "source.csv"}, 0),
			node("write", "write_csv", {"filepath": "generated/out.csv", "index": True}),
		],
		"edges": [edge("read", "write")],
	}
	module, _ = compile_module(tmp_path, pipeline)
	expected = reference_run(pipeline, base_dir=tmp_path)
	generated = module.run(base_dir=tmp_path)
	assert_frame_equal(generated["write"], expected["write"])
	assert pd.read_csv(tmp_path / "generated/out.csv").columns.tolist() == ["Unnamed: 0", "text"]


def test_branched_pipeline_and_structural_fixture_match_runner(tmp_path):
	shutil.copytree(ROOT / "data", tmp_path / "data")
	pipeline = json.loads((ROOT / "dag/pipeline.json").read_text(encoding="utf-8"))
	reference = reference_run(pipeline, base_dir=tmp_path)
	module, manifest = compile_module(tmp_path, pipeline)
	generated = module.run(base_dir=tmp_path)
	assert set(reference) == set(generated)
	for node_id in reference:
		assert_frame_equal(generated[node_id], reference[node_id])
	assert manifest["output_node_ids"] == list(build_plan(pipeline).output_node_ids)
	assert manifest["datasource_port_ids"] == []


def test_fanout_does_not_mutate_shared_input_and_retains_all_terminal_nodes(tmp_path):
	pipeline = {
		"nodes": [
			node("add", "add_column", {"column_name": "branch", "value": "left"}),
			node("drop", "drop_column", {"column": "text"}),
			node("source", "limit", {"limit": 10}),
		],
		"edges": [edge("source", "add"), edge("source", "drop")],
	}
	datasources = {"source_in_0": pd.DataFrame({"id": [1, 2], "text": ["a", "b"]})}
	module, manifest = compile_module(tmp_path, pipeline)
	reference = reference_run(pipeline, datasources)
	actual = module.run(datasources)
	for node_id in reference:
		assert_frame_equal(actual[node_id], reference[node_id])
	assert manifest["output_node_ids"] == ["add", "drop"]
	assert actual["source"].columns.tolist() == ["id", "text"]


def test_runtime_references_nested_values_and_manifest_schema(tmp_path):
	pipeline = {"nodes": [node("add", "add_column", {
		"column_name": {"$param": "column"},
		"value": {"nested": [{"$param": "value"}]},
	})], "edges": []}
	module, manifest = compile_module(tmp_path, pipeline)
	params = {"column": "metadata", "value": "x"}
	frame = pd.DataFrame({"id": [1]}, index=["nested"])
	result = module.run({"add_in_0": frame}, params)
	# A dict value uses pandas' index alignment, just as the reference operation.
	reference_pipeline = deepcopy(pipeline)
	reference_pipeline["nodes"][0]["parameters"] = {"column_name": "metadata", "value": {"nested": ["x"]}}
	assert_frame_equal(
		result["add"],
		reference_run(reference_pipeline, {"add_in_0": frame})["add"],
	)
	assert manifest["parameters_schema"]["required"] == ["column", "value"]
	assert manifest["parameters_schema"]["properties"]["column"]["allOf"] == [
		{"type": "string", "minLength": 1},
	]
	assert params == {"column": "metadata", "value": "x"}


def test_runtime_contracts_fail_before_node_io(tmp_path):
	pipeline = {
		"nodes": [
			node("read", "read_csv", {"filepath": "DOES_NOT_EXIST.csv"}, 0),
			node("limit", "limit", {"limit": {"$param": "count"}}),
		],
		"edges": [edge("read", "limit")],
	}
	module, _ = compile_module(tmp_path, pipeline)
	for parameters, match in [
		({}, "missing"), ({"count": 1, "typo": 1}, "unknown"),
		({"count": True}, "type"), ({"count": -1}, ">="),
		({"count": float("nan")}, "finite JSON"),
		({"count": float("inf")}, "finite JSON"),
		({"count": object()}, "finite JSON"),
		({1: 1}, "names must be strings"),
	]:
		with pytest.raises(ValueError, match=match):
			module.run(parameters=parameters)


def test_missing_datasource_and_runtime_column_error_are_explicit(tmp_path):
	pipeline = {"nodes": [node("drop", "drop_column", {"column": "missing"})], "edges": []}
	module, _ = compile_module(tmp_path, pipeline)
	with pytest.raises(ValueError, match="Missing datasource"):
		module.run()
	with pytest.raises(ValueError, match="DataFrame"):
		module.run({"drop_in_0": "not-a-frame"})
	with pytest.raises(KeyError, match="missing"):
		module.run({"drop_in_0": pd.DataFrame({"id": [1]})})


def test_literals_cannot_inject_code_and_only_used_helpers_are_bundled(tmp_path):
	malicious = "x'); __import__('os').system('never-run'); #"
	pipeline = {"nodes": [node(malicious, "add_column", {"column_name": malicious, "value": malicious})], "edges": []}
	module, _ = compile_module(tmp_path, pipeline)
	frame = pd.DataFrame({"id": [1]})
	result = module.run({f"{malicious}_in_0": frame})[malicious]
	assert result[malicious].tolist() == [malicious]
	source = (tmp_path / "artifact/main.py").read_text()
	tree = ast.parse(source)
	assert not any(
		isinstance(item, ast.ImportFrom) and (item.module or "").startswith("script_builder")
		for item in ast.walk(tree)
	)
	assert "script_builder.operations" not in source
	assert "_StructuralOperations_add_column" in source
	assert "_StructuralOperations_join" not in source
	assert "execute_operation" not in source


def test_artifacts_are_deterministic_hashed_and_not_overwritten(tmp_path):
	pipeline = {
		"nodes": [
			node("b", "limit", {"limit": 2}),
			node("a", "limit", {"limit": 1}),
			node("join", "join", {}, 2),
		],
		"edges": [edge("b", "join", 1), edge("a", "join", 0)],
	}
	before = deepcopy(pipeline)
	first = build_artifact(pipeline, tmp_path / "one", pipeline_id="test", pipeline_version="1")
	pipeline["nodes"].reverse()
	pipeline["edges"].reverse()
	second = build_artifact(pipeline, tmp_path / "two", pipeline_id="test", pipeline_version="1")
	assert first == second
	script = (tmp_path / "one/main.py").read_bytes()
	assert script == (tmp_path / "two/main.py").read_bytes()
	assert first["files"][0]["sha256"] == hashlib.sha256(script).hexdigest()
	assert first["plan_hash"] == hashlib.sha256(json.dumps(
		build_plan(before).to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False,
	).encode()).hexdigest()
	assert json.loads((tmp_path / "one/manifest.json").read_text()) == first
	with pytest.raises(FileExistsError):
		build_artifact(before, tmp_path / "one", pipeline_id="test", pipeline_version="2")
	assert (tmp_path / "one/main.py").read_bytes() == script


def test_parameter_object_key_order_does_not_change_artifact():
	first = {
		"nodes": [node("a", "add_column", {"column_name": "x", "value": {"z": 1, "a": 2}})],
		"edges": [],
	}
	second = deepcopy(first)
	second["nodes"][0]["parameters"] = {"value": {"a": 2, "z": 1}, "column_name": "x"}
	assert PandasEmitter().emit(build_plan(first)) == PandasEmitter().emit(build_plan(second))


def test_documented_example_executes_and_matches_reference(tmp_path):
	pipeline = json.loads((ROOT / "dag/pipeline_codegen.json").read_text())
	params = {"source_csv": "source.csv", "output_csv": "result.csv", "row_limit": 2}
	pd.DataFrame({"Sales": [0, 20, -1, 40, 30]}).to_csv(tmp_path / "source.csv", index=False)
	module, manifest = compile_module(tmp_path, pipeline)
	resolved = deepcopy(pipeline)
	values = {"read": ("filepath", "source_csv"), "limit": ("limit", "row_limit"), "write": ("filepath", "output_csv")}
	for item in resolved["nodes"]:
		if item["id"] in values:
			name, param = values[item["id"]]
			item["parameters"][name] = params[param]
	reference = reference_run(resolved, base_dir=tmp_path)
	actual = module.run(parameters=params, base_dir=tmp_path)
	for node_id in reference:
		assert_frame_equal(actual[node_id], reference[node_id])
	assert pd.read_csv(tmp_path / "result.csv")["Sales"].tolist() == [40, 30]
	assert manifest["parameters_schema"]["required"] == ["output_csv", "row_limit", "source_csv"]


def test_builder_and_generated_cli_run_outside_repository(tmp_path):
	pipeline = {
		"nodes": [
			node("read", "read_csv", {"filepath": {"$param": "source"}}, 0),
			node("limit", "limit", {"limit": {"$param": "count"}}),
			node("write", "write_csv", {"filepath": {"$param": "destination"}}),
		],
		"edges": [edge("read", "limit"), edge("limit", "write")],
	}
	(tmp_path / "dag.json").write_text(json.dumps(pipeline))
	artifact = tmp_path / "artifact"
	built = subprocess.run([
		sys.executable, str(BUILDER), str(tmp_path / "dag.json"),
		"--output-dir", str(artifact), "--pipeline-id", "orders", "--pipeline-version", "7",
	], cwd=ROOT, capture_output=True, text=True, check=True)
	assert json.loads((artifact / "manifest.json").read_text())["pipeline_version"] == "7"
	pd.DataFrame({"id": [1, 2, 3]}).to_csv(tmp_path / "input.csv", index=False)
	params = {"source": "input.csv", "destination": "results/output.csv", "count": 2}
	params_file = tmp_path / "params.json"
	params_file.write_text(json.dumps(params))
	command = [
		sys.executable, str(artifact / "main.py"),
		"--params-file", str(params_file), "--base-dir", str(tmp_path),
	]
	worker_env = {**os.environ, "PYTHONPATH": ""}
	subprocess.run([
		sys.executable, "-c",
		"import importlib.util; assert importlib.util.find_spec('script_builder') is None",
	], cwd=tmp_path, env=worker_env, check=True)
	completed = subprocess.run(command, cwd=tmp_path, env=worker_env, capture_output=True, text=True, check=True)
	assert json.loads(completed.stdout)["write"] == {"rows": 2, "columns": 1}
	assert pd.read_csv(tmp_path / "results/output.csv")["id"].tolist() == [1, 2]
	params["count"] = -1
	params_file.write_text(json.dumps(params))
	failed = subprocess.run(command, cwd=tmp_path, env=worker_env, capture_output=True, text=True)
	assert failed.returncode != 0
	assert "ValueError" in failed.stderr
	assert failed.stdout == ""


def test_builder_cli_defaults_artifacts_under_repository_output_folder(tmp_path):
	pipeline = tmp_path / f"cli_default_{tmp_path.name}.json"
	shutil.copy(ROOT / "dag/pipeline.json", pipeline)
	artifact = ROOT / "output" / pipeline.stem
	try:
		subprocess.run([sys.executable, str(BUILDER), str(pipeline)], cwd=tmp_path, capture_output=True, text=True, check=True)
		manifest = json.loads((artifact / "manifest.json").read_text())
		assert (artifact / "main.py").is_file()
		assert (manifest["pipeline_id"], manifest["pipeline_version"]) == (pipeline.stem, "1")
	finally:
		shutil.rmtree(artifact, ignore_errors=True)


def test_generated_cli_supports_external_csv_datasources(tmp_path):
	pipeline = {"nodes": [node("limit", "limit", {"limit": 1})], "edges": []}
	compile_module(tmp_path, pipeline)
	pd.DataFrame({"id": [1, 2]}).to_csv(tmp_path / "input.csv", index=False)
	(tmp_path / "datasources.json").write_text(json.dumps({"limit_in_0": "input.csv"}))
	completed = subprocess.run([
		sys.executable, str(tmp_path / "artifact/main.py"),
		"--datasources-file", str(tmp_path / "datasources.json"), "--base-dir", str(tmp_path),
	], cwd=tmp_path, env={**os.environ, "PYTHONPATH": ""}, capture_output=True, text=True, check=True)
	assert json.loads(completed.stdout)["limit"]["rows"] == 1


def test_generation_is_stable_across_python_hash_seeds(tmp_path):
	pipeline = {
		"nodes": [
			node("a", "limit", {"limit": 1}), node("b", "limit", {"limit": 1}),
			node("join", "join", {}, 2),
		],
		"edges": [edge("a", "join", 0), edge("b", "join", 1)],
	}
	(tmp_path / "pipeline.json").write_text(json.dumps(pipeline))
	for seed in ["1", "2"]:
		subprocess.run([
			sys.executable, str(BUILDER), str(tmp_path / "pipeline.json"),
			"--output-dir", str(tmp_path / seed), "--pipeline-id", "test", "--pipeline-version", "1",
		], cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True, check=True)
	assert (tmp_path / "1/main.py").read_bytes() == (tmp_path / "2/main.py").read_bytes()
	assert (tmp_path / "1/manifest.json").read_bytes() == (tmp_path / "2/manifest.json").read_bytes()


def test_catalog_is_backend_independent():
	code = (
		"import sys; from script_builder.ir import build_plan; "
		"assert 'pandas' not in sys.modules; "
		"assert 'script_builder.operations' not in sys.modules"
	)
	subprocess.run([sys.executable, "-c", code], cwd=BUILDER.parent, check=True)
	for canonical in ALIASES.values():
		assert canonical in OPERATIONS
	assert PandasEmitter.engine == "python"
	assert PandasEmitter.framework == "pandas"
