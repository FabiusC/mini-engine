"""Verify numeric transformations and output-column handling."""

import pandas as pd
import pytest

from tableau_engine.interfaces.numeric import NumericInterface


@pytest.mark.parametrize(
	"operation, expected",
	[
		("absolute", [2.7, 1.235]),
		("ceiling", [-2.0, 2.0]),
		("floor", [-3.0, 1.0]),
		("round", [-2.7, 1.24]),
	],
)
def test_numeric_operations_create_a_column_without_changing_source(
	operation: str,
	expected: list[float],
) -> None:
	frame = pd.DataFrame({"value": [-2.7, 1.235]})
	parameters = {"decimals": 2} if operation == "round" else {}

	result = NumericInterface.execute(
		operation,
		[frame],
		column="value",
		new_column=True,
		new_column_name="result",
		**parameters,
	)

	assert result["result"].tolist() == expected
	assert result["value"].tolist() == [-2.7, 1.235]
	assert frame.columns.tolist() == ["value"]


def test_numeric_operations_replace_source_and_preserve_missing_values() -> None:
	frame = pd.DataFrame({"value": [-2.7, None]})

	result = NumericInterface.execute("floor", [frame], column="value")

	assert result["value"].iloc[0] == -3
	assert pd.isna(result["value"].iloc[1])
	assert frame["value"].iloc[0] == -2.7


def test_numeric_operation_rejects_non_numeric_columns() -> None:
	frame = pd.DataFrame({"value": ["not numeric"]})

	with pytest.raises(ValueError):
		NumericInterface.execute("absolute", [frame], column="value")