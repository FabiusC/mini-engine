"""Null handling and vectorized conditional transformations."""

from collections.abc import Callable, Mapping
import json
import operator
import re

import pandas as pd
from pandas.api.types import is_bool_dtype

from engine.processors.row_processor import RowProcessor
from engine.processors.structural_processor import StructuralProcessor


class LogicalProcessor:
	"""Stateless logical operations for dataframe pipelines."""

	_CONDITION_PATTERN = re.compile(
		r"^\s*(?P<column>.+?)\s*(?P<operator>==|!=|>=|<=|>|<|contains|isnull)\s*(?P<value>.*?)\s*$",
		re.IGNORECASE,
	)

	def _parse_condition(
		self,
		df: pd.DataFrame, column: str, statement: str,
	) -> tuple[pd.Series, str]:
		"""Parse a single safe ``column operator value`` condition."""
		if not isinstance(statement, str):
			raise ValueError("Conditions must be strings in 'column operator value' format")
		match = self._CONDITION_PATTERN.fullmatch(statement)
		if match is None:
			raise ValueError("Condition must use 'column operator value' format")
		if match.group("column").strip() != column:
			raise ValueError(f"Condition column must match source column {column!r}")

		operator = match.group("operator").lower()
		raw_value = match.group("value").strip()
		if operator == "isnull":
			if raw_value:
				raise ValueError("The isnull condition does not accept a value")
			value = None
		else:
			if not raw_value:
				raise ValueError("Condition value is required")
			try:
				value = json.loads(raw_value)
			except json.JSONDecodeError:
				if re.fullmatch(r"[\w .-]+", raw_value) is None:
					raise ValueError("Condition value must be a literal, not an expression")
				value = raw_value
			if not isinstance(value, (str, int, float, bool, type(None))):
				raise ValueError("Condition value must be a scalar literal")
		return RowProcessor().condition_mask(df[column], operator, value), operator

	def logical(
		self,
			df: pd.DataFrame,
			operation: str,
			column: str,
			sentencia1: str,
		sentencia2: str | None = None,
		reemplazar_campo: bool = True,
		nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame:
		"""Evaluate a logical operation and assign its boolean result."""
		operators = {
			"and": operator.and_,
			"if": operator.and_,
			"or": operator.or_,
			"case": operator.or_,
			"elseif": operator.or_,
		}
		if operation not in (*operators, "not"):
			raise ValueError(f"Unsupported logical operation: {operation!r}")
		if not isinstance(reemplazar_campo, bool):
			raise ValueError("reemplazar_campo must be a boolean")
		if reemplazar_campo:
			if nombre_nueva_columna is not None:
				raise ValueError("nombre_nueva_columna requires reemplazar_campo to be false")
		elif not isinstance(nombre_nueva_columna, str) or not nombre_nueva_columna:
			raise ValueError("nombre_nueva_columna is required when reemplazar_campo is false")

		first_mask, first_operator = self._parse_condition(df, column, sentencia1)
		first_mask = first_mask.fillna(False)
		if operation == "not":
			values = ~first_mask
			if first_operator != "isnull":
				values &= df[column].notna()
		else:
			if sentencia2 is None:
				raise ValueError(f"{operation} requires sentencia2")
			second_mask, _ = self._parse_condition(df, column, sentencia2)
			values = operators[operation](first_mask, second_mask.fillna(False))

		return StructuralProcessor().assign_result(
			df,
			column,
			values.astype(bool),
			create_new_column=not reemplazar_campo,
			new_column_name=nombre_nueva_columna if not reemplazar_campo else None,
		)

	def coalesce(
		self,
		df: pd.DataFrame, column: str, default_value: object,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Fill nulls and empty strings, without treating zero/False as missing."""
		values = df[column].replace("", None)
		if default_value is not None:
			values = values.fillna(default_value)
		return StructuralProcessor().assign_result(df, column, values, create_new_column, new_column_name)

	def conditional_map(
		self,
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
			mask = RowProcessor().condition_mask(df[column], operator, condition_func.get("value"))
		elif callable(condition_func):
			mask = condition_func(df[column].copy())
		else:
			raise ValueError("condition_func must be a callable or an operator/value mapping")
		if not isinstance(mask, pd.Series) or not mask.index.equals(df.index) or not is_bool_dtype(mask.dtype):
			raise ValueError("condition_func must return a boolean Series with the input index")
		values = pd.Series(true_value, index=df.index).where(mask.fillna(False), false_value)
		return StructuralProcessor().assign_result(df, column, values, create_new_column, new_column_name)
