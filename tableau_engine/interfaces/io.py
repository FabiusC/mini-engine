"""Facade for reading and writing datasets."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.io import IOProcessor
from tableau_engine.interfaces.inputs import require_inputs


class IOInterface:
	"""Route input and output operations."""

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Read a source without inputs, or write the single input dataframe."""
		if operation == "input":
			require_inputs(operation, inputs, 0)
			return IOProcessor.input_data(**parameters)
		if operation == "output":
			require_inputs(operation, inputs, 1)
			return IOProcessor.output_data(inputs[0], **parameters)
		if operation == "read_csv":
			require_inputs(operation, inputs, 0)
			return IOProcessor.read_csv(**parameters)
		if operation == "write_csv":
			require_inputs(operation, inputs, 1)
			return IOProcessor.write_csv(inputs[0], **parameters)
		raise ValueError(f"Unknown IO operation: {operation}")
