"""Vectorized date and time transformations."""

import pandas as pd

from script_builder.operations.pandas.structural import StructuralOperations


class DateTimeOperations:
	"""Stateless datetime operations for dataframe pipelines."""

	_DATE_UNITS = {
		"day": "days",
		"days": "days",
		"week": "weeks",
		"weeks": "weeks",
		"month": "months",
		"months": "months",
		"quarter": "quarters",
		"quarters": "quarters",
		"year": "years",
		"years": "years",
		"hour": "hours",
		"hours": "hours",
		"minute": "minutes",
		"minutes": "minutes",
		"second": "seconds",
		"seconds": "seconds",
	}
	_MONTH_NAMES = (
		"enero", "febrero", "marzo", "abril", "mayo", "junio",
		"julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
	)
	_WEEKDAY_NAMES = (
		"lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
	)

	def _assign(
		self,
		df: pd.DataFrame,
		source: str,
		values: pd.Series,
		create_new_column: bool,
		new_column_name: str | None,
	) -> pd.DataFrame:
		if not isinstance(create_new_column, bool):
			raise ValueError("create_new_column must be a boolean")
		if create_new_column and not new_column_name:
			raise ValueError("new_column_name is required when create_new_column is true")
		if not create_new_column and new_column_name is not None:
			raise ValueError("new_column_name requires create_new_column to be true")
		return StructuralOperations().assign_result(
			df,
			source,
			values,
			create_new_column=create_new_column,
			new_column_name=new_column_name if create_new_column else None,
		)

	def date_parser(
		self,
		df: pd.DataFrame, column: str, date_format: str,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], format=date_format, errors="raise")
		return StructuralOperations().assign_result(df, column, values, create_new_column, new_column_name)

	def date_parse(
		self,
		df: pd.DataFrame,
		column: str,
		date_format: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Parse values matching a format; invalid values become NaT."""
		values = pd.to_datetime(df[column], format=date_format, errors="coerce")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def date_trunc(
		self,
		df: pd.DataFrame,
		column: str,
		part: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Truncate datetimes to the beginning of the requested calendar period."""
		values = pd.to_datetime(df[column], errors="coerce").dt.normalize()
		if part in ("year", "years"):
			truncated = values.map(lambda value: value.replace(month=1, day=1) if pd.notna(value) else pd.NaT)
		elif part in ("quarter", "quarters"):
			truncated = values.map(
				lambda value: value.replace(month=((value.month - 1) // 3) * 3 + 1, day=1)
				if pd.notna(value) else pd.NaT
			)
		elif part in ("month", "months"):
			truncated = values.map(lambda value: value.replace(day=1) if pd.notna(value) else pd.NaT)
		elif part in ("week", "weeks"):
			truncated = values.dt.normalize() - pd.to_timedelta(values.dt.dayofweek, unit="D")
		elif part in ("day", "days"):
			truncated = values.dt.normalize()
		elif part in ("hour", "hours"):
			truncated = values.dt.floor("h")
		elif part in ("minute", "minutes"):
			truncated = values.dt.floor("min")
		elif part in ("second", "seconds"):
			truncated = values.dt.floor("s")
		else:
			raise ValueError(
				"part must be one of year, quarter, month, week, day, hour, minute or second"
			)
		return self._assign(df, column, truncated, create_new_column, new_column_name)

	def day(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="coerce").dt.day.astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def iso_quarter(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return ISO-week-based quarter numbers, assigning week 53 to quarter 4."""
		weeks = pd.to_datetime(df[column], errors="coerce").dt.isocalendar().week
		values = (((weeks - 1) // 13) + 1).clip(upper=4).astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def iso_week(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="coerce").dt.isocalendar().week.astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def iso_week_day(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="coerce").dt.isocalendar().day.astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def iso_year(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="coerce").dt.isocalendar().year.astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def now(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.Series(pd.Timestamp.now().floor("s"), index=df.index)
		return self._assign(df, column, values, create_new_column, new_column_name)

	def quarter(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="coerce").dt.quarter.astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def today(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.Series(pd.Timestamp.today().normalize(), index=df.index)
		return self._assign(df, column, values, create_new_column, new_column_name)

	def week(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Return weekday numbers with Monday as 0 and Sunday as 6."""
		values = pd.to_datetime(df[column], errors="coerce").dt.dayofweek.astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def year(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="coerce").dt.year.astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def date_add(
		self,
		df: pd.DataFrame,
		column: str,
		unit: str | None = None,
		amount: int | None = None,
		create_new_column: bool = False, new_column_name: str | None = None,
		*,
		part: str | None = None,
		interval: int | None = None,
	) -> pd.DataFrame:
		"""Use calendar offsets for months/years, including month-end clipping."""
		if part is not None:
			if unit is not None and unit != part:
				raise ValueError("unit and part must agree")
			unit = part
		if interval is not None:
			if amount is not None and amount != interval:
				raise ValueError("amount and interval must agree")
			amount = interval
		if unit is None:
			raise ValueError("unit or part is required")
		if amount is None:
			raise ValueError("amount or interval is required")
		if isinstance(amount, bool) or not isinstance(amount, int):
			raise ValueError("amount must be an integer")
		normalized_unit = self._DATE_UNITS.get(unit.lower())
		if normalized_unit is None:
			raise ValueError(f"Unsupported date unit: {unit!r}")
		if normalized_unit == "quarters":
			normalized_unit = "months"
			amount *= 3
		values = pd.to_datetime(df[column], errors="raise") + pd.DateOffset(**{normalized_unit: amount})
		return StructuralOperations().assign_result(df, column, values, create_new_column, new_column_name)

	def date_sub(
		self,
		df: pd.DataFrame, column: str, unit: str, amount: int,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		if isinstance(amount, bool):
			raise ValueError("amount must be an integer")
		return self.date_add(df, column, unit, -amount, create_new_column, new_column_name)

	def date_diff(
		self,
		df: pd.DataFrame, start_column: str, end_column: str, unit: str = "days",
		create_new_column: bool = False, new_column_name: str | None = None,
		*, part: str | None = None,
	) -> pd.DataFrame:
		"""Return end minus start: elapsed days or signed complete calendar units."""
		if part is not None:
			if unit != "days" and unit != part:
				raise ValueError("unit and part must agree")
			unit = part
		start = pd.to_datetime(df[start_column], errors="raise")
		end = pd.to_datetime(df[end_column], errors="raise")
		normalized_unit = self._DATE_UNITS.get(unit.lower())
		if normalized_unit is None:
			raise ValueError(f"Unsupported date unit: {unit!r}")
		if normalized_unit == "quarters":
			normalized_unit = "months"
		if normalized_unit in ("days", "weeks", "hours", "minutes", "seconds"):
			values = (end - start).dt.total_seconds() / 86400
			divisors = {"days": 1, "weeks": 7, "hours": 1 / 24, "minutes": 1 / 1440, "seconds": 1 / 86400}
			values = values / divisors[normalized_unit]
		elif normalized_unit in ("months", "years"):
			negative = end < start
			early, late = start.where(~negative, end), end.where(~negative, start)
			months = (late.dt.year - early.dt.year) * 12 + late.dt.month - early.dt.month
			incomplete = (late.dt.day < early.dt.day) | (
				(late.dt.day == early.dt.day)
				& ((late - late.dt.normalize()) < (early - early.dt.normalize()))
			)
			values = months - incomplete.astype(int)
			if normalized_unit == "years":
				values = values // 12
			elif unit.lower() in ("quarter", "quarters"):
				values = values // 3
			values = values.where(~negative, -values).where(start.notna() & end.notna())
		return StructuralOperations().assign_result(df, start_column, values, create_new_column, new_column_name)

	def extract_date_part(
		self,
		df: pd.DataFrame, column: str, part: str,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		if part not in ("year", "month", "day", "weekday"):
			raise ValueError("part must be 'year', 'month', 'day' or 'weekday'")
		values = getattr(pd.to_datetime(df[column], errors="raise").dt, part)
		return StructuralOperations().assign_result(df, column, values, create_new_column, new_column_name)

	def month(
		self, df: pd.DataFrame, column: str, create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		values = pd.to_datetime(df[column], errors="coerce").dt.month.astype("Int64")
		return self._assign(df, column, values, create_new_column, new_column_name)

	def date_name(
		self,
		df: pd.DataFrame,
		column: str,
		part: str,
		create_new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame:
		dates = pd.to_datetime(df[column], errors="coerce")
		if part in ("month", "months"):
			month_numbers = dates.dt.month
			values = month_numbers.map(
				lambda number: self._MONTH_NAMES[int(number) - 1] if pd.notna(number) else pd.NA
			).astype("string")
		elif part in ("weekday", "week", "day"):
			weekday_numbers = dates.dt.dayofweek
			values = weekday_numbers.map(
				lambda number: self._WEEKDAY_NAMES[int(number)] if pd.notna(number) else pd.NA
			).astype("string")
		elif part in ("year", "years"):
			values = dates.dt.year.astype("Int64").astype("string")
		elif part in ("quarter", "quarters"):
			values = dates.dt.quarter.astype("Int64").astype("string")
		else:
			raise ValueError("part must be month, weekday, year or quarter")
		return self._assign(df, column, values, create_new_column, new_column_name)
