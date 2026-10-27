class PolarsTextOperations:
	def lowercase(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.String).str.to_lowercase(),
			create_new_column, new_column_name,
		)

	def uppercase(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.String).str.to_uppercase(),
			create_new_column, new_column_name,
		)

	def proper(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.String).str.to_titlecase(),
			create_new_column, new_column_name,
		)

	def propper(self, df, column, create_new_column=False, new_column_name=None):
		return self.proper(df, column, create_new_column, new_column_name)

	def trim(self, df, column, create_new_column=False, new_column_name=None, *, side="both"):
		value = pl.col(column).cast(pl.String)
		if side == "both":
			value = value.str.strip_chars()
		elif side == "left":
			value = value.str.strip_chars_start()
		elif side == "right":
			value = value.str.strip_chars_end()
		else:
			raise ValueError("side must be 'both', 'left' or 'right'")
		return self.assign_result(df, column, value, create_new_column, new_column_name)

	def ltrim(self, df, column, create_new_column=False, new_column_name=None):
		return self.trim(df, column, create_new_column, new_column_name, side="left")

	def rtrim(self, df, column, create_new_column=False, new_column_name=None):
		return self.trim(df, column, create_new_column, new_column_name, side="right")

	def substring(self, df, column, start, length, create_new_column=False, new_column_name=None):
		if length < 0:
			raise ValueError("length must be nonnegative")
		return self.assign_result(
			df, column, pl.col(column).cast(pl.String).str.slice(start, length),
			create_new_column, new_column_name,
		)

	def replace(self, df, column, old_text, new_text, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column,
			pl.col(column).cast(pl.String).str.replace_all(old_text, new_text, literal=True),
			create_new_column, new_column_name,
		)

	def split(self, df, column, delimiter, index=None, create_new_column=True, new_column_name=None):
		if not delimiter:
			raise ValueError("delimiter must not be empty")
		tokens = pl.col(column).cast(pl.String).str.split(delimiter)
		if index is not None:
			return self.assign_result(
				df, column, tokens.list.get(index, null_on_oob=True),
				create_new_column, new_column_name,
			)
		if not create_new_column:
			raise ValueError("split without index requires create_new_column=true")
		base = self.resolve_output_column(df, column, True, new_column_name)
		count = df.select(tokens.list.len().max()).item() or 0
		names = [f"{base}_{index}" for index in range(count)]
		if any(name in df.columns for name in names):
			raise ValueError("split output columns already exist")
		return df.with_columns([
			tokens.list.get(index, null_on_oob=True).alias(name)
			for index, name in enumerate(names)
		])

	def concat_column(self, df, columns, separator="", create_new_column=True, new_column_name=None):
		if not columns:
			raise ValueError("columns must not be empty")
		values = pl.concat_str(
			[pl.col(column).cast(pl.String) for column in columns],
			separator=separator,
			ignore_nulls=False,
		)
		return self.assign_result(df, columns[0], values, create_new_column, new_column_name)

	def concat_text(self, df, column_name, value, create_new_column=False, new_column_name=None):
		if not isinstance(value, str):
			raise ValueError("value must be a string")
		return self.assign_result(
			df, column_name, pl.col(column_name).cast(pl.String) + value,
			create_new_column, new_column_name,
		)

	def contains(self, df, column, search_text, create_new_column=True, new_column_name=None):
		if not isinstance(search_text, str):
			raise ValueError("search_text must be a string")
		values = pl.col(column).cast(pl.String).str.contains(search_text, literal=True).fill_null(False)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def starts_with(self, df, column, search_text, create_new_column=True, new_column_name=None):
		if not isinstance(search_text, str):
			raise ValueError("search_text must be a string")
		values = pl.col(column).cast(pl.String).str.starts_with(search_text).fill_null(False)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def ends_with(self, df, column, search_text, create_new_column=True, new_column_name=None):
		if not isinstance(search_text, str):
			raise ValueError("search_text must be a string")
		values = pl.col(column).cast(pl.String).str.ends_with(search_text).fill_null(False)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def transform_left(self, df, column, limit, create_new_column=False, new_column_name=None):
		if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
			raise ValueError("limit must be a nonnegative integer")
		values = pl.col(column).cast(pl.String).str.slice(0, limit)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def transform_right(self, df, column, limit, create_new_column=False, new_column_name=None):
		if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
			raise ValueError("limit must be a nonnegative integer")
		values = pl.col(column).cast(pl.String).str.slice(-limit) if limit else pl.lit("")
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def length(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.String).str.len_chars(),
			create_new_column, new_column_name,
		)
