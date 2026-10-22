"""Pandas conversions for scalar and composed date/time values."""

from datetime import time

import pandas as pd

from engine.processors.structural_processor import StructuralProcessor


class ConversionProcessor:
	"""Stateless dataframe conversions."""

	def _assign(
		self,
		df: pd.DataFrame,
		source: str,
		values: pd.Series,
		replace: bool,
		new_column_name: str | None,
	) -> pd.DataFrame:
		if not isinstance(replace, bool):
			raise ValueError("replace must be a boolean")
		if replace and new_column_name is not None:
			raise ValueError("new_column_name requires replace to be false")
		if not replace and not new_column_name:
			raise ValueError("new_column_name is required when replace is false")
		return StructuralProcessor().assign_result(
			df, source, values, create_new_column=not replace,
			new_column_name=new_column_name if not replace else None,
		)

	def _integer_parts(self, df: pd.DataFrame, columns: tuple[str, ...]) -> dict[str, pd.Series]:
		parts = {}
		for name in columns:
			values = pd.to_numeric(df[name], errors="raise")
			if ((values.dropna() % 1) != 0).any():
				raise ValueError(f"{name} values must be integers")
			parts[name] = values.astype("Int64")
		return parts

	def date(
		self,
		df: pd.DataFrame,
		column: str,
		replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="raise").dt.normalize()
		return self._assign(df, column, values, replace, new_column_name)

	def datetime(
		self,
		df: pd.DataFrame,
		column: str,
		replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="raise")
		return self._assign(df, column, values, replace, new_column_name)

	def float(
		self,
		df: pd.DataFrame,
		column: str,
		replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_numeric(df[column], errors="raise").astype("float64")
		return self._assign(df, column, values, replace, new_column_name)

	def int(
		self,
		df: pd.DataFrame,
		column: str,
		replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_numeric(df[column], errors="raise").astype("Int64")
		return self._assign(df, column, values, replace, new_column_name)

	def str(
		self,
		df: pd.DataFrame,
		column: str,
		replace: bool = True,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = df[column].astype("string")
		return self._assign(df, column, values, replace, new_column_name)

	def make_date(
		self,
		df: pd.DataFrame,
		column_day: str,
		column_month: str,
		column_year: str,
		replace: bool = False,
		new_column_name: str = "date",
	) -> pd.DataFrame:
		parts = self._integer_parts(
			df, (column_year, column_month, column_day),
		)
		month = parts[column_month]
		if ((month.dropna() < 1) | (month.dropna() > 12)).any():
			raise ValueError("month values must be between 1 and 12")
		day = parts[column_day]
		if (day.dropna() < 1).any():
			raise ValueError("day values must be 1 or greater")

		components = pd.DataFrame({
			"year": parts[column_year],
			"month": month,
			"day": day,
		}, index=df.index)
		month_lengths = pd.to_datetime(
			components.assign(day=1), errors="raise",
		).dt.days_in_month
		components["day"] = components["day"].where(
			components["day"].isna(),
			components["day"].clip(upper=month_lengths),
		)
		values = pd.to_datetime(components, errors="raise")
		if replace:
			return self._assign(df, column_day, values, True, None)
		return self._assign(df, column_day, values, False, new_column_name)

	def make_time(
		self,
		df: pd.DataFrame,
		column_hour: str,
		column_minute: str,
		column_second: str,
		new_column_name: str = "time",
	) -> pd.DataFrame:
		parts = self._integer_parts(
			df, (column_hour, column_minute, column_second),
		)
		for column, maximum in ((column_hour, 23), (column_minute, 59), (column_second, 59)):
			values = parts[column].dropna()
			if ((values < 0) | (values > maximum)).any():
				raise ValueError(f"{column} values must be between 0 and {maximum}")
		datetimes = pd.to_datetime({
			"year": pd.Series(2000, index=df.index),
			"month": pd.Series(1, index=df.index),
			"day": pd.Series(1, index=df.index),
			"hour": parts[column_hour],
			"minute": parts[column_minute],
			"second": parts[column_second],
		}, errors="raise")
		values = datetimes.dt.time
		return self._assign(
			df, column_hour, values, False, new_column_name,
		)

	def make_date_time(
		self,
		df: pd.DataFrame,
		column_date: str,
		column_hour: str,
		new_column_name: str = "datetime",
	) -> pd.DataFrame:
		dates = pd.to_datetime(df[column_date], errors="raise").dt.normalize()
		hour_values = df[column_hour]
		if hour_values.map(lambda value: pd.isna(value) or isinstance(value, time)).all():
			times = pd.Series(
				[
					pd.Timedelta(
						hours=value.hour,
						minutes=value.minute,
						seconds=value.second,
						microseconds=value.microsecond,
					) if isinstance(value, time) else pd.NaT
					for value in hour_values
				],
				index=df.index,
			)
		else:
			times = pd.to_timedelta(hour_values.astype("string"), errors="raise")
		if ((times.dropna() < pd.Timedelta(0)) | (times.dropna() >= pd.Timedelta(days=1))).any():
			raise ValueError("time values must be within a single day")
		values = dates + times
		return self._assign(
			df, column_date, values, False, new_column_name,
		)
