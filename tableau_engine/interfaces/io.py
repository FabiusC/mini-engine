"""Dispatch data-loading operations."""

from typing import Any

import pandas as pd

from tableau_engine.functions.io import load_csv, save_csv


class IOInterface:
	"""Route supported input operations."""

	@staticmethod
	def execute(operation: str, df: pd.DataFrame | None, **kwargs: Any) -> pd.DataFrame:
		"""Load a dataset from a supported file format."""
		normalized = operation.upper()
		if normalized == "LOAD_CSV":
			return load_csv(**kwargs)
		if normalized == "SAVE_CSV":
			if df is None:
				raise ValueError("SAVE_CSV requires one input dataframe")
			return save_csv(df, **kwargs)
		raise ValueError(f"Unknown input operation: {operation}")