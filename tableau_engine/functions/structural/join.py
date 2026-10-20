"""Join two input dataframes."""

import pandas as pd


def _join(
	df_left: pd.DataFrame,
	df_right: pd.DataFrame,
	left_on: str | list[str],
	right_on: str | list[str],
	how: str,
) -> pd.DataFrame:
	return df_left.merge(df_right, left_on=left_on, right_on=right_on, how=how)


def inner_join(
	df_left: pd.DataFrame,
	df_right: pd.DataFrame,
	left_on: str | list[str],
	right_on: str | list[str],
) -> pd.DataFrame:
	"""Return only rows with matching join keys."""
	return _join(df_left, df_right, left_on, right_on, "inner")


def outer_join(
	df_left: pd.DataFrame,
	df_right: pd.DataFrame,
	left_on: str | list[str],
	right_on: str | list[str],
) -> pd.DataFrame:
	"""Return rows from both inputs, matching keys where possible."""
	return _join(df_left, df_right, left_on, right_on, "outer")