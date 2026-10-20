"""Filter dataframe rows using one simple condition."""

import pandas as pd


def filter_rows(
	df: pd.DataFrame,
	column: str,
	operator: str,
	value: object,
) -> pd.DataFrame:
	"""Return rows matching equality, numeric comparison, or literal contains."""
	series = df[column]
	if operator == "==":
		mask = series == value
	elif operator == ">":
		mask = series > value
	elif operator == "<":
		mask = series < value
	elif operator == "contains":
		mask = series.astype("string").str.contains(str(value), regex=False, na=False)
	else:
		raise ValueError(f"Unsupported filter operator: {operator!r}")
	return df.loc[mask].copy()