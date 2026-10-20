"""Verify the compact DAG output built from local API snapshots."""

import json
from pathlib import Path

from tableau_engine.core.pipeline_clean import merge_pipeline_clean


ROOT = Path(__file__).resolve().parents[1]


def _read_operation_responses() -> dict[str, list[dict[str, object]]]:
	"""Read operation definitions referenced by active nodes in the fixture."""
	nodes_json = json.loads((ROOT / "dag" / "nodes.json").read_text(encoding="utf-8"))
	# Avoid loading operation snapshots that are not part of this graph.
	operation_ids = {
		node["operation_id"]
		for node in nodes_json["data"]
		if not node.get("is_deleted")
	}
	return {
		"data": [
			json.loads((ROOT / "dag" / f"{operation_id}.json").read_text(encoding="utf-8"))["data"]
			for operation_id in operation_ids
		]
	}


def test_merge_pipeline_clean_embeds_compact_nodes_in_edges() -> None:
	"""Each edge includes compact endpoint nodes and their operation metadata."""
	nodes_json = json.loads((ROOT / "dag" / "nodes.json").read_text(encoding="utf-8"))
	edges_json = json.loads((ROOT / "dag" / "edges.json").read_text(encoding="utf-8"))
	clean_dag = merge_pipeline_clean(edges_json, nodes_json, _read_operation_responses())

	assert len(clean_dag["edges"]) == len(edges_json["data"])
	first_edge = clean_dag["edges"][0]
	assert first_edge["source_node"]["operation"] == {
		"id": "a41e3632-2549-49ea-b252-3b9e97b7b759",
		"name": "inner_join",
	}
	assert first_edge["target_node"]["input_ports"][0] == {
		"id": "e281e872-1e9c-4ff5-8ce1-997c629c5b01",
		"description": "Left-side dataset",
		"ordinal": 0,
	}
	assert set(first_edge) == {
		"id",
		"source_node_id",
		"target_node_id",
		"source_output_port_id",
		"target_input_port_id",
		"source_node",
		"target_node",
	}


def test_merge_pipeline_clean_accepts_data_envelopes_and_ignores_deleted_records() -> None:
	"""API envelopes are accepted and deleted endpoint nodes are omitted."""
	result = merge_pipeline_clean(
		{"data": [{"id": "edge", "source_node_id": "source", "target_node_id": "missing"}]},
		{"data": [{
			"id": "source",
			"operation_id": "op",
			"is_deleted": False,
			"input_ports": [],
			"output_ports": [],
		}, {
			"id": "deleted",
			"operation_id": "op",
			"is_deleted": True,
		}]},
		{"data": [{"id": "op", "name": "example"}]},
	)

	assert result["edges"][0]["source_node"]["operation"]["name"] == "example"
	assert result["edges"][0]["target_node"] is None