"""Uppercase a dataframe text column without mutating the input."""

import pandas as pd


def uppercase(df: pd.DataFrame, column: str) -> pd.DataFrame:
	"""Return a copy with the selected column converted to uppercase."""
	result = df.copy()
	result[column] = result[column].astype("string").str.upper()
	return result