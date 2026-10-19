"""Dispatch data type conversions to their atomic implementation."""

from typing import Any

import pandas as pd

from tableau_engine.functions.casting import change_type, to_numeric


class CastingInterface:
	"""Route casting operation names to the corresponding pure function."""

	_operations = {"CHANGE_TYPE": change_type, "TO_NUMERIC": to_numeric}

	@staticmethod
	def execute(operation: str, df: pd.DataFrame | None, **kwargs: Any) -> pd.DataFrame:
		"""Execute a named type conversion on one dataframe."""
		if df is None:
			raise ValueError("Casting operations require one input dataframe")
		try:
			function = CastingInterface._operations[operation.upper()]
		except KeyError as error:
			raise ValueError(f"Unknown casting operation: {operation}") from error
		return function(df, **kwargs)