"""Convert a dataframe column to numeric values."""

import pandas as pd


def to_numeric(
	df: pd.DataFrame,
	column: str,
	errors: str = "raise",
) -> pd.DataFrame:
	"""Return a copy with the selected column parsed as numeric values."""
	result = df.copy()
	result[column] = pd.to_numeric(result[column], errors=errors)
	return result