class PolarsRowOperations:
	def filter(self, df, column, operator, value=None):
		item = pl.col(column)
		if operator == "isnull":
			mask = item.is_null()
		elif operator == "contains":
			mask = item.cast(pl.String).str.contains(str(value), literal=True)
		else:
			comparisons = {"==": item == value, "!=": item != value, ">": item > value,
				"<": item < value, ">=": item >= value, "<=": item <= value}
			mask = comparisons[operator]
		return df.filter(mask.fill_null(False))

	def limit(self, df, limit):
		return df.head(limit)

	def sort(self, df, column, direction="asc"):
		return df.sort(column, descending=direction.lower() != "asc", nulls_last=True)

	def sample(self, df, sample_type, fraction_or_count, random_state=None):
		if isinstance(fraction_or_count, bool) or not isinstance(fraction_or_count, (int, float)):
			raise ValueError("fraction_or_count must be an integer count or a float fraction")
		is_fraction = isinstance(fraction_or_count, float)
		if is_fraction and not 0 <= fraction_or_count <= 1:
			raise ValueError("A fraction must be between 0 and 1")
		if fraction_or_count < 0:
			raise ValueError("A count must not be negative")
		if sample_type == "head":
			count = int(df.height * fraction_or_count) if is_fraction else fraction_or_count
			return df.head(count)
		if sample_type == "random":
			return df.sample(
				fraction=fraction_or_count if is_fraction else None,
				n=None if is_fraction else fraction_or_count,
				seed=random_state,
			)
		raise ValueError("sample_type must be 'random' or 'head'")
