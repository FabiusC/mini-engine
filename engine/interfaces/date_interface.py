"""Abstract contracts for calendar transformations."""

from abc import ABC, abstractmethod

import pandas as pd


class DateTimeInterface(ABC):
	"""Contract implemented by pandas date and time processors."""

	@staticmethod
	@abstractmethod
	def date_parser(
		df: pd.DataFrame, column: str, date_format: str,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def date_add(
		df: pd.DataFrame, column: str, unit: str, amount: int,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def date_sub(
		df: pd.DataFrame, column: str, unit: str, amount: int,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def date_diff(
		df: pd.DataFrame, start_column: str, end_column: str, unit: str = "days",
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def extract_date_part(
		df: pd.DataFrame, column: str, part: str,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...
