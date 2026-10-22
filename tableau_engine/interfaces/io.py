"""Abstract contracts for dataset input and output operations."""

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class IOInterface(ABC):
	"""Contract implemented by pandas IO processors."""

	@staticmethod
	@abstractmethod
	def read_csv(filepath: str | Path) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def write_csv(
		df: pd.DataFrame, filepath: str | Path, index: bool = False,
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def input_data(
		source_type: str, filepath_or_connection: str | Path,
		table_or_sheet: str | None = None, encoding: str = "utf-8",
		delimiter: str = ",",
	) -> pd.DataFrame: ...

	@staticmethod
	@abstractmethod
	def output_data(
		df: pd.DataFrame, destination_type: str, output_path: str | Path,
		write_mode: str = "overwrite", *, encoding: str = "utf-8",
		delimiter: str = ",",
	) -> pd.DataFrame: ...
