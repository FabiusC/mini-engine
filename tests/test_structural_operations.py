"""Verify dataframe structural operations and their validation."""

import pandas as pd
import pytest

from engine.core.operation_registry import execute_operation


def test_sort_orders_rows_in_requested_direction_without_mutating_input() -> None:
	frame = pd.DataFrame({"score": [2, 5, 1], "label": ["b", "a", "c"]})

	result = execute_operation("sort", [frame], column="score", direction="desc")

	assert result["score"].tolist() == [5, 2, 1]
	assert result["label"].tolist() == ["a", "b", "c"]
	assert frame["score"].tolist() == [2, 5, 1]


def test_drop_column_accepts_one_or_multiple_columns() -> None:
	frame = pd.DataFrame({"a": [1], "b": [2], "c": [3]})

	result = execute_operation("drop-column", [frame], column=["a", "b"])

	assert result.columns.tolist() == ["c"]
	assert frame.columns.tolist() == ["a", "b", "c"]


def test_rename_column_and_change_data_type() -> None:
	frame = pd.DataFrame({"profit": [1.5, -2.0], "postal_code": [12345, 67890]})

	renamed = execute_operation(
		"rename-column", [frame], column="profit", new_name="profit_margin"
	)
	converted = execute_operation(
		"change-data-type", [renamed], column="postal_code", new_type="string"
	)

	assert "profit_margin" in converted
	assert converted["postal_code"].dtype == pd.StringDtype()
	assert frame["profit"].tolist() == [1.5, -2.0]
	assert frame["postal_code"].dtype == "int64"


@pytest.mark.parametrize(
	"operation, parameters",
	[
		("sort", {"column": "missing"}),
		("drop-column", {"column": "missing"}),
		("change-data-type", {"column": "missing", "new_type": "str"}),
	],
)
def test_structural_operations_rely_on_pandas_for_missing_columns(
	operation: str,
	parameters: dict[str, str],
) -> None:
	frame = pd.DataFrame({"value": [1], "other": [2]})

	with pytest.raises(KeyError):
		execute_operation(operation, [frame], **parameters)


def test_sort_rejects_invalid_direction() -> None:
	frame = pd.DataFrame({"value": [1]})
	with pytest.raises(ValueError, match="direction"):
		execute_operation("sort", [frame], column="value", direction="sideways")


def test_rename_rejects_existing_destination() -> None:
	frame = pd.DataFrame({"value": [1], "other": [2]})
	with pytest.raises(ValueError, match="already exists"):
		execute_operation("rename-column", [frame], column="value", new_name="other")