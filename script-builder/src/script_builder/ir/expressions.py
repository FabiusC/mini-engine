"""Parse a bounded expression language and render native dataframe expressions."""

import ast
import math
from typing import Any


_BINARY = {
	ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
	ast.Mod: "%", ast.Pow: "**",
}
_COMPARE = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
_CALLS = {"abs": 1, "upper": 1, "lower": 1, "is_null": 1, "coalesce": 2, "year": 1, "month": 1, "day": 1}


def parse_expression(source: str) -> dict[str, Any]:
	"""Only literal values, explicit col/param calls and allowlisted operators."""
	if not isinstance(source, str) or not source or len(source) > 4096:
		raise ValueError("expression must be a nonempty string of at most 4096 characters")
	try:
		tree = ast.parse(source, mode="eval")
	except (SyntaxError, RecursionError) as error:
		raise ValueError("Invalid expression syntax") from error
	if sum(1 for _ in ast.walk(tree)) > 256:
		raise ValueError("Expression is too complex")

	def convert(node: ast.AST) -> dict[str, Any]:
		if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, float, bool, type(None))):
			if isinstance(node.value, float) and not math.isfinite(node.value):
				raise ValueError("Expression literals must be finite")
			return {"kind": "literal", "value": node.value}
		if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
			name = node.func.id
			if name in ("col", "param") and len(node.args) == 1:
				arg = node.args[0]
				if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value:
					return {"kind": name, "name": arg.value}
			if name in _CALLS and len(node.args) == _CALLS[name]:
				return {"kind": "call", "name": name, "args": [convert(arg) for arg in node.args]}
		if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
			return {"kind": "binary", "op": _BINARY[type(node.op)], "args": [convert(node.left), convert(node.right)]}
		if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _COMPARE:
			return {"kind": "binary", "op": _COMPARE[type(node.ops[0])], "args": [convert(node.left), convert(node.comparators[0])]}
		if isinstance(node, ast.BoolOp):
			return {"kind": "boolean", "op": "and" if isinstance(node.op, ast.And) else "or", "args": [convert(arg) for arg in node.values]}
		if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub, ast.UAdd)):
			return {"kind": "unary", "op": "not" if isinstance(node.op, ast.Not) else "-" if isinstance(node.op, ast.USub) else "+", "args": [convert(node.operand)]}
		if isinstance(node, ast.IfExp):
			return {"kind": "if", "args": [convert(node.test), convert(node.body), convert(node.orelse)]}
		raise ValueError(f"Forbidden expression syntax: {type(node).__name__}")

	return convert(tree.body)


def expression_parameters(tree: dict[str, Any]) -> set[str]:
	if tree["kind"] == "param":
		return {tree["name"]}
	return set().union(*(expression_parameters(arg) for arg in tree.get("args", [])))


def render_expression(tree: dict[str, Any], framework: str, frame: str) -> str:
	"""Render trusted syntax only; names and values are always quoted literals."""
	kind = tree["kind"]
	if kind in ("literal", "param"):
		value = repr(tree["value"]) if kind == "literal" else f"parameters[{tree['name']!r}]"
		return value if framework == "pandas" else f"pl.lit({value})" if framework == "polars" else f"F.lit({value})"
	if kind == "col":
		name = tree["name"]
		if framework == "pandas":
			return f"{frame}[{name!r}]"
		return f"pl.col({name!r})" if framework == "polars" else f"{frame}[{name!r}]"
	args = [render_expression(arg, framework, frame) for arg in tree["args"]]
	if kind in ("binary", "boolean"):
		op = tree["op"] if kind == "binary" else "&" if tree["op"] == "and" else "|"
		return "(" + f" {op} ".join(f"({arg})" for arg in args) + ")"
	if kind == "unary":
		op = "~" if tree["op"] == "not" else tree["op"]
		if framework == "pandas" and tree["op"] == "not":
			return f"(~_as_series({args[0]}, {frame}).astype('boolean'))"
		return f"({op}({args[0]}))"
	if kind == "if":
		if framework == "pandas":
			return f"_as_series({args[1]}, {frame}).where(_as_series({args[0]}, {frame}).fillna(False), {args[2]})"
		if framework == "polars":
			return f"pl.when({args[0]}).then({args[1]}).otherwise({args[2]})"
		return f"F.when({args[0]}, {args[1]}).otherwise({args[2]})"
	name = tree["name"]
	value = args[0]
	if name == "abs":
		return f"abs({value})" if framework == "pandas" else f"({value}).abs()" if framework == "polars" else f"F.abs({value})"
	if name in ("upper", "lower"):
		if framework == "pandas":
			return f"_as_series({value}, {frame}).astype('string').str.{name}()"
		if framework == "polars":
			return f"({value}).str.to_{'uppercase' if name == 'upper' else 'lowercase'}()"
		return f"F.{name}({value})"
	if name == "is_null":
		return f"pd.isna({value})" if framework == "pandas" else f"({value}).is_null()" if framework == "polars" else f"({value}).isNull()"
	if name == "coalesce":
		return f"_as_series({value}, {frame}).fillna({args[1]})" if framework == "pandas" else f"pl.coalesce({', '.join(args)})" if framework == "polars" else f"F.coalesce({', '.join(args)})"
	if name in ("year", "month", "day"):
		if framework == "pandas":
			return f"pd.to_datetime(_as_series({value}, {frame}), errors='raise').dt.{name}"
		if framework == "polars":
			return f"({value}).cast(pl.String).str.to_datetime(strict=True).dt.{name}()"
		return f"F.{'dayofmonth' if name == 'day' else name}(F.to_timestamp({value}))"
	raise ValueError(f"Unsupported expression function {name!r}")
