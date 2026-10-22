"""Text dataframe transformations."""

import pandas as pd

from engine.processors.structural_processor import StructuralProcessor


class TextProcessor:
	"""Stateless text operations for dataframe pipelines."""

	def lowercase(
		self,
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with lowercase text in the source column or a new column."""
		result = df.copy()
		target = StructuralProcessor().resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		result[target] = result[column].astype("string").str.lower()
		return result

	def uppercase(
		self,
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with uppercase text in the source column or a new column."""
		result = df.copy()
		target = StructuralProcessor().resolve_output_column(
			result, column, new_column, new_column_name, create_new_column=create_new_column
		)
		result[target] = result[column].astype("string").str.upper()
		return result

	def proper(
		self,
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Return a copy with each word capitalized in the source or a new column."""
		result = df.copy()
		target = StructuralProcessor().resolve_output_column(
			result, column, new_column, new_column_name,
			create_new_column=create_new_column,
		)
		result[target] = result[column].astype("string").str.title()
		return result

	def propper(
		self,
		df: pd.DataFrame,
		column: str,
		new_column: bool = False,
		new_column_name: str | None = None,
		*,
		create_new_column: bool | None = None,
	) -> pd.DataFrame:
		"""Alias of ``proper`` using the operation name from the pipeline specification."""
		return self.proper(
			df, column, new_column, new_column_name,
			create_new_column=create_new_column,
		)

	def trim(
		self,
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
		return StructuralProcessor().assign_result(df, column, values, create_new_column, new_column_name)

	def ltrim(
		self,
		df: pd.DataFrame, 
		column: str, 
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		return self.trim(df, column, create_new_column, new_column_name, side="left")

	def rtrim(
		self,
		df: pd.DataFrame, 
		column: str, 
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		return self.trim(df, column, create_new_column, new_column_name, side="right")

	def substring(
		self,
		df: pd.DataFrame, 
		column: str, 
		start: int, 
		length: int,
		create_new_column: bool = False, 
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Slice using zero-based pandas string offsets."""
		if length < 0:
			raise ValueError("length must be nonnegative")
		values = df[column].astype("string").str.slice(start, None)
		values = values.str.slice(0, length)
		return StructuralProcessor().assign_result(df, column, values, create_new_column, new_column_name)

	def replace(
		self,
		df: pd.DataFrame, 
		column: str, 
		old_text: str, 
		new_text: str,
		create_new_column: bool = False, 
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = df[column].astype("string").str.replace(old_text, new_text, regex=False)
		return StructuralProcessor().assign_result(df, column, values, create_new_column, new_column_name)

	def split(
		self,
		df: pd.DataFrame, 
		column: str, 
		delimiter: str, 
		index: int | None = None,
		create_new_column: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Select one token, or expand all tokens into new columns."""
		if not delimiter:
			raise ValueError("delimiter must not be empty")
		if index is not None:
			values = df[column].astype("string").str.split(delimiter, regex=False).str.get(index)
			return StructuralProcessor().assign_result(df, column, values, create_new_column, new_column_name)
		if not create_new_column:
			raise ValueError("split without index requires create_new_column=true")
		base = StructuralProcessor().resolve_output_column(
			df, column, new_column_name=new_column_name, create_new_column=True
		)
		parts = df[column].astype("string").str.split(delimiter, regex=False, expand=True)
		names = [f"{base}_{i}" for i in range(len(parts.columns))]
		if any(name in df.columns for name in names):
			raise ValueError("split output columns already exist")
		result = df.copy()
		parts.columns = names
		return pd.concat([result, parts], axis=1)

	def concat_column(
		self,
		df: pd.DataFrame, 
		columns: list[str], 
		separator: str = "",
		create_new_column: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Concatenate selected columns into a new column by default."""
		if not columns:
			raise ValueError("columns must not be empty")
		values = df[columns[0]].astype("string")
		for column in columns[1:]:
			values = values.str.cat(df[column].astype("string"), sep=separator)
		return StructuralProcessor().assign_result(df, columns[0], values, create_new_column, new_column_name)

	def concat_text(
		self,
		df: pd.DataFrame,
		column_name: str,
		value: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Append literal text to a column, replacing it by default."""
		if not isinstance(value, str):
			raise ValueError("value must be a string")
		values = df[column_name].astype("string") + value
		return StructuralProcessor().assign_result(
			df, column_name, values, create_new_column, new_column_name,
		)

	def contains(
		self,
		df: pd.DataFrame,
		column: str,
		search_text: str,
		create_new_column: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return whether each non-null value contains the literal search text."""
		if not isinstance(search_text, str):
			raise ValueError("search_text must be a string")
		values = df[column].astype("string").str.contains(
			search_text, regex=False, na=False,
		)
		return StructuralProcessor().assign_result(
			df, column, values.astype(bool), create_new_column, new_column_name,
		)

	def starts_with(
		self,
		df: pd.DataFrame,
		column: str,
		search_text: str,
		create_new_column: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return whether each non-null value starts with the literal search text."""
		if not isinstance(search_text, str):
			raise ValueError("search_text must be a string")
		values = df[column].astype("string").str.startswith(search_text, na=False)
		return StructuralProcessor().assign_result(
			df, column, values.astype(bool), create_new_column, new_column_name,
		)

	def ends_with(
		self,
		df: pd.DataFrame,
		column: str,
		search_text: str,
		create_new_column: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return whether each non-null value ends with the literal search text."""
		if not isinstance(search_text, str):
			raise ValueError("search_text must be a string")
		values = df[column].astype("string").str.endswith(search_text, na=False)
		return StructuralProcessor().assign_result(
			df, column, values.astype(bool), create_new_column, new_column_name,
		)

	def transform_left(
		self,
		df: pd.DataFrame,
		column: str,
		limit: int,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Keep up to ``limit`` characters from the beginning of each value."""
		if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
			raise ValueError("limit must be a nonnegative integer")
		values = df[column].astype("string").str.slice(0, limit)
		return StructuralProcessor().assign_result(
			df, column, values, create_new_column, new_column_name,
		)

	def transform_right(
		self,
		df: pd.DataFrame,
		column: str,
		limit: int,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Keep up to ``limit`` characters from the end of each value."""
		if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
			raise ValueError("limit must be a nonnegative integer")
		text = df[column].astype("string")
		values = text.str.slice(-limit, None) if limit else text.str.slice(0, 0)
		return StructuralProcessor().assign_result(
			df, column, values, create_new_column, new_column_name,
		)

	def length(
		self,
		df: pd.DataFrame,
		column: str,
		create_new_column: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return the character count for each value, preserving nulls."""
		values = df[column].astype("string").str.len().astype("Int64")
		return StructuralProcessor().assign_result(
			df, column, values, create_new_column, new_column_name,
		)