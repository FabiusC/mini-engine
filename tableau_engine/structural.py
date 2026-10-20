"""Structural dataframe operations."""

from typing import Literal

import pandas as pd


def join(
	df_left: pd.DataFrame,
	df_right: pd.DataFrame,
	left_on: str | list[str],
	right_on: str | list[str],
	how: Literal["inner", "left", "right", "outer"] = "inner",
) -> pd.DataFrame:
	"""Join two dataframes by their key columns without modifying the inputs."""
	return df_left.merge(df_right, left_on=left_on, right_on=right_on, how=how)