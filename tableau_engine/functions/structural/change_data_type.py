"""Change the dtype of a dataframe column."""

import pandas as pd


def change_data_type(df: pd.DataFrame, column: str, new_type: str) -> pd.DataFrame:
	"""Return a copy with the selected column cast to ``new_type``."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	result = df.copy()
	result[column] = result[column].astype(new_type)
	return result