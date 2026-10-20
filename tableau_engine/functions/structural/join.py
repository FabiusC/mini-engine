"""Join two dataframes."""

from collections.abc import Sequence

import pandas as pd


def join(
	left: pd.DataFrame,
	right: pd.DataFrame,
	how: str = "inner",
	left_on: str | list[str] | None = None,
	right_on: str | list[str] | None = None,
	suffixes: Sequence[str] = ("_x", "_y"),
) -> pd.DataFrame:
	"""Join two dataframes, inferring the key only when exactly one column is shared."""
	if left_on is None and right_on is None:
		shared = [column for column in left.columns if column in right.columns]
		if len(shared) != 1:
			raise ValueError(f"Join needs join keys; shared columns are {shared}")
		left_on = right_on = shared[0]
	if left_on is None or right_on is None:
		raise ValueError("Join needs both left_on and right_on")
	return left.merge(
		right,
		left_on=left_on,
		right_on=right_on,
		how=how,
		suffixes=tuple(suffixes),
	)
