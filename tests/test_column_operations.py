"""Verify text transformations and column creation rules."""

import pandas as pd
import pytest

from tableau_engine.functions.structural import StructuralProcessor
from tableau_engine.core.operation_registry import execute_operation


def _frame() -> pd.DataFrame:
	return pd.DataFrame({"name": ["Ana", None], "name_1": ["taken", "taken"]})


def test_text_operation_updates_the_source_column_by_default() -> None:
	frame = _frame()
	result = execute_operation("uppercase", [frame], column="name")

	assert result["name"].iloc[0] == "ANA"
	assert pd.isna(result["name"].iloc[1])
	assert frame["name"].iloc[0] == "Ana"


def test_new_column_without_name_uses_the_next_free_index() -> None:
	result = execute_operation("lowercase", [_frame()], column="name", new_column=True)

	assert result["name_2"].iloc[0] == "ana"
	assert result["name"].iloc[0] == "Ana"


def test_new_column_uses_the_requested_name() -> None:
	result = execute_operation(
		"uppercase", [_frame()], column="name", new_column=True, new_column_name="upper_name"
	)

	assert result["upper_name"].iloc[0] == "ANA"


@pytest.mark.parametrize(
	"parameters, message",
	[
		({"new_column": True, "new_column_name": "name_1"}, "already exists"),
		({"new_column": False, "new_column_name": "other"}, "requires new_column"),
	],
)
def test_invalid_output_column_requests_are_rejected(parameters: dict, message: str) -> None:
	arguments = {"column": "name", **parameters}
	with pytest.raises(ValueError, match=message):
		execute_operation("uppercase", [_frame()], **arguments)


def test_missing_source_column_uses_pandas_key_error() -> None:
	with pytest.raises(KeyError):
		execute_operation("uppercase", [_frame()], column="missing")


def test_add_column_fills_a_constant_and_rejects_existing_names() -> None:
	result = StructuralProcessor.add_column(_frame(), "region", "South")

	assert result["region"].tolist() == ["South", "South"]
	with pytest.raises(ValueError, match="already exists"):
		StructuralProcessor.add_column(_frame(), "name", "x")
