"""Facade for operations that select rows."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.row import filter_rows, limit_rows
from tableau_engine.interfaces.inputs import require_inputs


class RowInterface:
	"""Route row selection operations."""

	_operations = {"filter": filter_rows, "limit": limit_rows}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a row operation to the single input dataframe."""
		function = RowInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown row operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
