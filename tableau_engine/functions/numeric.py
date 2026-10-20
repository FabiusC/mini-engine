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