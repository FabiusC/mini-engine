"""Facade for operations that combine datasets."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.structural import (
	change_data_type,
	drop_column,
	join,
	rename_column,
	sort_rows,
)
from tableau_engine.interfaces.inputs import require_inputs


class StructuralInterface:
	"""Route joins and dataframe-structure operations."""

	_join_types = {"inner_join": "inner", "outer_join": "outer"}
	_transformations = {
		"sort": sort_rows,
		"drop-column": drop_column,
		"rename-column": rename_column,
		"change-data-type": change_data_type,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a join or a structural operation to dataframe inputs."""
		how = StructuralInterface._join_types.get(operation)
		if how is not None:
			require_inputs(operation, inputs, 2)
			return join(inputs[0], inputs[1], how=how, **parameters)
		function = StructuralInterface._transformations.get(operation)
		if function is None:
			raise ValueError(f"Unknown structural operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
