"""Abstract contracts for text dataframe transformations."""

from abc import ABC, abstractmethod

import pandas as pd


class TextInterface(ABC):
	"""Contract implemented by pandas text processors."""

	@staticmethod
	@abstractmethod
	def lowercase(
		df: pd.DataFrame, column: str, new_column: bool = False,
		new_column_name: str | None = None, *,
		create_new_column: bool | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def uppercase(
		df: pd.DataFrame, column: str, new_column: bool = False,
		new_column_name: str | None = None, *,
		create_new_column: bool | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def trim(
		df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None, *, side: str = "both",
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def ltrim(
		df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def rtrim(
		df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def substring(
		df: pd.DataFrame, column: str, start: int, length: int,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def replace(
		df: pd.DataFrame, column: str, old_text: str, new_text: str,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def split(
		df: pd.DataFrame, column: str, delimiter: str, index: int | None = None,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def concat(
		df: pd.DataFrame, columns: list[str], separator: str = "",
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...
