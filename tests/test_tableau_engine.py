from pathlib import Path

import pandas as pd
import pytest

from tableau_engine.core.dag_runner import DAGRunner
from tableau_engine.interfaces.text import TextInterface
from tableau_engine.io import read_datasource
from tableau_engine.structural import join


def test_runner_chains_text_operations() -> None:
	frame = pd.DataFrame({"text": ["Mixed", None]})
	runner = DAGRunner([
		{"id": "upper", "input": "source", "operation": "UPPER", "column": "text"},
		{"id": "lower", "input": "upper", "operation": "LOWER", "column": "text"},
	])
	result = runner.run(frame, "lower")
	assert result["text"].iloc[0] == "mixed"
	assert pd.isna(result["text"].iloc[1])
	assert frame["text"].iloc[0] == "Mixed"


def test_runner_joins_sources_then_uppercases_a_column() -> None:
	south = pd.DataFrame({"Customer ID": ["A", "B"], "Segment": ["consumer", "home"]})
	central = pd.DataFrame({"Customer ID": ["A", "C"], "Segment": ["corporate", "consumer"]})
	runner = DAGRunner([
		{
			"id": "joined",
			"inputs": ["south", "central"],
			"operation": "JOIN",
			"left_on": "Customer ID",
			"right_on": "Customer ID",
			"how": "inner",
		},
		{"id": "upper", "input": "joined", "operation": "UPPER", "column": "Segment_x"},
	])
	result = runner.run({"south": south, "central": central}, "upper")
	assert result["Segment_x"].tolist() == ["CONSUMER"]
	assert result["Segment_y"].tolist() == ["corporate"]
	assert len(result) == 1


def test_runner_rejects_forward_references() -> None:
	runner = DAGRunner([
		{"id": "first", "input": "missing", "operation": "UPPER", "column": "text"},
	])
	with pytest.raises(ValueError, match="Input must precede"):
		runner.run(pd.DataFrame({"text": ["Mixed"]}), "first")


@pytest.mark.parametrize("operation, expected", [("UPPER", " MIXED "), ("LOWER", " mixed ")])
def test_text_operations_are_pure(operation: str, expected: str) -> None:
	frame = pd.DataFrame({"text": [" Mixed "]})
	result = TextInterface.execute(operation, frame, column="text")
	assert result["text"].iloc[0] == expected
	assert frame["text"].iloc[0] == " Mixed "


def test_unknown_operation_is_rejected() -> None:
	with pytest.raises(ValueError, match="Unknown text operation"):
		TextInterface.execute("TRIM", pd.DataFrame({"text": ["Mixed"]}), column="text")


@pytest.mark.parametrize("encoding", ["utf-8-sig", "latin1"])
def test_read_datasource_returns_dataframe(tmp_path: Path, encoding: str) -> None:
	path = tmp_path / "orders.csv"
	expected = pd.DataFrame({"name": ["caf\u00e9"], "quantity": [2]})
	expected.to_csv(path, index=False, encoding=encoding)
	pd.testing.assert_frame_equal(read_datasource(path), expected)


def test_read_datasource_missing_file(tmp_path: Path) -> None:
	with pytest.raises(FileNotFoundError):
		read_datasource(str(tmp_path / "missing.csv"))


@pytest.mark.parametrize("how, expected_ids", [("inner", [2]), ("left", [1, 2])])
def test_join_returns_matches_without_mutating_inputs(
	how: str, expected_ids: list[int]
) -> None:
	left = pd.DataFrame({"id": [1, 2], "name": ["Alice", "Bob"]})
	right = pd.DataFrame({"customer_id": [2, 3], "amount": [10, 20]})
	original_left = left.copy()
	original_right = right.copy()
	result = join(left, right, left_on="id", right_on="customer_id", how=how)
	assert result["id"].tolist() == expected_ids
	assert result.loc[result["id"] == 2, "amount"].iloc[0] == 10
	pd.testing.assert_frame_equal(left, original_left)
	pd.testing.assert_frame_equal(right, original_right)


def test_join_supports_compound_keys() -> None:
	left = pd.DataFrame({"id": [1, 1], "region": ["South", "Central"]})
	right = pd.DataFrame({"id": [1], "region": ["Central"], "amount": [10]})
	result = join(left, right, left_on=["id", "region"], right_on=["id", "region"])
	assert result["region"].tolist() == ["Central"]