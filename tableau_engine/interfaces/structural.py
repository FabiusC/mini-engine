"""Facade for structural dataframe operations."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.structural import inner_join, outer_join


class StructuralInterface:
	"""Dispatch join operations and their input dataframes."""

	_operations = {"inner_join": inner_join, "outer_join": outer_join}

	@staticmethod
	def execute(
		operation: str,
		inputs: Sequence[pd.DataFrame],
		**parameters: Any,
	) -> pd.DataFrame:
		"""Run a structural operation selected by its API operation name."""
		if len(inputs) != 2:
			raise ValueError(f"{operation} requires two input dataframes")
		try:
			function = StructuralInterface._operations[operation.lower()]
		except KeyError as error:
			raise ValueError(f"Unknown structural operation: {operation}") from error
		try:
			return function(inputs[0], inputs[1], **parameters)
		except TypeError as error:
			raise ValueError(
				f"{operation} requires left_on and right_on parameters"
			) from error