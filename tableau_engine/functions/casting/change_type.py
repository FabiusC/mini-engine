"""Convert a dataframe column to a requested data type."""

import pandas as pd


def change_type(
	df: pd.DataFrame,
	column: str,
	dtype: str,
	errors: str = "raise",
) -> pd.DataFrame:
	"""Return a copy with a column converted to a common pandas dtype."""
	result = df.copy()
	target = dtype.lower()
	if target in {"int", "integer", "int64"} and errors == "coerce":
		result[column] = pd.to_numeric(result[column], errors="coerce").astype("Int64")
	elif target in {"float", "float64"}:
		result[column] = pd.to_numeric(result[column], errors=errors).astype("float64")
	elif target in {"datetime", "date"}:
		result[column] = pd.to_datetime(result[column], errors=errors)
	elif target in {"string", "str"}:
		result[column] = result[column].astype("string")
	elif target in {"int", "integer", "int64"}:
		result[column] = pd.to_numeric(result[column], errors=errors).astype("int64")
	else:
		result[column] = result[column].astype(dtype, errors=errors)
	return result