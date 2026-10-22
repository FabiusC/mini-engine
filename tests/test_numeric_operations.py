"""Verify numeric transformations and output-column handling."""

import pandas as pd
import pytest

from engine.core.operation_registry import execute_operation


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

	result = execute_operation(
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

	result = execute_operation("floor", [frame], column="value")

	assert result["value"].iloc[0] == -3
	assert pd.isna(result["value"].iloc[1])
	assert frame["value"].iloc[0] == -2.7


def test_numeric_operation_rejects_non_numeric_columns() -> None:
	frame = pd.DataFrame({"value": ["not numeric"]})

	with pytest.raises(ValueError):
		execute_operation("absolute", [frame], column="value")


def test_clean_float_coerces_invalid_values_and_preserves_source() -> None:
	frame = pd.DataFrame({"value": ["1.25", "bad", None, float("nan")]})

	result = execute_operation("clean_float", [frame], column="value")

	assert result["value"].tolist() == [1.25, 0.0, 0.0, 0.0]
	assert result["value"].dtype == "float64"
	assert frame["value"].iloc[1] == "bad"


@pytest.mark.parametrize(
	"operation, expected",
	[("max", [5.0, 4.0, 7.0]), ("min", [2.0, -1.0, 7.0])],
)
def test_horizontal_min_and_max_create_a_new_column(
	operation: str,
	expected: list[float],
) -> None:
	frame = pd.DataFrame({"left": [2, 4, 7], "right": [5, -1, 7]})

	result = execute_operation(
		operation,
		[frame],
		column_a="left",
		column_b="right",
		new_column_name="result",
	)

	assert result["result"].tolist() == expected
	assert frame.columns.tolist() == ["left", "right"]


def test_power_supports_a_new_output_column() -> None:
	frame = pd.DataFrame({"value": [-2, 3]})

	result = execute_operation(
		"power",
		[frame],
		column="value",
		value=2,
		new_column=True,
		new_column_name="squared",
	)

	assert result["squared"].tolist() == [4, 9]
	assert result["value"].tolist() == [-2, 3]