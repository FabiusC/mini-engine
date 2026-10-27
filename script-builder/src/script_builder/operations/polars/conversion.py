class PolarsConversionOperations:
	def _to_datetime(self, df, column, strict=True):
		value = pl.col(column)
		if df.schema[column] == pl.String:
			return value.str.to_datetime(strict=strict)
		return value.cast(pl.Datetime, strict=strict)

	def date(self, df, column, create_new_column=False, new_column_name=None):
		values = self._to_datetime(df, column).dt.date()
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def datetime(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, self._to_datetime(df, column),
			create_new_column, new_column_name,
		)

	def float(self, df, column, create_new_column=False, new_column_name=None):
		values = pl.col(column).cast(pl.Float64, strict=True)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def int(self, df, column, create_new_column=False, new_column_name=None):
		values = pl.col(column).cast(pl.Int64, strict=True)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def str(self, df, column, create_new_column=False, new_column_name=None):
		values = pl.col(column).cast(pl.String)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def make_date(
		self, df, column_day, column_month, column_year,
		create_new_column=True, new_column_name="date",
	):
		year = pl.col(column_year).cast(pl.Int32, strict=True)
		month = pl.col(column_month).cast(pl.Int32, strict=True)
		day = pl.col(column_day).cast(pl.Int32, strict=True)
		first = pl.datetime(year, month, 1)
		last_day = first.dt.month_end().dt.day()
		values = pl.datetime(year, month, day.clip(upper_bound=last_day))
		return self.assign_result(
			df, column_day, values, create_new_column, new_column_name,
		)

	def make_time(self, df, column_hour, column_minute, column_second, new_column_name="time"):
		values = pl.time(
			pl.col(column_hour).cast(pl.Int8, strict=True),
			pl.col(column_minute).cast(pl.Int8, strict=True),
			pl.col(column_second).cast(pl.Int8, strict=True),
		)
		return self.assign_result(df, column_hour, values, True, new_column_name)

	def make_date_time(self, df, column_date, column_hour, new_column_name="datetime"):
		date_value = self._to_datetime(df, column_date).dt.date().cast(pl.Datetime)
		time_value = pl.col(column_hour)
		if df.schema[column_hour] == pl.String:
			time_value = time_value.str.to_time(strict=True)
		else:
			time_value = time_value.cast(pl.Time, strict=True)
		values = date_value + pl.duration(
			hours=time_value.dt.hour(),
			minutes=time_value.dt.minute(),
			seconds=time_value.dt.second(),
			microseconds=time_value.dt.microsecond(),
		)
		return self.assign_result(df, column_date, values, True, new_column_name)
