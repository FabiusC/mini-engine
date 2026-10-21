"""Facade for null handling and conditional transformations."""

from collections.abc import Sequence
from functools import partial
from typing import Any

import pandas as pd

from tableau_engine.functions.logical import LogicalProcessor
from tableau_engine.interfaces.inputs import require_inputs


class LogicalInterface:
	"""Route logical operations."""

	_operations = {
		"coalesce": LogicalProcessor.coalesce,
		"ifnull": LogicalProcessor.coalesce,
		"conditional_map": LogicalProcessor.conditional_map,
		"and": partial(LogicalProcessor.logical, operation="and"),
		"case": partial(LogicalProcessor.logical, operation="case"),
		"if": partial(LogicalProcessor.logical, operation="if"),
		"elseif": partial(LogicalProcessor.logical, operation="elseif"),
		"or": partial(LogicalProcessor.logical, operation="or"),
		"not": partial(LogicalProcessor.logical, operation="not"),
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		function = LogicalInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown logical operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
