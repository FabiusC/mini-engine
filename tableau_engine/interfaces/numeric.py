"""Facade for numeric dataframe transformations."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.numeric import (
	absolute,
	arithmetic,
	ceiling,
	clean_float,
	floor,
	max,
	min,
	power,
	round_column,
)
from tableau_engine.interfaces.inputs import require_inputs


class NumericInterface:
	"""Route numeric operations to their dataframe functions."""

	_operations = {
		"absolute": absolute,
		"abs": absolute,
		"arithmetic": arithmetic,
		"ceiling": ceiling,
		"clean_float": clean_float,
		"floor": floor,
		"max": max,
		"min": min,
		"power": power,
		"round": round_column,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a numeric operation to the single input dataframe."""
		function = NumericInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown numeric operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)