"""Facade for operations that combine datasets."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.structural import (
	add_column,
	aggregate,
	change_data_type,
	drop_column,
	join,
	pivot,
	rename_column,
	sort_rows,
	union,
)
from tableau_engine.interfaces.inputs import require_inputs


class StructuralInterface:
	"""Route joins and dataframe-structure operations."""

	_join_types = {"inner_join": "inner", "outer_join": "outer"}
	_transformations = {
		"add_column": add_column,
		"sort": sort_rows,
		"drop-column": drop_column,
		"drop_column": drop_column,
		"rename-column": rename_column,
		"rename_column": rename_column,
		"change-data-type": change_data_type,
		"change_data_type": change_data_type,
		"aggregate": aggregate,
		"pivot": pivot,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a join or a structural operation to dataframe inputs."""
		if operation == "union":
			return union(inputs, **parameters)
		if operation == "join":
			require_inputs(operation, inputs, 2)
			return join(inputs[0], inputs[1], **parameters)
		how = StructuralInterface._join_types.get(operation)
		if how is not None:
			require_inputs(operation, inputs, 2)
			return join(inputs[0], inputs[1], how=how, **parameters)
		function = StructuralInterface._transformations.get(operation)
		if function is None:
			raise ValueError(f"Unknown structural operation: {operation}")
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
