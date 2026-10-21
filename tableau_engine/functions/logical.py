"""Null handling and vectorized conditional transformations."""

import ast
from collections.abc import Callable, Mapping
import json
import re

import pandas as pd
from pandas.api.types import is_bool_dtype

from tableau_engine.functions.row import RowProcessor
from tableau_engine.functions.structural import StructuralProcessor


class LogicalProcessor:
	"""Stateless logical operations for dataframe pipelines."""

	_CONDITION_PATTERN = re.compile(
		r"^\s*(?P<column>.+?)\s*(?P<operator>==|!=|>=|<=|>|<|contains|isnull)\s*(?P<value>.*?)\s*$",
		re.IGNORECASE,
	)

	@staticmethod
	def _parse_condition(
		df: pd.DataFrame, column: str, statement: str,
	) -> tuple[pd.Series, str]:
		"""Parse a single safe ``column operator value`` condition."""
		if not isinstance(statement, str):
			raise ValueError("Conditions must be strings in 'column operator value' format")
		match = LogicalProcessor._CONDITION_PATTERN.fullmatch(statement)
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
				try:
					value = ast.literal_eval(raw_value)
				except (SyntaxError, ValueError):
					if re.fullmatch(r"[\w .-]+", raw_value) is None:
						raise ValueError("Condition value must be a literal, not an expression")
					value = raw_value
			if not isinstance(value, (str, int, float, bool, type(None))):
				raise ValueError("Condition value must be a scalar literal")
		return RowProcessor.condition_mask(df[column], operator, value), operator

	@staticmethod
	def _logical_result(
		df: pd.DataFrame,
		operation: str,
		column: str,
		sentencia1: str,
		sentencia2: str | None = None,
		reemplazar_campo: bool = True,
		nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame:
		"""Evaluate a logical operation and assign its boolean result."""
		if not isinstance(reemplazar_campo, bool):
			raise ValueError("reemplazar_campo must be a boolean")
		if reemplazar_campo:
			if nombre_nueva_columna is not None:
				raise ValueError("nombre_nueva_columna requires reemplazar_campo to be false")
		elif not isinstance(nombre_nueva_columna, str) or not nombre_nueva_columna:
			raise ValueError("nombre_nueva_columna is required when reemplazar_campo is false")

		if operation == "and":
			if sentencia2 is None:
				raise ValueError("and requires sentencia2")
			first_mask, _ = LogicalProcessor._parse_condition(df, column, sentencia1)
			second_mask, _ = LogicalProcessor._parse_condition(df, column, sentencia2)
			values = first_mask.fillna(False) & second_mask.fillna(False)
		elif operation == "or":
			if sentencia2 is None:
				raise ValueError("or requires sentencia2")
			first_mask, _ = LogicalProcessor._parse_condition(df, column, sentencia1)
			second_mask, _ = LogicalProcessor._parse_condition(df, column, sentencia2)
			values = first_mask.fillna(False) | second_mask.fillna(False)
		elif operation == "not":
			first_mask, first_operator = LogicalProcessor._parse_condition(df, column, sentencia1)
			first_mask = first_mask.fillna(False)
			values = ~first_mask
			if first_operator != "isnull":
				values &= df[column].notna()
		elif operation == "elseif":
			if sentencia2 is None:
				raise ValueError("elseif requires sentencia2")
			values, _ = LogicalProcessor._parse_condition(df, column, sentencia2)
			values = values.fillna(False)
		else:
			first_mask, _ = LogicalProcessor._parse_condition(df, column, sentencia1)
			first_mask = first_mask.fillna(False)
			values = first_mask

		return StructuralProcessor.assign_result(
			df,
			column,
			values.astype(bool),
			create_new_column=not reemplazar_campo,
			new_column_name=nombre_nueva_columna if not reemplazar_campo else None,
		)

	@staticmethod
	def and_(
		df: pd.DataFrame, column: str, sentencia1: str, sentencia2: str | None = None,
		reemplazar_campo: bool = True, nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame:
		return LogicalProcessor._logical_result(
			df, "and", column, sentencia1, sentencia2, reemplazar_campo, nombre_nueva_columna,
		)

	@staticmethod
	def case(
		df: pd.DataFrame, column: str, sentencia1: str, sentencia2: str | None = None,
		reemplazar_campo: bool = True, nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame:
		return LogicalProcessor._logical_result(
			df, "case", column, sentencia1, sentencia2, reemplazar_campo, nombre_nueva_columna,
		)

	@staticmethod
	def if_(
		df: pd.DataFrame, column: str, sentencia1: str, sentencia2: str | None = None,
		reemplazar_campo: bool = True, nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame:
		return LogicalProcessor._logical_result(
			df, "if", column, sentencia1, sentencia2, reemplazar_campo, nombre_nueva_columna,
		)

	@staticmethod
	def elseif(
		df: pd.DataFrame, column: str, sentencia1: str, sentencia2: str | None = None,
		reemplazar_campo: bool = True, nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame:
		return LogicalProcessor._logical_result(
			df, "elseif", column, sentencia1, sentencia2, reemplazar_campo, nombre_nueva_columna,
		)

	@staticmethod
	def or_(
		df: pd.DataFrame, column: str, sentencia1: str, sentencia2: str | None = None,
		reemplazar_campo: bool = True, nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame:
		return LogicalProcessor._logical_result(
			df, "or", column, sentencia1, sentencia2, reemplazar_campo, nombre_nueva_columna,
		)

	@staticmethod
	def not_(
		df: pd.DataFrame, column: str, sentencia1: str, sentencia2: str | None = None,
		reemplazar_campo: bool = True, nombre_nueva_columna: str | None = None,
	) -> pd.DataFrame:
		return LogicalProcessor._logical_result(
			df, "not", column, sentencia1, sentencia2, reemplazar_campo, nombre_nueva_columna,
		)

	@staticmethod
	def coalesce(
		df: pd.DataFrame, column: str, default_value: object,
		create_new_column: bool = False, new_column_name: str | None = None,
	) -> pd.DataFrame:
		"""Fill nulls and empty strings, without treating zero/False as missing."""
		values = df[column].replace("", None)
		if default_value is not None:
			values = values.fillna(default_value)
		return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)

	@staticmethod
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
			mask = RowProcessor.condition_mask(df[column], operator, condition_func.get("value"))
		elif callable(condition_func):
			mask = condition_func(df[column].copy())
		else:
			raise ValueError("condition_func must be a callable or an operator/value mapping")
		if not isinstance(mask, pd.Series) or not mask.index.equals(df.index) or not is_bool_dtype(mask.dtype):
			raise ValueError("condition_func must return a boolean Series with the input index")
		values = pd.Series(true_value, index=df.index).where(mask.fillna(False), false_value)
		return StructuralProcessor.assign_result(df, column, values, create_new_column, new_column_name)
