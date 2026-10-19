"""Lowercase a dataframe text column without mutating the input."""

import pandas as pd


def lowercase(df: pd.DataFrame, column: str) -> pd.DataFrame:
	"""Return a copy with the selected column converted to lowercase."""
	result = df.copy()
	result[column] = result[column].astype("string").str.lower()
	return result