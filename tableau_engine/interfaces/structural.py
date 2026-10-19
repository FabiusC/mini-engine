"""Dispatch table-level operations to their atomic implementations."""

from collections.abc import Sequence
from typing import Any

import pandas as pd

from tableau_engine.functions.structural import join, union


class StructuralInterface:
	"""Route joins, unions, aggregations, and column removal."""

	@staticmethod
	def execute(
		operation: str,
		df: pd.DataFrame | None,
		*,
		input_dfs: Sequence[pd.DataFrame] | None = None,
		**kwargs: Any,
	) -> pd.DataFrame:
		"""Execute a named structural operation using one or more input frames."""
		normalized = operation.upper()
		if normalized == "UNION":
			frames = list(input_dfs or ([df] if df is not None else []))
			return union(frames)
		if normalized == "JOIN":
			frames = list(input_dfs or ([df] if df is not None else []))
			if len(frames) != 2:
				raise ValueError("JOIN requires exactly two input dataframes")
			return join(frames[0], frames[1], **kwargs)
		raise ValueError(f"Unknown structural operation: {operation}")