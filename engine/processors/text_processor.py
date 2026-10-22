"""Text dataframe transformations."""

import pandas as pd

from engine.processors.structural_processor import StructuralProcessor


class TextProcessor:
	"""Stateless text operations for dataframe pipelines."""

	@staticmethod
	def lowercase(
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with lowercase text in the source column or a new column."""
		result = df.copy()
		target = StructuralProcessor.resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		result[target] = result[column].astype("string").str.lower()
		return result

	@staticmethod
	def uppercase(
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with uppercase text in the source column or a new column."""
		result = df.copy()
		target = StructuralProcessor.resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		result[target] = result[column].astype("string").str.upper()
		return result

	@staticmethod
	def trim(
		df: pd.DataFrame,
		column: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
		*,
		side: str = "both",
	) -> pd.DataFrame:
		"""Strip whitespace on either side, preserving missing values."""
		values = df[column].astype("string")
		if side == "both":
			values = values.str.strip()
		elif side == "left":
			values = values.str.lstrip()
		elif side == "right":
			values = values.str.rstrip()
		else:
			raise ValueError("side must be 'both', 'left' or 'right'")
		return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)

	@staticmethod
	def ltrim(
		df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		return TextProcessor.trim(df, column, create_new_column, new_column_name, side="left")

	@staticmethod
	def rtrim(
		df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		return TextProcessor.trim(df, column, create_new_column, new_column_name, side="right")

	@staticmethod
	def substring(
		df: pd.DataFrame, column: str, start: int, length: int,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Slice using zero-based pandas string offsets."""
		if length < 0:
			raise ValueError("length must be nonnegative")
		values = df[column].astype("string").str.slice(start, None)
		values = values.str.slice(0, length)
		return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)

	@staticmethod
	def replace(
		df: pd.DataFrame, column: str, old_text: str, new_text: str,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = df[column].astype("string").str.replace(old_text, new_text, regex=False)
		return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)

	@staticmethod
	def split(
		df: pd.DataFrame, column: str, delimiter: str, index: int | None = None,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Select one token, or expand all tokens into new columns."""
		if not delimiter:
			raise ValueError("delimiter must not be empty")
		if index is not None:
			values = df[column].astype("string").str.split(delimiter, regex=False).str.get(index)
			return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)
		if not create_new_column:
			raise ValueError("split without index requires create_new_column=true")
		base = StructuralProcessor.resolve_output_column(
			df, column, new_column_name=new_column_name, create_new_column=True
		)
		parts = df[column].astype("string").str.split(delimiter, regex=False, expand=True)
		names = [f"{base}_{i}" for i in range(len(parts.columns))]
		if any(name in df.columns for name in names):
			raise ValueError("split output columns already exist")
		result = df.copy()
		parts.columns = names
		return pd.concat([result, parts], axis=1)

	@staticmethod
	def concat(
		df: pd.DataFrame, columns: list[str], separator: str = "",
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Concatenate columns; missing inputs propagate to the result."""
		if not columns:
			raise ValueError("columns must not be empty")
		values = df[columns[0]].astype("string")
		for column in columns[1:]:
			values = values.str.cat(df[column].astype("string"), sep=separator)
		return StructuralProcessor.assign_result(df, columns[0], values, create_new_column, new_column_name)
