"""Verify normalized DAGs built from API snapshots and their execution."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from main import export_clean_pipeline, run_pipeline
from tableau_engine.core.pipeline_clean import merge_pipeline_clean
from tableau_engine.core.pipeline_runner import PipelineRunner


ROOT = Path(__file__).resolve().parents[1]


def _read_operation_responses() -> dict[str, list[dict[str, object]]]:
	nodes = json.loads((ROOT / "dag/nodes.json").read_text(encoding="utf-8"))
	operation_ids = {
		node["operation_id"] for node in nodes["data"] if not node.get("is_deleted")
	}
	return {
		"data": [
			json.loads((ROOT / "dag" / f"{id}.json").read_text(encoding="utf-8"))["data"]
			for id in sorted(operation_ids)
		]
	}


def test_merge_snapshots_has_the_local_pipeline_schema() -> None:
	nodes = json.loads((ROOT / "dag/nodes.json").read_text(encoding="utf-8"))
	edges = json.loads((ROOT / "dag/edges.json").read_text(encoding="utf-8"))
	clean = merge_pipeline_clean(edges, nodes, _read_operation_responses())

	assert set(clean) == {"nodes", "edges"}
	assert len(clean["nodes"]) == len(nodes["data"])
	assert len(clean["edges"]) == len(edges["data"])
	assert clean["nodes"][0] == {
		"id": nodes["data"][0]["id"],
		"input_ports": [
			{"id": port["id"], "ordinal": port["ordinal"]}
			for port in nodes["data"][0]["input_ports"]
		],
		"output_ports": [
			{"id": port["id"], "ordinal": port["ordinal"]}
			for port in nodes["data"][0]["output_ports"]
		],
		"operation": {"id": "a41e3632-2549-49ea-b252-3b9e97b7b759", "name": "inner_join"},
		"parameters": {"left_on": "Customer ID", "right_on": "Customer ID"},
	}
	assert set(clean["edges"][0]) == {
		"id", "source_node_id", "target_node_id",
		"source_output_port_id", "target_input_port_id",
	}
	runner = PipelineRunner(clean, base_dir=ROOT)
	assert runner.datasource_port_ids == ()
	results = runner.run()
	assert not results[runner.output_node_ids[0]].empty


def test_current_snapshot_parameters_are_loaded_and_execute_without_external_data(
	tmp_path: Path,
) -> None:
	nodes = json.loads((ROOT / "dag/nodes.json").read_text(encoding="utf-8"))
	edges = json.loads((ROOT / "dag/edges.json").read_text(encoding="utf-8"))
	clean = merge_pipeline_clean(edges, nodes, _read_operation_responses())
	parameters = {node["id"]: node["parameters"] for node in clean["nodes"]}

	assert parameters["b6c84e8c-1115-45c4-a561-44acff99e138"] == {
		"left_on": "Customer ID", "right_on": "Customer ID",
	}
	assert parameters["5bf00f4b-a830-4b0f-9211-533488c671c2"] == {
		"left_on": "Customer ID", "right_on": "Customer ID",
	}
	assert parameters["8d2a0a01-39e2-48bb-baa1-c446baac2a03"] == {"limit": 100}
	assert parameters["bee978e7-0fc4-491b-8ec2-07a95b3937e5"] == {
		"column": "Profit", "operator": ">", "value": 100,
	}
	assert parameters["504433cd-7ea1-4644-9ade-c60b590b473c"] == {
		"left_on": "Customer ID", "right_on": "Customer ID",
	}

	runner = PipelineRunner(clean, base_dir=ROOT)
	assert runner.datasource_port_ids == ()
	results = runner.run()
	filtered = results["bee978e7-0fc4-491b-8ec2-07a95b3937e5"]
	assert not filtered.empty
	assert (filtered["Profit"] > 100).all()


def _node(id: str = "source") -> dict:
	return {
		"id": id, "operation_id": "op", "parameters": [],
		"input_ports": [], "output_ports": [],
	}


def test_merge_filters_deleted_records_and_retains_isolated_nodes() -> None:
	source = _node()
	source["input_ports"] = [
		{"id": "active", "ordinal": None},
		{"id": "deleted_port", "ordinal": 1, "is_deleted": True},
	]
	deleted = {**_node("deleted"), "is_deleted": True}
	result = merge_pipeline_clean(
		{"data": [
			{"id": "deleted_node_edge", "source_node_id": "source", "target_node_id": "deleted"},
			{"id": "deleted_edge", "is_deleted": True},
		]},
		{"data": [source, deleted, _node("isolated")]},
		{"data": {"id": "op", "name": "example"}},
	)
	assert result["edges"] == []
	assert [node["id"] for node in result["nodes"]] == ["source", "isolated"]
	assert result["nodes"][0]["input_ports"] == [{"id": "active", "ordinal": 0}]


@pytest.mark.parametrize("parameters", [
	{"column": "v", "create_new_column": True, "new_column_name": None, "value": 0},
	[{"name": "column", "value": "v"}, {"name": "create_new_column", "value": False}],
	None, [],
])
def test_merge_preserves_typed_parameters_without_mutating_inputs(parameters) -> None:
	nodes = {"data": [{**_node(), "parameters": parameters}]}
	before = deepcopy(nodes)
	clean = merge_pipeline_clean({"data": []}, nodes, {"id": "op", "name": "absolute"})
	expected = (
		{item["name"]: item["value"] for item in parameters}
		if isinstance(parameters, list) else parameters or {}
	)
	assert clean["nodes"][0]["parameters"] == expected
	assert nodes == before


@pytest.mark.parametrize("parameters", [
	"value", [1], [{"name": "column"}], [{"value": "v"}],
	[{"name": "column", "value": "v"}, {"name": "column", "value": "other"}],
])
def test_merge_rejects_invalid_or_duplicate_parameters(parameters) -> None:
	with pytest.raises(ValueError, match="parameter"):
		merge_pipeline_clean([], [{**_node(), "parameters": parameters}], {"id": "op", "name": "upper"})


def test_merge_rejects_dangling_edges_missing_operations_and_duplicate_nodes() -> None:
	with pytest.raises(ValueError, match="unknown node"):
		merge_pipeline_clean(
			[{"id": "edge", "source_node_id": "source", "target_node_id": "missing"}],
			[_node()], {"id": "op", "name": "upper"},
		)
	with pytest.raises(ValueError, match="missing operation"):
		merge_pipeline_clean([], [_node()], [])
	with pytest.raises(ValueError, match="Duplicate node"):
		merge_pipeline_clean([], [_node(), _node()], {"id": "op", "name": "upper"})


def test_export_overwrites_real_snapshots_deterministically(tmp_path: Path) -> None:
	for name in ["nodes.json", "edges.json"] + [
		f"{op['id']}.json" for op in _read_operation_responses()["data"]
		if op["id"] != "local_write_csv"
	]:
		shutil.copy(ROOT / "dag" / name, tmp_path / name)
	path = tmp_path / "pipeline_clean.json"
	path.write_text("stale content", encoding="utf-8")
	export_clean_pipeline(tmp_path)
	first = path.read_text(encoding="utf-8")
	pipeline = json.loads(first)
	assert len(pipeline["nodes"]) == 7
	assert len(pipeline["edges"]) == 8
	output_nodes = [
		node for node in pipeline["nodes"]
		if node["operation"]["name"] == "write_csv"
	]
	assert output_nodes == []
	export_clean_pipeline(tmp_path)
	assert path.read_text(encoding="utf-8") == first


def test_run_pipeline_executes_pipeline_test_writer(tmp_path: Path) -> None:
	pipeline_path = tmp_path / "pipeline_test.json"
	shutil.copy(ROOT / "dag" / "pipeline_test.json", pipeline_path)
	output_path = tmp_path / "processed.csv"
	parameters = {"local_write_clean_output": {"filepath": str(output_path)}}

	run_pipeline(ROOT, pipeline_path, parameters=parameters)

	assert output_path.is_file()
	result = pd.read_csv(output_path)
	assert not result.empty
	assert len(result.columns) == 133


def test_generated_pipeline_can_replace_local_pipeline_file(tmp_path: Path, capsys) -> None:
	dag = tmp_path / "dag"
	dag.mkdir()
	pd.DataFrame({"v": [-2, 3]}).to_csv(tmp_path / "input.csv", index=False)
	local = {
		"nodes": [
			{"id": "read", "operation_id": "read_op", "input_ports": [],
			 "output_ports": [{"id": "read_out", "ordinal": 0}],
			 "parameters": {"filepath": "input.csv"}},
			{"id": "absolute", "operation_id": "abs_op",
			 "input_ports": [{"id": "abs_in", "ordinal": 0}],
			 "output_ports": [{"id": "abs_out", "ordinal": 0}],
			 "parameters": [{"name": "column", "value": "v"},
				{"name": "create_new_column", "value": True}]},
			{"id": "write", "operation_id": "write_op",
			 "input_ports": [{"id": "write_in", "ordinal": 0}], "output_ports": [],
			 "parameters": {"filepath": "output/result.csv"}},
		],
		"edges": [
			{"id": "e1", "source_node_id": "read", "target_node_id": "absolute",
			 "source_output_port_id": "read_out", "target_input_port_id": "abs_in"},
			{"id": "e2", "source_node_id": "absolute", "target_node_id": "write",
			 "source_output_port_id": "abs_out", "target_input_port_id": "write_in"},
		],
	}
	for key in ("nodes", "edges"):
		(dag / f"{key}.json").write_text(json.dumps({"data": local[key]}), encoding="utf-8")
	for id, name in [("read_op", "read_csv"), ("abs_op", "absolute"), ("write_op", "write_csv")]:
		(dag / f"{id}.json").write_text(json.dumps({"data": {"id": id, "name": name}}), encoding="utf-8")
	export_clean_pipeline(dag)
	run_pipeline(tmp_path, dag / "pipeline_clean.json")
	assert pd.read_csv(tmp_path / "output/result.csv")["v_processed"].tolist() == [2, 3]
	assert "write: 2 rows, 2 columns" in capsys.readouterr().out
