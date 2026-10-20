import pandas as pd
import pytest

from tableau_engine.core.dag_runner import DAGRunner
from tableau_engine.interfaces.text import TextInterface


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