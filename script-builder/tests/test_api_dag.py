"""pipeline_clean: normalize API node/edge/operation responses (offline, outside the main flow)."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from builder_testing import compile_pipeline
from script_builder.dag.pipeline_clean import export_clean_pipeline, merge_pipeline_clean


DAG = Path(__file__).resolve().parents[2] / "dag"


def _read_operation_responses() -> dict[str, list[dict[str, object]]]:
	nodes = json.loads((DAG / "nodes.json").read_text(encoding="utf-8"))
	operation_ids = {
		node["operation_id"] for node in nodes["data"] if not node.get("is_deleted")
	}
	return {
		"data": [
			json.loads((DAG / f"{id}.json").read_text(encoding="utf-8"))["data"]
			for id in sorted(operation_ids)
		]
	}


def test_merge_snapshots_has_the_local_pipeline_schema() -> None:
	nodes = json.loads((DAG / "nodes.json").read_text(encoding="utf-8"))
	edges = json.loads((DAG / "edges.json").read_text(encoding="utf-8"))
	operations = _read_operation_responses()
	clean = merge_pipeline_clean(edges, nodes, operations)

	active_nodes = [node for node in nodes["data"] if not node.get("is_deleted")]
	names = {operation["id"]: operation["name"] for operation in operations["data"]}
	assert set(clean) == {"nodes", "edges"}
	assert [node["id"] for node in clean["nodes"]] == [node["id"] for node in active_nodes]
	first = active_nodes[0]
	assert clean["nodes"][0] == {
		"id": first["id"],
		"input_ports": [
			{"id": port["id"], "ordinal": port["ordinal"]}
			for port in first["input_ports"] if not port.get("is_deleted")
		],
		"output_ports": [
			{"id": port["id"], "ordinal": port["ordinal"]}
			for port in first["output_ports"] if not port.get("is_deleted")
		],
		"operation": {"id": first["operation_id"], "name": names[first["operation_id"]]},
		"parameters": clean["nodes"][0]["parameters"],
	}
	assert all(set(edge) == {
		"id", "source_node_id", "target_node_id",
		"source_output_port_id", "target_input_port_id",
	} for edge in clean["edges"])


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
	for name in ["nodes.json", "edges.json"] + [f"{op['id']}.json" for op in _read_operation_responses()["data"]]:
		shutil.copy(DAG / name, tmp_path / name)
	path = tmp_path / "pipeline_clean.json"
	path.write_text("stale content", encoding="utf-8")
	clean = export_clean_pipeline(tmp_path)
	first = path.read_text(encoding="utf-8")
	assert json.loads(first) == clean
	nodes = json.loads((DAG / "nodes.json").read_text(encoding="utf-8"))
	assert len(clean["nodes"]) == len([node for node in nodes["data"] if not node.get("is_deleted")])
	export_clean_pipeline(tmp_path)
	assert path.read_text(encoding="utf-8") == first


def test_cleaned_api_responses_compile_and_run_as_a_script(tmp_path: Path) -> None:
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
	clean = export_clean_pipeline(dag)
	results = compile_pipeline(clean).run(base_dir=tmp_path)
	assert pd.read_csv(tmp_path / "output/result.csv")["v_processed"].tolist() == [2, 3]
	assert results["write"].shape == (2, 2)


@pytest.mark.parametrize("framework", ["pandas", "polars"])
def test_real_api_snapshots_build_a_script_that_a_worker_runs(tmp_path: Path, framework: str) -> None:
	from script_builder.__main__ import main as builder_main
	from workers import WORKERS

	for name in ["nodes.json", "edges.json"] + [f"{op['id']}.json" for op in _read_operation_responses()["data"]]:
		shutil.copy(DAG / name, tmp_path / name)
	export_clean_pipeline(tmp_path)
	artifact = tmp_path / "artifact"
	manifest = builder_main([str(tmp_path / "pipeline_clean.json"), "--framework", framework, "--output-dir", str(artifact)])
	datasources = json.loads((DAG / "pipeline_clean_datasources.json").read_text(encoding="utf-8"))
	assert sorted(manifest["datasource_port_ids"]) == sorted(datasources)
	shutil.copytree(DAG.parent / "data", tmp_path / "data")
	exit_code = WORKERS[framework]().run(
		artifact, datasources_file=DAG / "pipeline_clean_datasources.json", base_dir=tmp_path,
	)
	assert exit_code == 0
