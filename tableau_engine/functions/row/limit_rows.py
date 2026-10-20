"""Keep the first rows of a dataframe."""

import pandas as pd


def limit_rows(df: pd.DataFrame, limit: int) -> pd.DataFrame:
	"""Return a copy containing at most ``limit`` rows."""
	limit = int(limit)
	if limit < 0:
		raise ValueError("limit must be zero or greater")
	return df.head(limit).copy()
