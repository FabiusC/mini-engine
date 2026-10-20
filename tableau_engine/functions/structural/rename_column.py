"""Rename a dataframe column."""

import pandas as pd


def rename_column(df: pd.DataFrame, column: str, new_name: str) -> pd.DataFrame:
	"""Return a copy with ``column`` renamed to ``new_name``."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	if new_name != column and new_name in df.columns:
		raise ValueError(f"Column {new_name!r} already exists")
	return df.rename(columns={column: new_name})