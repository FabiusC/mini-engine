"""Filter dataframe rows with a single condition."""

import pandas as pd


def filter_rows(df: pd.DataFrame, column: str, operator: str, value: object) -> pd.DataFrame:
	"""Return rows matching ``==``, ``>``, ``<`` or a literal ``contains``."""
	if column not in df.columns:
		raise ValueError(f"Filter column {column!r} is not present in the input")
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
