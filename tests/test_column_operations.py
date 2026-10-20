"""Verify text transformations and column creation rules."""

import pandas as pd
import pytest

from tableau_engine.functions.structural import add_column
from tableau_engine.interfaces.text import TextInterface


def _frame() -> pd.DataFrame:
	return pd.DataFrame({"name": ["Ana", None], "name_1": ["taken", "taken"]})


def test_text_operation_updates_the_source_column_by_default() -> None:
	frame = _frame()
	result = TextInterface.execute("uppercase", [frame], column="name")

	assert result["name"].iloc[0] == "ANA"
	assert pd.isna(result["name"].iloc[1])
	assert frame["name"].iloc[0] == "Ana"


def test_new_column_without_name_uses_the_next_free_index() -> None:
	result = TextInterface.execute("lowercase", [_frame()], column="name", new_column=True)

	assert result["name_2"].iloc[0] == "ana"
	assert result["name"].iloc[0] == "Ana"


def test_new_column_uses_the_requested_name() -> None:
	result = TextInterface.execute(
		"uppercase", [_frame()], column="name", new_column=True, new_column_name="upper_name"
	)

	assert result["upper_name"].iloc[0] == "ANA"


@pytest.mark.parametrize(
	"parameters, message",
	[
		({"new_column": True, "new_column_name": "name_1"}, "already exists"),
		({"new_column": False, "new_column_name": "other"}, "requires new_column"),
		({"column": "missing"}, "not present"),
	],
)
def test_invalid_output_column_requests_are_rejected(parameters: dict, message: str) -> None:
	arguments = {"column": "name", **parameters}
	with pytest.raises(ValueError, match=message):
		TextInterface.execute("uppercase", [_frame()], **arguments)


def test_add_column_fills_a_constant_and_rejects_existing_names() -> None:
	result = add_column(_frame(), "region", "South")

	assert result["region"].tolist() == ["South", "South"]
	with pytest.raises(ValueError, match="already exists"):
		add_column(_frame(), "name", "x")
