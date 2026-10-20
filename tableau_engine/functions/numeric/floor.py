"""Round numeric values down to the nearest integer."""

import math

import pandas as pd

from tableau_engine.functions.structural.output_column import resolve_output_column


def floor(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with values rounded down in the source or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	numeric_values = pd.to_numeric(result[column], errors="raise")
	result[target] = numeric_values.map(
		lambda value: math.floor(value) if pd.notna(value) else value
	)
	return result