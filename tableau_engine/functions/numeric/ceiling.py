"""Round numeric values upward to the nearest integer."""

import numpy as np
import pandas as pd


def ceiling(df: pd.DataFrame, column: str) -> pd.DataFrame:
	"""Return a copy with values in the selected column rounded upward."""
	result = df.copy()
	result[column] = np.ceil(pd.to_numeric(result[column]))
	return result