"""CSV input and output operations."""

from pathlib import Path

import pandas as pd


def read_csv(filepath: str | Path) -> pd.DataFrame:
	"""Read a CSV as UTF-8, falling back to Latin-1 when decoding fails."""
	try:
		return pd.read_csv(filepath, encoding="utf-8-sig")
	except UnicodeDecodeError:
		return pd.read_csv(filepath, encoding="latin1")


def write_csv(df: pd.DataFrame, filepath: str | Path, index: bool = False) -> pd.DataFrame:
	"""Overwrite the target CSV and return the dataframe unchanged."""
	path = Path(filepath)
	path.parent.mkdir(parents=True, exist_ok=True)
	df.to_csv(path, index=index)
	return df