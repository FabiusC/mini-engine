"""Numeric dataframe transformations."""

import numpy as np

import pandas as pd

from tableau_engine.functions.structural import StructuralProcessor
from tableau_engine.interfaces.numeric import NumericInterface


class NumericProcessor(NumericInterface):
	"""Stateless numeric operations for dataframe pipelines."""

	@staticmethod
	def absolute(
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with absolute values in the source or a new column."""
		result = df.copy()
		target = StructuralProcessor.resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		result[target] = pd.to_numeric(result[column], errors="raise").abs()
		return result

	@staticmethod
	def clean_float(
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Convert values to floats, replacing null or invalid values with zero."""
		result = df.copy()
		target = StructuralProcessor.resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		result[target] = (
			pd.to_numeric(result[column], errors="coerce")
			.fillna(0)
			.astype("float64")
		)
		return result

	@staticmethod
	def ceiling(
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with values rounded up in the source or a new column."""
		result = df.copy()
		target = StructuralProcessor.resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		numeric_values = pd.to_numeric(result[column], errors="raise")
		result[target] = np.ceil(numeric_values)
		return result

	@staticmethod
	def max(
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

	@staticmethod
	def min(
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

	@staticmethod
	def floor(
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with values rounded down in the source or a new column."""
		result = df.copy()
		target = StructuralProcessor.resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		numeric_values = pd.to_numeric(result[column], errors="raise")
		result[target] = np.floor(numeric_values)
		return result

	@staticmethod
	def power(
		df: pd.DataFrame,
		column: str,
		value: float,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Raise numeric values to ``value`` in the source or a new column."""
		result = df.copy()
		target = StructuralProcessor.resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		result[target] = pd.to_numeric(result[column], errors="raise").pow(value)
		return result

	@staticmethod
	def round_column(
		df: pd.DataFrame,
		column: str,
		decimals: int = 0,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with rounded values in the source or a new column."""
		result = df.copy()
		target = StructuralProcessor.resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		result[target] = pd.to_numeric(result[column], errors="raise").round(decimals)
		return result

	@staticmethod
	def arithmetic(
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
		return StructuralProcessor.assign_result(df, column_a, values, create_new_column, new_column_name)
