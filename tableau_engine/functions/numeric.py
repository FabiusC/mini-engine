"""Numeric dataframe transformations."""

import math

import pandas as pd

from tableau_engine.functions.structural import resolve_output_column


def absolute(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with absolute values in the source or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	result[target] = pd.to_numeric(result[column], errors="raise").abs()
	return result


def clean_float(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Convert values to floats, replacing null or invalid values with zero."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	result[target] = (
		pd.to_numeric(result[column], errors="coerce")
		.fillna(0)
		.astype("float64")
	)
	return result


def ceiling(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with values rounded up in the source or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	numeric_values = pd.to_numeric(result[column], errors="raise")
	result[target] = numeric_values.map(
		lambda value: math.ceil(value) if pd.notna(value) else value
	)
	return result


def max(
	df: pd.DataFrame,
	column_a: str,
	column_b: str,
	new_column_name: str,
) -> pd.DataFrame:
	"""Add a column with the row-wise maximum of two numeric columns."""
	if column_a not in df.columns or column_b not in df.columns:
		missing = [column for column in (column_a, column_b) if column not in df.columns]
		raise ValueError(f"Columns {missing!r} are not present in the input")
	if not new_column_name:
		raise ValueError("new_column_name is required")
	if new_column_name in df.columns:
		raise ValueError(f"Column {new_column_name!r} already exists")
	values = pd.concat(
		[
			pd.to_numeric(df[column_a], errors="raise"),
			pd.to_numeric(df[column_b], errors="raise"),
		],
		axis=1,
	)
	result = df.copy()
	result[new_column_name] = values.max(axis=1)
	return result


def min(
	df: pd.DataFrame,
	column_a: str,
	column_b: str,
	new_column_name: str,
) -> pd.DataFrame:
	"""Add a column with the row-wise minimum of two numeric columns."""
	if column_a not in df.columns or column_b not in df.columns:
		missing = [column for column in (column_a, column_b) if column not in df.columns]
		raise ValueError(f"Columns {missing!r} are not present in the input")
	if not new_column_name:
		raise ValueError("new_column_name is required")
	if new_column_name in df.columns:
		raise ValueError(f"Column {new_column_name!r} already exists")
	values = pd.concat(
		[
			pd.to_numeric(df[column_a], errors="raise"),
			pd.to_numeric(df[column_b], errors="raise"),
		],
		axis=1,
	)
	result = df.copy()
	result[new_column_name] = values.min(axis=1)
	return result


def floor(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with values rounded down in the source or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	numeric_values = pd.to_numeric(result[column], errors="raise")
	result[target] = numeric_values.map(
		lambda value: math.floor(value) if pd.notna(value) else value
	)
	return result


def power(
	df: pd.DataFrame,
	column: str,
	value: float,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Raise numeric values to ``value`` in the source or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	result[target] = pd.to_numeric(result[column], errors="raise").pow(value)
	return result


def round_column(
	df: pd.DataFrame,
	column: str,
	decimals: int = 0,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with rounded values in the source or a new column."""
	result = df.copy()
	target = resolve_output_column(result, column, new_column, new_column_name)
	result[target] = pd.to_numeric(result[column], errors="raise").round(decimals)
	return result