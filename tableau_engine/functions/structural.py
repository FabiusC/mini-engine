"""Structural operations that combine or reshape dataframes."""

from collections.abc import Sequence

import pandas as pd


def add_column(df: pd.DataFrame, column_name: str, value: object = None) -> pd.DataFrame:
	"""Return a copy with a new column filled with a constant value."""
	if column_name in df.columns:
		raise ValueError(f"Column {column_name!r} already exists")
	result = df.copy()
	result[column_name] = value
	return result


def change_data_type(df: pd.DataFrame, column: str, new_type: str) -> pd.DataFrame:
	"""Return a copy with the selected column cast to ``new_type``."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	result = df.copy()
	result[column] = result[column].astype(new_type)
	return result


def drop_column(df: pd.DataFrame, column: str | Sequence[str]) -> pd.DataFrame:
	"""Return a copy without the requested column or columns."""
	columns = [column] if isinstance(column, str) else list(column)
	missing = [name for name in columns if name not in df.columns]
	if missing:
		raise ValueError(f"Columns {missing!r} are not present in the input")
	return df.drop(columns=columns)


def join(
	left: pd.DataFrame,
	right: pd.DataFrame,
	how: str = "inner",
	left_on: str | list[str] | None = None,
	right_on: str | list[str] | None = None,
	suffixes: Sequence[str] = ("_x", "_y"),
) -> pd.DataFrame:
	"""Join two dataframes, inferring the key only when exactly one column is shared."""
	if left_on is None and right_on is None:
		shared = [column for column in left.columns if column in right.columns]
		if len(shared) != 1:
			raise ValueError(f"Join needs join keys; shared columns are {shared}")
		left_on = right_on = shared[0]
	if left_on is None or right_on is None:
		raise ValueError("Join needs both left_on and right_on")
	return left.merge(
		right,
		left_on=left_on,
		right_on=right_on,
		how=how,
		suffixes=tuple(suffixes),
	)


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


def rename_column(df: pd.DataFrame, column: str, new_name: str) -> pd.DataFrame:
	"""Return a copy with ``column`` renamed to ``new_name``."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	if new_name != column and new_name in df.columns:
		raise ValueError(f"Column {new_name!r} already exists")
	return df.rename(columns={column: new_name})


def sort_rows(
	df: pd.DataFrame,
	column: str,
	direction: str = "asc",
) -> pd.DataFrame:
	"""Return a copy sorted by ``column`` in ascending or descending order."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	directions = {"asc": True, "desc": False, "des": False}
	try:
		ascending = directions[direction.lower()]
	except (AttributeError, KeyError) as error:
		raise ValueError("direction must be 'asc' or 'desc'") from error
	return df.sort_values(by=column, ascending=ascending)