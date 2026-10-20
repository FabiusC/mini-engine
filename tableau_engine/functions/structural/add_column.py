"""Add a new column to a dataframe."""

import pandas as pd


def add_column(df: pd.DataFrame, column_name: str, value: object = None) -> pd.DataFrame:
	"""Return a copy with a new column filled with a constant value."""
	if column_name in df.columns:
		raise ValueError(f"Column {column_name!r} already exists")
	result = df.copy()
	result[column_name] = value
	return result