"""Concatenate dataframes by rows."""

from collections.abc import Sequence

import pandas as pd


def union(dataframes: Sequence[pd.DataFrame]) -> pd.DataFrame:
	"""Return dataframes concatenated by rows and aligned by column name."""
	if not dataframes:
		raise ValueError("At least one dataframe is required for union")
	return pd.concat(dataframes, ignore_index=True, sort=False)