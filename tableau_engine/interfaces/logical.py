"""Abstract contracts for logical dataframe transformations."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping

import pandas as pd


class LogicalInterface(ABC):
	"""Contract implemented by pandas logical processors."""

	@staticmethod
	@abstractmethod
	def logical(
		df: pd.DataFrame, operation: str, column: str, sentencia1: str,
		sentencia2: str | None = None, reemplazar_campo: bool = True,
		nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def coalesce(
		df: pd.DataFrame, column: str, default_value: object,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def conditional_map(
		df: pd.DataFrame, column: str,
		condition_func: Callable[[pd.Series], pd.Series] | Mapping[str, object],
		true_value: object, false_value: object,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame: ...
