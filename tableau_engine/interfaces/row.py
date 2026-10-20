"""Facade for row filtering and limiting operations."""

from typing import Any

import pandas as pd

from tableau_engine.functions.row import filter_rows, limit_rows


class RowInterface:
	"""Dispatch row operations to their pure implementations."""

	_operations = {"filter": filter_rows, "limit": limit_rows}

	@staticmethod
	def execute(operation: str, df: pd.DataFrame, **parameters: Any) -> pd.DataFrame:
		"""Run a row operation selected by its API operation name."""
		try:
			function = RowInterface._operations[operation.lower()]
		except KeyError as error:
			raise ValueError(f"Unknown row operation: {operation}") from error
		try:
			return function(df, **parameters)
		except TypeError as error:
			required = "limit" if operation.lower() == "limit" else "column, operator, value"
			raise ValueError(f"{operation} requires {required} parameters") from error