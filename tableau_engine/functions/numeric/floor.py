"""Round numeric values downward to the nearest integer."""

import numpy as np
import pandas as pd


def floor(df: pd.DataFrame, column: str) -> pd.DataFrame:
	"""Return a copy with values in the selected column rounded downward."""
	result = df.copy()
	result[column] = np.floor(pd.to_numeric(result[column]))
	return result