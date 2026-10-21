"""Facade for operations that combine datasets."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.structural import StructuralProcessor
from tableau_engine.interfaces.inputs import require_inputs


class StructuralInterface:
	"""Route joins and dataframe-structure operations."""

	_join_types = {"inner_join": "inner", "outer_join": "outer"}
	_operations = {
		"union": StructuralProcessor.union,
		"join": StructuralProcessor.join,
		"inner_join": StructuralProcessor.join,
		"outer_join": StructuralProcessor.join,
		"add_column": StructuralProcessor.add_column,
		"sort": StructuralProcessor.sort_rows,
		"drop-column": StructuralProcessor.drop_column,
		"drop_column": StructuralProcessor.drop_column,
		"rename-column": StructuralProcessor.rename_column,
		"rename_column": StructuralProcessor.rename_column,
		"change-data-type": StructuralProcessor.change_data_type,
		"change_data_type": StructuralProcessor.change_data_type,
		"aggregate": StructuralProcessor.aggregate,
		"pivot": StructuralProcessor.pivot,
	}

	@staticmethod
	def execute(operation: str, inputs: Sequence[pd.DataFrame], **parameters: Any) -> pd.DataFrame:
		"""Apply a join or a structural operation to dataframe inputs."""
		if operation == "union":
			return StructuralProcessor.union(inputs, **parameters)
		function = StructuralInterface._operations.get(operation)
		if function is None:
			raise ValueError(f"Unknown structural operation: {operation}")
		if operation == "join":
			require_inputs(operation, inputs, 2)
			return function(inputs[0], inputs[1], **parameters)
		how = StructuralInterface._join_types.get(operation)
		if how is not None:
			require_inputs(operation, inputs, 2)
			return function(inputs[0], inputs[1], how=how, **parameters)
		require_inputs(operation, inputs, 1)
		return function(inputs[0], **parameters)
