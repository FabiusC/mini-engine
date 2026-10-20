"""Decide which column receives the result of a column transformation."""

import pandas as pd


def resolve_output_column(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> str:
	"""Return the source column, the requested new name, or the next indexed name."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	if not new_column:
		if new_column_name is not None:
			raise ValueError("new_column_name requires new_column to be true")
		return column
	if new_column_name is not None:
		if new_column_name in df.columns:
			raise ValueError(f"Column {new_column_name!r} already exists")
		return new_column_name
	index = 1
	while f"{column}_{index}" in df.columns:
		index += 1
	return f"{column}_{index}"
