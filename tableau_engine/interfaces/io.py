"""Facade for reading and writing datasets."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.io import IOProcessor
from tableau_engine.interfaces.inputs import require_inputs


class IOInterface:
	"""Route input and output operations."""

	_operations = {
		"input": IOProcessor.input_data,
		"output": IOProcessor.output_data,
		"read_csv": IOProcessor.read_csv,
		"write_csv": IOProcessor.write_csv,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Read a source without inputs, or write the single input dataframe."""
		function = IOInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown IO operation: {operation}")
		if operation in ("input", "read_csv"):
			require_inputs(operation, inputs, 0)
			return function(**parameters)
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
