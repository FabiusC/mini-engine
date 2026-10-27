import json
import re


class PolarsLogicalOperations:
	_CONDITION_PATTERN = re.compile(
		r"^\s*(?P<column>.+?)\s*(?P<operator>==|!=|>=|<=|>|<|contains|isnull)\s*(?P<value>.*?)\s*$",
		re.IGNORECASE,
	)

	def _condition_expr(self, column, operator, value=None):
		item = pl.col(column)
		if operator == "==":
			return item == value
		if operator == "!=":
			return item != value
		if operator == ">":
			return item > value
		if operator == "<":
			return item < value
		if operator == ">=":
			return item >= value
		if operator == "<=":
			return item <= value
		if operator == "contains":
			return item.cast(pl.String).str.contains(str(value), literal=True)
		if operator == "isnull":
			return item.is_null()
		raise ValueError(f"Unsupported filter operator: {operator!r}")

	def _parse_condition(self, column, statement):
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
		return self._condition_expr(column, operator, value), operator

	def logical(
		self, df, operation, column, sentencia1, sentencia2=None,
		reemplazar_campo=True, nombre_nueva_columna=None,
	):
		operators = {"and": "and", "if": "and", "or": "or", "case": "or", "elseif": "or"}
		if operation not in (*operators, "not"):
			raise ValueError(f"Unsupported logical operation: {operation!r}")
		if not isinstance(reemplazar_campo, bool):
			raise ValueError("reemplazar_campo must be a boolean")
		if reemplazar_campo and nombre_nueva_columna is not None:
			raise ValueError("nombre_nueva_columna requires reemplazar_campo to be false")
		if not reemplazar_campo and (not isinstance(nombre_nueva_columna, str) or not nombre_nueva_columna):
			raise ValueError("nombre_nueva_columna is required when reemplazar_campo is false")
		first, first_operator = self._parse_condition(column, sentencia1)
		first = first.fill_null(False)
		if operation == "not":
			values = ~first
			if first_operator != "isnull":
				values = values & pl.col(column).is_not_null()
		else:
			if sentencia2 is None:
				raise ValueError(f"{operation} requires sentencia2")
			second, _ = self._parse_condition(column, sentencia2)
			second = second.fill_null(False)
			values = first & second if operators[operation] == "and" else first | second
		return self.assign_result(
			df, column, values, not reemplazar_campo,
			nombre_nueva_columna if not reemplazar_campo else None,
		)

	def coalesce(self, df, column, default_value, create_new_column=False, new_column_name=None):
		values = pl.col(column)
		if df.schema[column] == pl.String:
			values = pl.when(values == "").then(None).otherwise(values)
		if default_value is not None:
			values = values.fill_null(default_value)
		return self.assign_result(df, column, values, create_new_column, new_column_name)

	def conditional_map(
		self, df, column, condition_func, true_value, false_value,
		create_new_column=False, new_column_name=None,
	):
		if not isinstance(condition_func, dict) or set(condition_func) - {"operator", "value"} or "operator" not in condition_func:
			raise ValueError("condition_func must contain operator and optional value")
		operator = condition_func["operator"]
		if not isinstance(operator, str):
			raise ValueError("condition operator must be a string")
		mask = self._condition_expr(column, operator, condition_func.get("value"))
		values = (
			pl.when(mask.fill_null(False))
			.then(pl.lit(true_value))
			.otherwise(pl.lit(false_value))
		)
		return self.assign_result(df, column, values, create_new_column, new_column_name)
