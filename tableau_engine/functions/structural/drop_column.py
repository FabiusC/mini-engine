"""Remove one or more columns from a dataframe."""

from collections.abc import Sequence

import pandas as pd


def drop_column(df: pd.DataFrame, column: str | Sequence[str]) -> pd.DataFrame:
	"""Return a copy without the requested column or columns."""
	columns = [column] if isinstance(column, str) else list(column)
	missing = [name for name in columns if name not in df.columns]
	if missing:
		raise ValueError(f"Columns {missing!r} are not present in the input")
	return df.drop(columns=columns)