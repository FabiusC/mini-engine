"""Abstract contracts for numeric dataframe transformations."""

from abc import ABC, abstractmethod

import pandas as pd


class NumericInterface(ABC):
	"""Contract implemented by pandas numeric processors."""

	@staticmethod
	@abstractmethod
	def absolute(
		df: pd.DataFrame, column: str, new_column: bool = False,
		new_column_name: str | None = None, *,
		create_new_column: bool | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def clean_float(
		df: pd.DataFrame, column: str, new_column: bool = False,
		new_column_name: str | None = None, *,
		create_new_column: bool | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def ceiling(
		df: pd.DataFrame, column: str, new_column: bool = False,
		new_column_name: str | None = None, *,
		create_new_column: bool | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def floor(
		df: pd.DataFrame, column: str, new_column: bool = False,
		new_column_name: str | None = None, *,
		create_new_column: bool | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def max(
		df: pd.DataFrame, column_a: str, column_b: str, new_column_name: str,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def min(
		df: pd.DataFrame, column_a: str, column_b: str, new_column_name: str,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def power(
		df: pd.DataFrame, column: str, value: float, new_column: bool = False,
		new_column_name: str | None = None, *,
		create_new_column: bool | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def round_column(
		df: pd.DataFrame, column: str, decimals: int = 0,
		new_column: bool = False, new_column_name: str | None = None, *,
		create_new_column: bool | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def arithmetic(
		df: pd.DataFrame, column_a: str, operator: str,
		column_b_or_value: str | float, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...
