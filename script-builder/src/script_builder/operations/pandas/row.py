"""Row-level dataframe transformations."""

import pandas as pd


class RowOperations:
	"""Stateless row operations for dataframe pipelines."""

	def condition_mask(self, series: pd.Series, operator: str, value: object = None) -> pd.Series:
		"""Build a reusable pandas comparison mask, excluding missing comparisons."""
		if operator == "==":
			mask = series == value
		elif operator == "!=":
			mask = series != value
		elif operator == ">":
			mask = series > value
		elif operator == "<":
			mask = series < value
		elif operator == ">=":
			mask = series >= value
		elif operator == "<=":
			mask = series <= value
		elif operator == "contains":
			mask = series.astype("string").str.contains(str(value), regex=False, na=False)
		elif operator == "isnull":
			return series.isna()
		else:
			raise ValueError(f"Unsupported filter operator: {operator!r}")
		return mask.fillna(False) & series.notna()

	def filter_rows(self, df: pd.DataFrame, column: str, operator: str, value: object = None) -> pd.DataFrame:
		"""Return rows matching a comparison, literal contains, or null test."""
		mask = self.condition_mask(df[column], operator, value)
		return df.loc[mask].copy()

	def sample(
		self,
		df: pd.DataFrame,
		sample_type: str,
		fraction_or_count: float | int,
		random_state: int | None = None,
	) -> pd.DataFrame:
		"""Sample a fraction (float in [0, 1]) or an absolute count (integer)."""
		if isinstance(fraction_or_count, bool) or not isinstance(fraction_or_count, (int, float)):
			raise ValueError("fraction_or_count must be an integer count or a float fraction")
		is_fraction = isinstance(fraction_or_count, float)
		if is_fraction and not 0 <= fraction_or_count <= 1:
			raise ValueError("A fraction must be between 0 and 1")
		if fraction_or_count < 0:
			raise ValueError("A count must not be negative")
		if sample_type == "head":
			count = int(len(df) * fraction_or_count) if is_fraction else fraction_or_count
			return df.head(count).copy()
		if sample_type == "random":
			if is_fraction:
				return df.sample(frac=fraction_or_count, random_state=random_state)
			return df.sample(n=fraction_or_count, random_state=random_state)
		raise ValueError("sample_type must be 'random' or 'head'")

	def limit_rows(self, df: pd.DataFrame, limit: int) -> pd.DataFrame:
		"""Return a copy containing at most ``limit`` rows."""
		limit = int(limit)
		if limit < 0:
			raise ValueError("limit must be zero or greater")
		return df.head(limit).copy()

	def sort_rows(
		self,
		df: pd.DataFrame,
		column: str,
		direction: str = "asc",
	) -> pd.DataFrame:
		"""Return a copy sorted by ``column`` in ascending or descending order."""
		directions = {"asc": True, "desc": False, "des": False}
		try:
			ascending = directions[direction.lower()]
		except (AttributeError, KeyError) as error:
			raise ValueError("direction must be 'asc' or 'desc'") from error
		return df.sort_values(by=column, ascending=ascending)
