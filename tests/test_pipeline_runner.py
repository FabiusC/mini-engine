import pandas as pd
import pytest

from engine.core.pipeline_runner import PipelineRunner


def _node(
	node_id: str,
	operation: str,
	input_ports: list[str],
	output_ports: list[str],
) -> dict[str, object]:
	return {
		"id": node_id,
		"input_ports": [{"id": port_id, "ordinal": index} for index, port_id in enumerate(input_ports)],
		"output_ports": [{"id": port_id} for port_id in output_ports],
		"operation": {"id": node_id, "name": operation},
	}


def _edge(
	edge_id: str,
	source: dict[str, object],
	target: dict[str, object],
	source_port: str,
	target_port: str,
) -> dict[str, object]:
	return {
		"id": edge_id,
		"source_node_id": source["id"],
		"target_node_id": target["id"],
		"source_output_port_id": source_port,
		"target_input_port_id": target_port,
		"source_node": source,
		"target_node": target,
	}


def _branching_pipeline() -> dict[str, list[dict[str, object]]]:
	inner = _node("inner", "inner_join", ["left", "right"], ["inner_out"])
	limit = _node("limit", "limit", ["limit_in"], ["limit_out"])
	filter_node = _node("filter", "filter", ["filter_in"], ["filter_out"])
	outer = _node("outer", "outer_join", ["outer_left", "outer_right"], ["outer_out"])
	return {
		"edges": [
			_edge("edge-1", inner, limit, "inner_out", "limit_in"),
			_edge("edge-2", inner, filter_node, "inner_out", "filter_in"),
			_edge("edge-3", limit, outer, "limit_out", "outer_left"),
			_edge("edge-4", filter_node, outer, "filter_out", "outer_right"),
		]
	}


def test_runner_executes_join_branches_limit_filter_and_outer_join() -> None:
	runner = PipelineRunner(_branching_pipeline())
	datasources = {
		"left": pd.DataFrame({"id": [1, 2, 3], "left_value": ["a", "b", "c"]}),
		"right": pd.DataFrame({"id": [2, 3, 4], "right_value": [20, 30, 40]}),
	}
	parameters = {
		"limit": {"limit": 1},
		"filter": {"column": "id", "operator": ">", "value": 2},
		"outer": {"left_on": "id", "right_on": "id"},
	}

	results = runner.run(datasources, parameters)

	assert results["inner"]["id"].tolist() == [2, 3]
	assert results["limit"]["id"].tolist() == [2]
	assert results["filter"]["id"].tolist() == [3]
	assert results["outer"]["id"].tolist() == [2, 3]
	assert runner.output_node_ids == ("outer",)


def test_join_infers_a_single_shared_column_but_rejects_ambiguous_keys() -> None:
	join = _node("join", "inner_join", ["left", "right"], ["join_out"])
	limit = _node("limit", "limit", ["limit_in"], ["limit_out"])
	runner = PipelineRunner(
		{"edges": [_edge("join-to-limit", join, limit, "join_out", "limit_in")]}
	)
	left = pd.DataFrame({"id": [1, 2], "left_value": ["a", "b"]})
	right = pd.DataFrame({"id": [2, 3], "right_value": [20, 30]})
	datasources = {"left": left, "right": right}
	results = runner.run(datasources, {"limit": {"limit": 10}})
	assert results["join"]["id"].tolist() == [2]
	assert runner.datasource_port_ids == ("left", "right")

	left["region"] = ["S", "N"]
	right["region"] = ["N", "W"]
	with pytest.raises(ValueError, match="needs join keys"):
		runner.run(datasources, {"limit": {"limit": 10}})