"""Small JSON-contract validator shared by compilation and generated scripts."""

from collections.abc import Mapping
from typing import Any


def parameter_reference(value: Any) -> str | None:
	# Returns the parameter name when value is a placeholder {"$param": "name"}, else None; malformed ones raise.
	if isinstance(value, dict) and "$param" in value:
		if set(value) != {"$param"} or not isinstance(value["$param"], str) or not value["$param"]:
			raise ValueError("A parameter reference must be exactly {'$param': '<nonempty name>'}")
		return value["$param"]
	return None


def validate_value(
	value: Any,
	schema: Mapping[str, Any],
	label: str,
	allow_references: bool = False,
) -> None:
	"""Validate the supported JSON Schema subset, optionally accepting placeholders."""
	if allow_references and parameter_reference(value) is not None:
		return
	# allOf: the value must satisfy each sub-schema (the manifest builds these from several usages).
	for constraint in schema.get("allOf", []):
		validate_value(value, constraint, label, allow_references)
	kinds = schema.get("type")
	if isinstance(kinds, str):
		kinds = [kinds]
	# Type check via a lookup table of JSON type -> predicate; bool is excluded from int/number because bool subclasses int.
	matches = {
		"null": value is None,
		"boolean": isinstance(value, bool),
		"integer": isinstance(value, int) and not isinstance(value, bool),
		"number": isinstance(value, (int, float)) and not isinstance(value, bool),
		"string": isinstance(value, str),
		"array": isinstance(value, list),
		"object": isinstance(value, dict),
	}
	if kinds is not None and not any(matches[kind] for kind in kinds):
		raise ValueError(f"{label} must have type {kinds}, received {type(value).__name__}")
	if "enum" in schema and value not in schema["enum"]:
		raise ValueError(f"{label} must be one of {schema['enum']}")
	if isinstance(value, str) and len(value) < schema.get("minLength", 0):
		raise ValueError(f"{label} must be a nonempty string")
	if isinstance(value, (int, float)) and not isinstance(value, bool):
		if "minimum" in schema and value < schema["minimum"]:
			raise ValueError(f"{label} must be >= {schema['minimum']}")
	if isinstance(value, list):
		if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
			raise ValueError(f"{label} has an invalid number of items")
		for index, item in enumerate(value):
			validate_value(item, schema.get("items", {}), f"{label}[{index}]", allow_references)
	if isinstance(value, dict):
		# Objects: check required keys, reject unknown keys when additionalProperties is false, then recurse per key.
		if len(value) < schema.get("minProperties", 0):
			raise ValueError(f"{label} must not be empty")
		for name in schema.get("required", []):
			if name not in value:
				raise ValueError(f"{label} requires parameter {name!r}")
		properties = schema.get("properties", {})
		additional = schema.get("additionalProperties", {})
		for name, item in value.items():
			if name not in properties and additional is False:
				raise ValueError(f"{label} has unknown parameter {name!r}")
			child = properties.get(name, additional if isinstance(additional, dict) else {})
			validate_value(item, child, f"{label}.{name}", allow_references)


def validate_constraints(operation: str, parameters: Mapping[str, Any]) -> None:
	"""Check value relationships not expressible by the basic schema."""
	if operation == "drop_column":
		if (parameters.get("column") is None) == (parameters.get("columns") is None):
			raise ValueError("drop_column requires exactly one of column or columns")
	if operation == "change_data_type":
		new, target = parameters.get("new_type"), parameters.get("target_type")
		if new is None and target is None:
			raise ValueError("change_data_type requires new_type or target_type")
		if new is not None and target is not None and new != target:
			raise ValueError("new_type and target_type must agree")
		if parameters.get("new_column_name") is not None and not parameters.get("create_new_column", False):
			raise ValueError("new_column_name requires create_new_column to be true")
	if operation == "join":
		if (parameters.get("left_on") is None) != (parameters.get("right_on") is None):
			raise ValueError("join requires both left_on and right_on")
	if operation == "input" and parameters.get("source_type") == "sql" and not parameters.get("table_or_sheet"):
		raise ValueError("SQL input requires table_or_sheet")
	if operation == "sample":
		value = parameters["fraction_or_count"]
		if isinstance(value, float) and value > 1:
			raise ValueError("A fraction must be between 0 and 1")
	if operation == "sort" and parameters.get("direction", "asc").lower() not in ("asc", "desc", "des"):
		raise ValueError("direction must be 'asc' or 'desc'")
