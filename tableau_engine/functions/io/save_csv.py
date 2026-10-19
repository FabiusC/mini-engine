"""Write a dataframe to a CSV file."""

from pathlib import Path

import pandas as pd


def save_csv(
	df: pd.DataFrame,
	filepath: str | Path,
	index: bool = False,
) -> pd.DataFrame:
	"""Save a dataframe and return it unchanged for downstream graph outputs."""
	path = Path(filepath)
	path.parent.mkdir(parents=True, exist_ok=True)
	df.to_csv(path, index=index)
	return df