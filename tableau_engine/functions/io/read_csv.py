"""Read a CSV file into a dataframe."""

from pathlib import Path

import pandas as pd


def read_csv(filepath: str | Path) -> pd.DataFrame:
	"""Read a CSV as UTF-8, falling back to Latin-1 when decoding fails."""
	try:
		return pd.read_csv(filepath, encoding="utf-8-sig")
	except UnicodeDecodeError:
		return pd.read_csv(filepath, encoding="latin1")
