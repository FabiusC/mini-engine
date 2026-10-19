"""Dispatch date operations to their atomic implementations."""

from typing import Any

import pandas as pd

from tableau_engine.functions.dates import date_parser, date_part


class DatesInterface:
	"""Route date operation names to the corresponding pure function."""

	_operations = {"PARSE": date_parser, "DATE_PART": date_part}

	@staticmethod
	def execute(operation: str, df: pd.DataFrame | None, **kwargs: Any) -> pd.DataFrame:
		"""Execute a named date transformation on one dataframe."""
		if df is None:
			raise ValueError("Date operations require one input dataframe")
		try:
			function = DatesInterface._operations[operation.upper()]
		except KeyError as error:
			raise ValueError(f"Unknown date operation: {operation}") from error
		return function(df, **kwargs)