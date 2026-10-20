"""Convert numeric values to their absolute values."""

import pandas as pd

from tableau_engine.functions.structural.output_column import resolve_output_column


def absolute(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with absolute values in the source or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	result[target] = pd.to_numeric(result[column], errors="raise").abs()
	return result