"""Vectorized date and time transformations."""

import pandas as pd

from engine.processors.structural_processor import StructuralProcessor
from engine.interfaces.date_interface import DateTimeInterface


class DateTimeProcessor(DateTimeInterface):
	"""Stateless datetime operations for dataframe pipelines."""

	@staticmethod
	def date_parser(
		df: pd.DataFrame, column: str, date_format: str,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], format=date_format, errors="raise")
		return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)

	@staticmethod
	def date_add(
		df: pd.DataFrame, column: str, unit: str, amount: int,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Use calendar offsets for months/years, including month-end clipping."""
		if unit not in ("days", "months", "years"):
			raise ValueError("unit must be 'days', 'months' or 'years'")
		if isinstance(amount, bool) or not isinstance(amount, int):
			raise ValueError("amount must be an integer")
		values = pd.to_datetime(df[column], errors="raise") + pd.DateOffset(**{unit: amount})
		return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)

	@staticmethod
	def date_sub(
		df: pd.DataFrame, column: str, unit: str, amount: int,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		if isinstance(amount, bool):
			raise ValueError("amount must be an integer")
		return DateTimeProcessor.date_add(df, column, unit, -amount, create_new_column, new_column_name)

	@staticmethod
	def date_diff(
		df: pd.DataFrame, start_column: str, end_column: str, unit: str = "days",
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return end minus start: elapsed days or signed complete calendar units."""
		start = pd.to_datetime(df[start_column], errors="raise")
		end = pd.to_datetime(df[end_column], errors="raise")
		if unit == "days":
			values = (end - start).dt.total_seconds() / 86400
		elif unit in ("months", "years"):
			negative = end < start
			early, late = start.where(~negative, end), end.where(~negative, start)
			months = (late.dt.year - early.dt.year) * 12 + late.dt.month - early.dt.month
			incomplete = (late.dt.day < early.dt.day) | (
				(late.dt.day == early.dt.day)
				& ((late - late.dt.normalize()) < (early - early.dt.normalize()))
			)
			values = months - incomplete.astype(int)
			if unit == "years":
				values = values // 12
			values = values.where(~negative, -values).where(start.notna() & end.notna())
		else:
			raise ValueError("unit must be 'days', 'months' or 'years'")
		return StructuralProcessor.assign_result(df, start_column, values, create_new_column, new_column_name)

	@staticmethod
	def extract_date_part(
		df: pd.DataFrame, column: str, part: str,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		if part not in ("year", "month", "day", "weekday"):
			raise ValueError("part must be 'year', 'month', 'day' or 'weekday'")
		values = getattr(pd.to_datetime(df[column], errors="raise").dt, part)
		return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)
