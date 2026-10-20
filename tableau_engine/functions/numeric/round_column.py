"""Round numeric values to a specified number of decimal places."""

import pandas as pd

from tableau_engine.functions.structural.output_column import resolve_output_column


def round_column(
	df: pd.DataFrame,
	column: str,
	decimals: int = 0,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with rounded values in the source or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	result[target] = pd.to_numeric(result[column], errors="raise").round(decimals)
	return result