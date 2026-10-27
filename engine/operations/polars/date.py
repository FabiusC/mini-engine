from datetime import date, datetime


class PolarsDateOperations:
	_DATE_UNITS = {
		"day": "d", "days": "d",
		"week": "w", "weeks": "w",
		"month": "mo", "months": "mo",
		"quarter": "mo", "quarters": "mo",
		"year": "y", "years": "y",
		"hour": "h", "hours": "h",
		"minute": "m", "minutes": "m",
		"second": "s", "seconds": "s",
	}
	_MONTH_NAMES = (
		"enero", "febrero", "marzo", "abril", "mayo", "junio",
		"julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
	)
	_WEEKDAY_NAMES = (
		"lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
	)

	def _to_datetime(self, df, column, strict=True):
		value = pl.col(column)
		return (
			value.str.to_datetime(strict=strict)
			if df.schema[column] == pl.String
			else value.cast(pl.Datetime, strict=strict)
		)

	def date_parser(self, df, column, date_format, create_new_column=False, new_column_name=None):
		values = pl.col(column).str.strptime(pl.Datetime, format=date_format, strict=True)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def date_parse(self, df, column, date_format, create_new_column=False, new_column_name=None):
		values = pl.col(column).str.strptime(pl.Datetime, format=date_format, strict=False)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def date_trunc(self, df, column, part, create_new_column=False, new_column_name=None):
		value = self._to_datetime(df, column, strict=False)
		if part in ("year", "years"):
			values = pl.datetime(value.dt.year(), 1, 1)
		elif part in ("quarter", "quarters"):
			month = ((value.dt.month() - 1) // 3) * 3 + 1
			values = pl.datetime(value.dt.year(), month, 1)
		elif part in ("month", "months"):
			values = pl.datetime(value.dt.year(), value.dt.month(), 1)
		elif part in ("week", "weeks"):
			values = value.dt.truncate("1w")
		elif part in ("day", "days"):
			values = value.dt.truncate("1d")
		elif part in ("hour", "hours"):
			values = value.dt.truncate("1h")
		elif part in ("minute", "minutes"):
			values = value.dt.truncate("1m")
		elif part in ("second", "seconds"):
			values = value.dt.truncate("1s")
		else:
			raise ValueError("part must be one of year, quarter, month, week, day, hour, minute or second")
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def day(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column, strict=False).dt.day()
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def iso_quarter(self, df, column, create_new_column=False, new_column_name=None):
		week = self._to_datetime(df, column, strict=False).dt.week()
		values = (((week - 1) // 13) + 1).clip(upper_bound=4)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def iso_week(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column, strict=False).dt.week()
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def iso_week_day(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column, strict=False).dt.weekday()
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def iso_year(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column, strict=False).dt.iso_year()
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def now(self, df, column, create_new_column=False, new_column_name=None):
		value = datetime.now().replace(microsecond=0)
		return self.assign_result(df, column, pl.lit(value), create_new_column, new_column_name)

	def quarter(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column, strict=False).dt.quarter()
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def today(self, df, column, create_new_column=False, new_column_name=None):
		value = datetime.combine(date.today(), datetime.min.time())
		return self.assign_result(df, column, pl.lit(value), create_new_column, new_column_name)

	def week(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column, strict=False).dt.weekday() - 1
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def year(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column, strict=False).dt.year()
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def date_add(
		self, df, column, unit=None, amount=None, create_new_column=False,
		new_column_name=None, *, part=None, interval=None,
	):
		if part is not None:
			if unit is not None and unit != part:
				raise ValueError("unit and part must agree")
			unit = part
		if interval is not None:
			if amount is not None and amount != interval:
				raise ValueError("amount and interval must agree")
			amount = interval
		if unit is None or amount is None:
			raise ValueError("unit/part and amount/interval are required")
		if isinstance(amount, bool) or not isinstance(amount, int):
			raise ValueError("amount must be an integer")
		offset_unit = self._DATE_UNITS.get(unit.lower())
		if offset_unit is None:
			raise ValueError(f"Unsupported date unit: {unit!r}")
		if offset_unit == "mo" and unit.lower() in ("quarter", "quarters"):
			amount *= 3
		value = self._to_datetime(df, column)
		values = value.dt.offset_by(f"{amount}{offset_unit}")
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def date_sub(self, df, column, unit, amount, create_new_column=False, new_column_name=None):
		if isinstance(amount, bool) or not isinstance(amount, int):
			raise ValueError("amount must be an integer")
		return self.date_add(df, column, unit, -amount, create_new_column, new_column_name)

	def date_diff(
		self, df, start_column, end_column, unit="days",
		create_new_column=False, new_column_name=None, *, part=None,
	):
		if part is not None:
			if unit != "days" and unit != part:
				raise ValueError("unit and part must agree")
			unit = part
		normalized = self._DATE_UNITS.get(unit.lower())
		if normalized is None:
			raise ValueError(f"Unsupported date unit: {unit!r}")
		start = self._to_datetime(df, start_column)
		end = self._to_datetime(df, end_column)
		duration = end - start
		if normalized in ("d", "w", "h", "m", "s"):
			divisor = {"d": 86400, "w": 604800, "h": 3600, "m": 60, "s": 1}[normalized]
			values = duration.dt.total_seconds() / divisor
		else:
			negative = end < start
			early = pl.when(negative).then(end).otherwise(start)
			late = pl.when(negative).then(start).otherwise(end)
			months = (
				(late.dt.year() - early.dt.year()) * 12
				+ late.dt.month() - early.dt.month()
			)
			early_time = (
				early.dt.hour() * 3600000000 + early.dt.minute() * 60000000
				+ early.dt.second() * 1000000 + early.dt.microsecond()
			)
			late_time = (
				late.dt.hour() * 3600000000 + late.dt.minute() * 60000000
				+ late.dt.second() * 1000000 + late.dt.microsecond()
			)
			incomplete = (late.dt.day() < early.dt.day()) | (
				(late.dt.day() == early.dt.day()) & (late_time < early_time)
			)
			count = months - incomplete.cast(pl.Int32)
			if normalized == "y":
				count = count // 12
			elif unit.lower() in ("quarter", "quarters"):
				count = count // 3
			values = pl.when(negative).then(-count).otherwise(count)
		return self.assign_result(
			df, start_column, values, create_new_column, new_column_name,
		)

	def extract_date_part(self, df, column, part, create_new_column=False, new_column_name=None):
		value = self._to_datetime(df, column)
		parts = {
			"year": value.dt.year(),
			"month": value.dt.month(),
			"day": value.dt.day(),
			"weekday": value.dt.weekday() - 1,
		}
		try:
			values = parts[part]
		except KeyError as error:
			raise ValueError("part must be 'year', 'month', 'day' or 'weekday'") from error
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def month(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column, strict=False).dt.month()
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def date_name(self, df, column, part, create_new_column=False, new_column_name=None):
		dates = self._to_datetime(df, column, strict=False)
		if part in ("month", "months"):
			values = dates.dt.month().replace_strict(
				{index: name for index, name in enumerate(self._MONTH_NAMES, 1)},
				default=None,
			)
		elif part in ("weekday", "week", "day"):
			values = (dates.dt.weekday() - 1).replace_strict(
				{index: name for index, name in enumerate(self._WEEKDAY_NAMES)},
				default=None,
			)
		elif part in ("year", "years"):
			values = dates.dt.year().cast(pl.String)
		elif part in ("quarter", "quarters"):
			values = dates.dt.quarter().cast(pl.String)
		else:
			raise ValueError("part must be month, weekday, year or quarter")
		return self.assign_result(df, column, values, create_new_column, new_column_name)
