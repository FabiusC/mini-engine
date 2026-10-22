"""Abstract contracts for row selection and sampling operations."""

from abc import ABC, abstractmethod

import pandas as pd


class RowInterface(ABC):
	"""Contract implemented by pandas row processors."""

	@staticmethod
	@abstractmethod
	def filter_rows(
		df: pd.DataFrame, column: str, operator: str, value: object = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def sample(
		df: pd.DataFrame, sample_type: str, fraction_or_count: float | int,
		random_state: int | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def limit_rows(df: pd.DataFrame, limit: int) -> pd.DataFrame: ...
