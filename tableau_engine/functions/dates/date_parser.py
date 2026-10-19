"""Parse a dataframe column as datetimes."""

import pandas as pd


def date_parser(
	df: pd.DataFrame,
	column: str,
	date_format: str | None = None,
	errors: str = "coerce",
) -> pd.DataFrame:
	"""Return a copy with the selected column parsed as datetime values."""
	result = df.copy()
	result[column] = pd.to_datetime(
		result[column], format=date_format, errors=errors
	)
	return result