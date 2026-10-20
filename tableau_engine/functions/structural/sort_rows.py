"""Sort dataframe rows by a column."""

import pandas as pd


def sort_rows(
	df: pd.DataFrame,
	column: str,
	direction: str = "asc",
) -> pd.DataFrame:
	"""Return a copy sorted by ``column`` in ascending or descending order."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	directions = {"asc": True, "desc": False, "des": False}
	try:
		ascending = directions[direction.lower()]
	except (AttributeError, KeyError) as error:
		raise ValueError("direction must be 'asc' or 'desc'") from error
	return df.sort_values(by=column, ascending=ascending)