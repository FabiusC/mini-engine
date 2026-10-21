"""Facade for type and date/time conversions."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.conversion import ConversionProcessor
from tableau_engine.interfaces.inputs import require_inputs


class ConversionInterface:
	"""Route conversion operations."""

	_operations = {
		"date": ConversionProcessor.date,
		"datetime": ConversionProcessor.datetime,
		"float": ConversionProcessor.float,
		"int": ConversionProcessor.int,
		"str": ConversionProcessor.str,
		"make_date": ConversionProcessor.make_date,
		"make_time": ConversionProcessor.make_time,
		"make_date_time": ConversionProcessor.make_date_time,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		function = ConversionInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown conversion operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
