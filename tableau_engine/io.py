"""Read CSV datasources as pandas dataframes."""

from pathlib import Path

import pandas as pd


def read_datasource(filepath: str | Path) -> pd.DataFrame:
	"""Read a CSV using UTF-8, falling back to Latin-1 when needed."""
	try:
		return pd.read_csv(filepath, encoding="utf-8-sig")
	except UnicodeDecodeError:
		return pd.read_csv(filepath, encoding="latin1")