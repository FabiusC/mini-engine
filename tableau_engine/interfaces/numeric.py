"""Dispatch numeric operations to their atomic implementations."""

from typing import Any

import pandas as pd

from tableau_engine.functions.numeric import ceiling, floor


class NumericInterface:
	"""Route numeric operation names to the corresponding pure function."""

	_operations = {"CEILING": ceiling, "FLOOR": floor}

	@staticmethod
	def execute(operation: str, df: pd.DataFrame | None, **kwargs: Any) -> pd.DataFrame:
		"""Execute a named numeric transformation on one dataframe."""
		if df is None:
			raise ValueError("Numeric operations require one input dataframe")
		try:
			function = NumericInterface._operations[operation.upper()]
		except KeyError as error:
			raise ValueError(f"Unknown numeric operation: {operation}") from error
		return function(df, **kwargs)