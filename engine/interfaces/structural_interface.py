"""Abstract contracts for dataframe structure and combination operations."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

import pandas as pd


class StructuralInterface(ABC):
	"""Contract implemented by pandas structural processors."""

	@staticmethod
	@abstractmethod
	def add_column(
		df: pd.DataFrame, column_name: str, value: object = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def change_data_type(
		df: pd.DataFrame, column: str, new_type: str | None = None, *,
		target_type: str | None = None,
		create_new_column: bool | None = None, new_column: bool = False,
		new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def drop_column(
		df: pd.DataFrame, column: str | Sequence[str] | None = None, *,
		columns: Sequence[str] | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def join(
		left: pd.DataFrame, right: pd.DataFrame, how: str = "inner",
		left_on: str | list[str] | None = None,
		right_on: str | list[str] | None = None,
		suffixes: Sequence[str] = ("_x", "_y"),
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def union(
		df_list: Sequence[pd.DataFrame], match_type: str = "auto",
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def aggregate(
		df: pd.DataFrame, group_by: list[str],
		aggregations: dict[str, str | list[str]],
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def pivot(
		df: pd.DataFrame, pivot_type: str, index_cols: list[str],
		target_col: str, values_col: str,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def rename_column(
		df: pd.DataFrame, column: str, new_name: str,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def sort_rows(
		df: pd.DataFrame, column: str, direction: str = "asc",
	) -> pd.DataFrame: ...
