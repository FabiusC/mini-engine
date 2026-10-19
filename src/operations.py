"""Pure dataframe operations used by the mini data engine."""

from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd


def load_csv(filepath: str | Path) -> pd.DataFrame:
	"""Load a CSV, preferring UTF-8 and falling back to Latin-1."""
	try:
		return pd.read_csv(filepath, encoding="utf-8-sig")
	except UnicodeDecodeError:
		return pd.read_csv(filepath, encoding="latin1")


def join_datasets(
	df_left: pd.DataFrame,
	df_right: pd.DataFrame,
	left_on: str | Sequence[str],
	right_on: str | Sequence[str],
	how: str = "inner",
) -> pd.DataFrame:
	"""Join two dataframes on the specified key columns."""
	return df_left.merge(df_right, left_on=left_on, right_on=right_on, how=how)


def union_datasets(df_list: Sequence[pd.DataFrame]) -> pd.DataFrame:
	"""Concatenate dataframes by rows, aligning columns by name."""
	if not df_list:
		raise ValueError("df_list must contain at least one dataframe")
	return pd.concat(df_list, ignore_index=True, sort=False)


def aggregate_data(
	df: pd.DataFrame,
	group_by_cols: Sequence[str],
	aggregations: Mapping[str, str | Sequence[str]],
) -> pd.DataFrame:
	"""Group rows and apply one or more aggregations to selected columns."""
	return df.groupby(list(group_by_cols), dropna=False).agg(aggregations).reset_index()


def drop_columns(df: pd.DataFrame, columns_to_drop: Sequence[str]) -> pd.DataFrame:
	"""Return a copy of the dataframe without the specified columns."""
	return df.drop(columns=list(columns_to_drop)).copy()


def filter_data(
	df: pd.DataFrame,
	column: str,
	operator: str,
	value: object,
) -> pd.DataFrame:
	"""Filter rows using equality, numeric comparisons, or literal substring matching."""
	if operator == "==":
		mask = df[column] == value
	elif operator == ">":
		mask = df[column] > value
	elif operator == "<":
		mask = df[column] < value
	elif operator == "contains":
		mask = df[column].astype("string").str.contains(
			str(value), regex=False, na=False
		)
	else:
		raise ValueError(
			f"Unsupported operator {operator!r}; expected '==', '>', '<', or 'contains'"
		)
	return df.loc[mask].copy()


def transform_string(df: pd.DataFrame, column: str, method: str) -> pd.DataFrame:
	"""Return a copy with a text column lowercased, uppercased, or trimmed."""
	transformations = {
		"lower": lambda values: values.str.lower(),
		"upper": lambda values: values.str.upper(),
		"trim": lambda values: values.str.strip(),
	}
	if method not in transformations:
		raise ValueError("method must be 'lower', 'upper', or 'trim'")

	result = df.copy()
	result[column] = transformations[method](result[column].astype("string"))
	return result
