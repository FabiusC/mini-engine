"""Null handling and vectorized conditional transformations."""

from collections.abc import Callable, Mapping

import pandas as pd
from pandas.api.types import is_bool_dtype

from tableau_engine.functions.row import condition_mask
from tableau_engine.functions.structural import assign_result


def coalesce(
	df: pd.DataFrame, column: str, default_value: object,
	create_new_column: bool = False, new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Fill nulls and empty strings, without treating zero/False as missing."""
	values = df[column].replace("", None)
	if default_value is not None:
		values = values.fillna(default_value)
	return assign_result(df, column, values, create_new_column, new_column_name)


def conditional_map(
	df: pd.DataFrame,
	column: str,
	condition_func: Callable[[pd.Series], pd.Series] | Mapping[str, object],
	true_value: object,
	false_value: object,
	create_new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Evaluate a Series callable or a JSON operator/value condition; never eval code."""
	if isinstance(condition_func, Mapping):
		if set(condition_func) - {"operator", "value"} or "operator" not in condition_func:
			raise ValueError("condition_func must contain operator and optional value")
		operator = condition_func["operator"]
		if not isinstance(operator, str):
			raise ValueError("condition operator must be a string")
		mask = condition_mask(df[column], operator, condition_func.get("value"))
	elif callable(condition_func):
		mask = condition_func(df[column].copy())
	else:
		raise ValueError("condition_func must be a callable or an operator/value mapping")
	if not isinstance(mask, pd.Series) or not mask.index.equals(df.index) or not is_bool_dtype(mask.dtype):
		raise ValueError("condition_func must return a boolean Series with the input index")
	values = pd.Series(true_value, index=df.index).where(mask.fillna(False), false_value)
	return assign_result(df, column, values, create_new_column, new_column_name)
