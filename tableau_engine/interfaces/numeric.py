"""Facade for numeric dataframe transformations."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.numeric import NumericProcessor
from tableau_engine.interfaces.inputs import require_inputs


class NumericInterface:
	"""Route numeric operations to their dataframe functions."""

	_operations = {
		"absolute": NumericProcessor.absolute,
		"abs": NumericProcessor.absolute,
		"arithmetic": NumericProcessor.arithmetic,
		"ceiling": NumericProcessor.ceiling,
		"clean_float": NumericProcessor.clean_float,
		"floor": NumericProcessor.floor,
		"max": NumericProcessor.max,
		"min": NumericProcessor.min,
		"power": NumericProcessor.power,
		"round": NumericProcessor.round_column,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a numeric operation to the single input dataframe."""
		function = NumericInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown numeric operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
