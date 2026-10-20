"""Facade for text transformations."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.text import lowercase, uppercase
from tableau_engine.interfaces.inputs import require_inputs


class TextInterface:
	"""Route text operations; each accepts ``new_column`` and ``new_column_name``."""

	_operations = {"uppercase": uppercase, "lowercase": lowercase}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a text operation to the single input dataframe."""
		function = TextInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown text operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
