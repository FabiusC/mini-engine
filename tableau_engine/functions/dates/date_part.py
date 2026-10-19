"""Extract a calendar component from a dataframe date column."""

import pandas as pd


def date_part(
	df: pd.DataFrame,
	column: str,
	part: str,
) -> pd.DataFrame:
	"""Return a copy with the selected date column replaced by a date component."""
	result = df.copy()
	dates = pd.to_datetime(result[column], errors="coerce")
	extractors = {
		"YEAR": dates.dt.year,
		"MONTH": dates.dt.month,
		"DAY": dates.dt.day,
		"WEEKDAY": dates.dt.dayofweek,
	}
	try:
		result[column] = extractors[part.upper()]
	except KeyError as error:
		raise ValueError("part must be YEAR, MONTH, DAY, or WEEKDAY") from error
	return result