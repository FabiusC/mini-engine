"""Facade for operations that change a dataframe's columns."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.column import add_column
from tableau_engine.interfaces.inputs import require_inputs


class ColumnInterface:
	"""Route column operations."""

	_operations = {"add_column": add_column}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a column operation to the single input dataframe."""
		function = ColumnInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown column operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
