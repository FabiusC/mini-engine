"""Dispatch text operations to their atomic implementations."""

from typing import Any

import pandas as pd

from tableau_engine.functions.text import lowercase, uppercase


class TextInterface:
	"""Route text operation names to the corresponding pure function."""

	_operations = {
		"UPPER": uppercase,
		"LOWER": lowercase,
	}

	@staticmethod
	def execute(operation: str, df: pd.DataFrame | None, **kwargs: Any) -> pd.DataFrame:
		"""Execute a named text transformation on one dataframe."""
		if df is None:
			raise ValueError("Text operations require one input dataframe")
		try:
			function = TextInterface._operations[operation.upper()]
		except KeyError as error:
			raise ValueError(f"Unknown text operation: {operation}") from error
		return function(df, **kwargs)