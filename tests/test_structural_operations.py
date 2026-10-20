"""Verify dataframe structural operations and their validation."""

import pandas as pd
import pytest

from tableau_engine.interfaces.structural import StructuralInterface


def test_sort_orders_rows_in_requested_direction_without_mutating_input() -> None:
	frame = pd.DataFrame({"score": [2, 5, 1], "label": ["b", "a", "c"]})

	result = StructuralInterface.execute("sort", [frame], column="score", direction="desc")

	assert result["score"].tolist() == [5, 2, 1]
	assert result["label"].tolist() == ["a", "b", "c"]
	assert frame["score"].tolist() == [2, 5, 1]


def test_drop_column_accepts_one_or_multiple_columns() -> None:
	frame = pd.DataFrame({"a": [1], "b": [2], "c": [3]})

	result = StructuralInterface.execute("drop-column", [frame], column=["a", "b"])

	assert result.columns.tolist() == ["c"]
	assert frame.columns.tolist() == ["a", "b", "c"]


def test_rename_column_and_change_data_type() -> None:
	frame = pd.DataFrame({"profit": [1.5, -2.0], "postal_code": [12345, 67890]})

	renamed = StructuralInterface.execute(
		"rename-column", [frame], column="profit", new_name="profit_margin"
	)
	converted = StructuralInterface.execute(
		"change-data-type", [renamed], column="postal_code", new_type="string"
	)

	assert "profit_margin" in converted
	assert converted["postal_code"].dtype == pd.StringDtype()
	assert frame["profit"].tolist() == [1.5, -2.0]
	assert frame["postal_code"].dtype == "int64"


@pytest.mark.parametrize(
	"operation, parameters, message",
	[
		("sort", {"column": "missing"}, "not present"),
		("sort", {"column": "value", "direction": "sideways"}, "direction"),
		("drop-column", {"column": "missing"}, "not present"),
		("rename-column", {"column": "value", "new_name": "other"}, "already exists"),
		("change-data-type", {"column": "missing", "new_type": "str"}, "not present"),
	],
)
def test_structural_operations_reject_invalid_columns_or_parameters(
	operation: str,
	parameters: dict[str, str],
	message: str,
) -> None:
	frame = pd.DataFrame({"value": [1], "other": [2]})

	with pytest.raises(ValueError, match=message):
		StructuralInterface.execute(operation, [frame], **parameters)