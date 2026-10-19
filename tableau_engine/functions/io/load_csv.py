"""Load a CSV file with UTF-8 or Latin-1 encoding."""

from pathlib import Path

import pandas as pd


def load_csv(filepath: str | Path) -> pd.DataFrame:
	"""Read a CSV, falling back to Latin-1 when it is not valid UTF-8."""
	try:
		return pd.read_csv(filepath, encoding="utf-8-sig")
	except UnicodeDecodeError:
		return pd.read_csv(filepath, encoding="latin1")