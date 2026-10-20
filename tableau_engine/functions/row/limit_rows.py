"""Limit the number of rows in a dataframe."""

import pandas as pd


def limit_rows(df: pd.DataFrame, limit: int) -> pd.DataFrame:
	"""Return a copy containing at most ``limit`` rows from the start."""
	if limit < 0:
		raise ValueError("limit must be zero or greater")
	return df.head(limit).copy()