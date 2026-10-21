"""Facade for calendar transformations."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.datetime import (
	date_add, date_diff, date_parser, date_sub, extract_date_part,
)
from tableau_engine.interfaces.inputs import require_inputs


class DateTimeInterface:
	"""Route pandas date and time transformations."""

	_operations = {
		"date_parser": date_parser, "date_add": date_add, "date_sub": date_sub,
		"date_diff": date_diff, "extract_date_part": extract_date_part,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		function = DateTimeInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown datetime operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
