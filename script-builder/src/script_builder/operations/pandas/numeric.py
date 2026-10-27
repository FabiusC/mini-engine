"""Numeric dataframe transformations."""

import numpy as np

import pandas as pd

from script_builder.operations.pandas.structural import StructuralOperations


class NumericOperations:
	"""Stateless numeric operations for dataframe pipelines."""

	def absolute(
		self,
		df: pd.DataFrame,
		column: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return a copy with absolute values in the source or a new column."""
		result = df.copy()
		target = StructuralOperations().resolve_output_column(
			result, column, create_new_column, new_column_name
		)
		result[target] = pd.to_numeric(result[column], errors="raise").abs()
		return result

	def clean_float(
		self,
		df: pd.DataFrame,
		column: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Convert values to floats, replacing null or invalid values with zero."""
		result = df.copy()
		target = StructuralOperations().resolve_output_column(
			result, column, create_new_column, new_column_name
		)
		result[target] = (
			pd.to_numeric(result[column], errors="coerce")
			.fillna(0)
			.astype("float64")
		)
		return result

	def ceiling(
		self,
		df: pd.DataFrame,
		column: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return a copy with values rounded up in the source or a new column."""
		result = df.copy()
		target = StructuralOperations().resolve_output_column(
			result, column, create_new_column, new_column_name
		)
		numeric_values = pd.to_numeric(result[column], errors="raise")
		result[target] = np.ceil(numeric_values)
		return result

	def max(
		self,
		df: pd.DataFrame,
		column_a: str,
		column_b: str,
		new_column_name: str,
	) -> pd.DataFrame:
		"""Add a column with the row-wise maximum of two numeric columns."""
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
		self,
		df: pd.DataFrame,
		column_a: str,
		column_b: str,
		new_column_name: str,
	) -> pd.DataFrame:
		"""Add a column with the row-wise minimum of two numeric columns."""
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
		self,
		df: pd.DataFrame,
		column: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return a copy with values rounded down in the source or a new column."""
		result = df.copy()
		target = StructuralOperations().resolve_output_column(
			result, column, create_new_column, new_column_name
		)
		numeric_values = pd.to_numeric(result[column], errors="raise")
		result[target] = np.floor(numeric_values)
		return result

	def power(
		self,
		df: pd.DataFrame,
		column: str,
		value: float,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Raise numeric values to ``value`` in the source or a new column."""
		result = df.copy()
		target = StructuralOperations().resolve_output_column(
			result, column, create_new_column, new_column_name
		)
		result[target] = pd.to_numeric(result[column], errors="raise").pow(value)
		return result

	def round_column(
		self,
		df: pd.DataFrame,
		column: str,
		decimals: int = 0,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return a copy with rounded values in the source or a new column."""
		result = df.copy()
		target = StructuralOperations().resolve_output_column(
			result, column, create_new_column, new_column_name
		)
		result[target] = pd.to_numeric(result[column], errors="raise").round(decimals)
		return result

	def arithmetic(
		self,
		df: pd.DataFrame, column_a: str, operator: str, column_b_or_value: str | float,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Apply vectorized arithmetic with a column or a numeric constant."""
		left = pd.to_numeric(df[column_a], errors="raise")
		right = (
			pd.to_numeric(df[column_b_or_value], errors="raise")
			if isinstance(column_b_or_value, str) else column_b_or_value
		)
		if operator == "+":
			values = left.add(right)
		elif operator == "-":
			values = left.sub(right)
		elif operator == "*":
			values = left.mul(right)
		elif operator == "/":
			zero_divisor = (right == 0).any() if isinstance(right, pd.Series) else right == 0
			if zero_divisor:
				raise ValueError("Division by zero")
			values = left.div(right)
		else:
			raise ValueError(f"Unsupported arithmetic operator: {operator!r}")
		return StructuralOperations().assign_result(df, column_a, values, create_new_column, new_column_name)
