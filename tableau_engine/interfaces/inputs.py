"""Shared input validation for operation facades."""

from collections.abc import Sequence

import pandas as pd


def require_inputs(operation: str, inputs: Sequence[pd.DataFrame], count: int) -> None:
	"""Raise when an operation receives the wrong number of input dataframes."""
	if len(inputs) != count:
		raise ValueError(
			f"{operation} requires {count} input dataframe(s), received {len(inputs)}"
		)
