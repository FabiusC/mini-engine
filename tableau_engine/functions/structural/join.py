"""Join two dataframes."""

import pandas as pd


def join(
	df_left: pd.DataFrame,
	df_right: pd.DataFrame,
	left_on: str | list[str],
	right_on: str | list[str],
	how: str = "inner",
) -> pd.DataFrame:
	"""Return a new dataframe with the requested relational join."""
	return df_left.merge(df_right, left_on=left_on, right_on=right_on, how=how)