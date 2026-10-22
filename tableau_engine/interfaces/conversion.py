"""Abstract contracts for scalar and date/time conversions."""

from abc import ABC, abstractmethod

import pandas as pd


class ConversionInterface(ABC):
	"""Contract implemented by pandas conversion processors."""

	@staticmethod
	@abstractmethod
	def date(
		df: pd.DataFrame, column: str, replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def datetime(
		df: pd.DataFrame, column: str, replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def float(
		df: pd.DataFrame, column: str, replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def int(
		df: pd.DataFrame, column: str, replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def str(
		df: pd.DataFrame, column: str, replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def make_date(
		df: pd.DataFrame, column_day: str, column_month: str, column_year: str,
		replace: bool = False, new_column_name: str = "date",
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def make_time(
		df: pd.DataFrame, column_hour: str, column_minute: str,
		column_second: str, new_column_name: str = "time",
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def make_date_time(
		df: pd.DataFrame, column_date: str, column_hour: str,
		new_column_name: str = "datetime",
	) -> pd.DataFrame: ...
