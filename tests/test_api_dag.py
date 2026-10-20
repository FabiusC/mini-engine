from pathlib import Path

import pandas as pd
import pytest

from tableau_engine.core.dag_graph import load_dag
from tableau_engine.core.dag_runner import DAGRunner
from tableau_engine.interfaces.row import RowInterface
from tableau_engine.interfaces.structural import StructuralInterface


ROOT = Path(__file__).resolve().parents[1]
NODE_INNER_JOIN = "5bf00f4b-a830-4b0f-9211-533488c671c2"
NODE_JOIN_SOURCE = "b6c84e8c-1115-45c4-a561-44acff99e138"
NODE_LIMIT = "8d2a0a01-39e2-48bb-baa1-c446baac2a03"
NODE_FILTER = "bee978e7-0fc4-491b-8ec2-07a95b3937e5"
NODE_OUTER_JOIN = "504433cd-7ea1-4644-9ade-c60b590b473c"


def _test_datasources() -> dict[str, pd.DataFrame]:
	return {
		"d177055b-30e4-4755-aad0-1c278a2bc4be": pd.DataFrame(
			{"id": [1, 2], "left_value": ["a", "b"]}
		),
		"445ba155-5458-4f8a-8e60-511308d77303": pd.DataFrame(
			{"id": [1, 3], "right_value": [10, 30]}
		),
		"e62d5b6c-a237-452d-9192-dd2c39535f77": pd.DataFrame(
			{"id": [1, 2], "extra": ["x", "y"]}
		),
	}


def _test_parameters() -> dict[str, dict[str, object]]:
	return {
		NODE_JOIN_SOURCE: {"left_on": "id", "right_on": "id"},
		NODE_INNER_JOIN: {"left_on": "id", "right_on": "id"},
		NODE_LIMIT: {"limit": 10},
		NODE_FILTER: {"column": "id", "operator": ">", "value": 0},
		NODE_OUTER_JOIN: {"left_on": "id", "right_on": "id"},
	}


def test_api_snapshots_build_a_topological_plan_and_find_missing_ports() -> None:
	dag = load_dag(ROOT / "dag")

	assert [node.operation for node in dag.nodes] == [
		"inner_join",
		"inner_join",
		"limit",
		"filter",
		"outer_join",
	]
	assert [(node_id, port.ordinal) for node_id, port in dag.missing_inputs] == [
		(NODE_JOIN_SOURCE, 0),
		(NODE_JOIN_SOURCE, 1),
		(NODE_INNER_JOIN, 1),
	]


def test_runner_executes_all_operations_through_category_facades() -> None:
	dag = load_dag(ROOT / "dag")
	results = DAGRunner(dag).run(_test_datasources(), _test_parameters())

	assert len(results[NODE_JOIN_SOURCE]) == 1
	assert len(results[NODE_INNER_JOIN]) == 1
	assert len(results[NODE_LIMIT]) == 1
	assert len(results[NODE_FILTER]) == 1
	assert len(results[NODE_OUTER_JOIN]) == 1
	assert StructuralInterface._operations.keys() == {"inner_join", "outer_join"}
	assert RowInterface._operations.keys() == {"filter", "limit"}


def test_runner_requires_external_data_and_join_parameters() -> None:
	dag = load_dag(ROOT / "dag")
	with pytest.raises(ValueError, match="Missing datasource"):
		DAGRunner(dag).run({}, {})

	with pytest.raises(ValueError, match="left_on and right_on"):
		DAGRunner(dag).run(_test_datasources(), {})