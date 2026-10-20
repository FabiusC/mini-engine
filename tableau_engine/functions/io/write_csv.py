"""Write a dataframe to a CSV file."""

from pathlib import Path

import pandas as pd


def write_csv(df: pd.DataFrame, filepath: str | Path, index: bool = False) -> pd.DataFrame:
	"""Overwrite the target CSV and return the dataframe unchanged."""
	path = Path(filepath)
	path.parent.mkdir(parents=True, exist_ok=True)
	df.to_csv(path, index=index)
	return df
