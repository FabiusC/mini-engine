class PolarsNumericOperations:
	def absolute(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.Float64, strict=True).abs(),
			create_new_column, new_column_name,
		)

	def clean_float(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.Float64, strict=False).fill_null(0.0),
			create_new_column, new_column_name,
		)

	def ceiling(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.Float64, strict=True).ceil(),
			create_new_column, new_column_name,
		)

	def floor(self, df, column, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.Float64, strict=True).floor(),
			create_new_column, new_column_name,
		)

	def max(self, df, column_a, column_b, new_column_name):
		if not new_column_name:
			raise ValueError("new_column_name is required")
		if new_column_name in df.columns:
			raise ValueError(f"Column {new_column_name!r} already exists")
		values = pl.max_horizontal(
			pl.col(column_a).cast(pl.Float64, strict=True),
			pl.col(column_b).cast(pl.Float64, strict=True),
		)
		return df.with_columns(values.alias(new_column_name))

	def min(self, df, column_a, column_b, new_column_name):
		if not new_column_name:
			raise ValueError("new_column_name is required")
		if new_column_name in df.columns:
			raise ValueError(f"Column {new_column_name!r} already exists")
		values = pl.min_horizontal(
			pl.col(column_a).cast(pl.Float64, strict=True),
			pl.col(column_b).cast(pl.Float64, strict=True),
		)
		return df.with_columns(values.alias(new_column_name))

	def power(self, df, column, value, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.Float64, strict=True).pow(value),
			create_new_column, new_column_name,
		)

	def round_column(self, df, column, decimals=0, create_new_column=False, new_column_name=None):
		return self.assign_result(
			df, column, pl.col(column).cast(pl.Float64, strict=True).round(decimals),
			create_new_column, new_column_name,
		)

	def arithmetic(
		self, df, column_a, operator, column_b_or_value,
		create_new_column=False, new_column_name=None,
	):
		left = pl.col(column_a).cast(pl.Float64, strict=True)
		right = (
			pl.col(column_b_or_value).cast(pl.Float64, strict=True)
			if isinstance(column_b_or_value, str) and column_b_or_value in df.columns
			else pl.lit(column_b_or_value)
		)
		if operator == "/":
			divisor = (
				df.select((right == 0).any()).item()
				if isinstance(column_b_or_value, str) and column_b_or_value in df.columns
				else column_b_or_value == 0
			)
			if divisor:
				raise ValueError("Division by zero")
			values = left / right
		elif operator == "+":
			values = left + right
		elif operator == "-":
			values = left - right
		elif operator == "*":
			values = left * right
		else:
			raise ValueError(f"Unsupported arithmetic operator: {operator!r}")
		return self.assign_result(df, column_a, values, create_new_column, new_column_name)
