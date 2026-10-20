"""Convert text values to lowercase."""

import pandas as pd

from tableau_engine.functions.column.output_column import resolve_output_column


def lowercase(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with lowercase text in the source column or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	result[target] = result[column].astype("string").str.lower()
	return result
