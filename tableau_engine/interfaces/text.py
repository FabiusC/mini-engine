"""Facade for text transformations."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.text import TextProcessor
from tableau_engine.interfaces.inputs import require_inputs


class TextInterface:
	"""Route text operations with shared output-column controls."""

	_operations = {
		"uppercase": TextProcessor.uppercase, "upper": TextProcessor.uppercase,
		"lowercase": TextProcessor.lowercase, "lower": TextProcessor.lowercase,
		"trim": TextProcessor.trim, "ltrim": TextProcessor.ltrim, "rtrim": TextProcessor.rtrim,
		"substring": TextProcessor.substring, "replace": TextProcessor.replace, "split": TextProcessor.split, "concat": TextProcessor.concat,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a text operation to the single input dataframe."""
		function = TextInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown text operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
