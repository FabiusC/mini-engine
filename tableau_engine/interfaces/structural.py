"""Facade for operations that combine datasets."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.structural import join
from tableau_engine.interfaces.inputs import require_inputs


class StructuralInterface:
	"""Route join operations to the shared join function."""

	_join_types = {"inner_join": "inner", "outer_join": "outer"}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Join the left and right input dataframes."""
		how = StructuralInterface._join_types.get(operation)
		if how is None:
			raise ValueError(f"Unknown structural operation: {operation}")
		require_inputs(operation, inputs, 2)
		return join(inputs[0], inputs[1], how=how, **parameters)
