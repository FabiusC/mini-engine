"""Logical operation contracts; no dataframe backend is imported here."""

from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class OperationSpec:
	name: str
	min_inputs: int
	max_inputs: int | None
	parameters: dict[str, Any]
	targets: tuple[tuple[str, str], ...] = (("python", "pandas"),)


def _object(required: dict[str, Any], **optional: dict[str, Any]) -> dict[str, Any]:
	return {
		"type": "object",
		"properties": {**required, **optional},
		"required": list(required),
		"additionalProperties": False,
	}


STRING = {"type": "string", "minLength": 1}
NULLABLE_STRING = {"type": ["string", "null"], "minLength": 1}
STRINGS = {"type": "array", "items": STRING}
KEY = {"type": ["string", "array", "null"], "items": STRING, "minLength": 1}
BOOLEAN = {"type": "boolean"}
ANY = {}


def _enum(*values: str) -> dict[str, Any]:
	return {"type": "string", "enum": list(values)}


_JOIN = _object(
	{},
	how=_enum("inner", "left", "right", "outer", "cross"),
	left_on=KEY,
	right_on=KEY,
	suffixes={"type": "array", "items": {"type": ["string", "null"]}, "minItems": 2, "maxItems": 2},
)

OPERATIONS = {
	spec.name: spec
	for spec in (
		OperationSpec("read_csv", 0, 0, _object({"filepath": STRING})),
		OperationSpec("write_csv", 1, 1, _object({"filepath": STRING}, index=BOOLEAN)),
		OperationSpec("input", 0, 0, _object(
			{"source_type": _enum("csv", "excel", "parquet", "sql"), "filepath_or_connection": STRING},
			table_or_sheet=NULLABLE_STRING, encoding=STRING, delimiter=STRING,
		)),
		OperationSpec("output", 1, 1, _object(
			{"destination_type": _enum("csv", "excel", "parquet"), "output_path": STRING},
			write_mode=_enum("overwrite", "append"), encoding=STRING, delimiter=STRING,
		)),
		OperationSpec("join", 2, 2, _JOIN),
		OperationSpec("union", 2, None, _object({}, match_type=_enum("auto", "manual"))),
		OperationSpec("add_column", 1, 1, _object({"column_name": STRING}, value=ANY)),
		OperationSpec("drop_column", 1, 1, _object({}, column=KEY, columns={**STRINGS, "type": ["array", "null"]})),
		OperationSpec("rename_column", 1, 1, _object({"column": STRING, "new_name": STRING})),
		OperationSpec("change_data_type", 1, 1, _object(
			{"column": STRING}, new_type=NULLABLE_STRING, target_type=NULLABLE_STRING,
			create_new_column=BOOLEAN, new_column_name=NULLABLE_STRING,
		)),
		OperationSpec("aggregate", 1, 1, _object({
			"group_by": STRINGS,
			"aggregations": {
				"type": "object", "minProperties": 1,
				"additionalProperties": {"type": ["string", "array"], "items": STRING, "minLength": 1},
			},
		})),
		OperationSpec("pivot", 1, 1, _object({
			"pivot_type": _enum("columns_to_rows", "rows_to_columns"),
			"index_cols": STRINGS, "target_col": STRING, "values_col": STRING,
		})),
		OperationSpec("filter", 1, 1, _object(
			{"column": STRING, "operator": _enum("==", "!=", ">", "<", ">=", "<=", "contains", "isnull")},
			value=ANY,
		)),
		OperationSpec("limit", 1, 1, _object({"limit": {"type": "integer", "minimum": 0}})),
		OperationSpec("sort", 1, 1, _object({"column": STRING}, direction=STRING)),
		OperationSpec("sample", 1, 1, _object(
			{"sample_type": _enum("head", "random"), "fraction_or_count": {"type": "number", "minimum": 0}},
			random_state={"type": ["integer", "null"]},
		)),
	)
}

# Pandas operations remain the canonical operation surface for both backends.
_COLUMN_OUTPUT = {"create_new_column": BOOLEAN, "new_column_name": NULLABLE_STRING}
_DATE_COLUMN = {"column": STRING}
for _name in ("date", "datetime", "float", "int", "str"):
	OPERATIONS[_name] = OperationSpec(
		_name, 1, 1, _object(_DATE_COLUMN, **_COLUMN_OUTPUT),
	)
for _name, _required in {
	"make_date": {
		"column_day": STRING, "column_month": STRING, "column_year": STRING,
	},
	"make_time": {
		"column_hour": STRING, "column_minute": STRING, "column_second": STRING,
	},
	"make_date_time": {"column_date": STRING, "column_hour": STRING},
}.items():
	OPERATIONS[_name] = OperationSpec(
		_name, 1, 1, _object(_required, new_column_name=NULLABLE_STRING),
	)
for _name, _required in {
	"absolute": {"column": STRING},
	"clean_float": {"column": STRING},
	"ceiling": {"column": STRING},
	"floor": {"column": STRING},
	"power": {"column": STRING, "value": {"type": "number"}},
	"round": {"column": STRING, "decimals": {"type": "integer"}},
}.items():
	OPERATIONS[_name] = OperationSpec(
		_name, 1, 1, _object(_required, **_COLUMN_OUTPUT),
	)
for _name in ("max", "min"):
	OPERATIONS[_name] = OperationSpec(_name, 1, 1, _object({
		"column_a": STRING, "column_b": STRING, "new_column_name": STRING,
	}))
OPERATIONS["arithmetic"] = OperationSpec("arithmetic", 1, 1, _object(
	{"column_a": STRING, "operator": _enum("+", "-", "*", "/"), "column_b_or_value": ANY},
	**_COLUMN_OUTPUT,
))
for _name in ("lowercase", "uppercase", "proper", "propper", "ltrim", "rtrim", "length"):
	OPERATIONS[_name] = OperationSpec(_name, 1, 1, _object(_DATE_COLUMN, **_COLUMN_OUTPUT))
OPERATIONS["trim"] = OperationSpec(
	"trim", 1, 1, _object(_DATE_COLUMN, side=_enum("both", "left", "right"), **_COLUMN_OUTPUT),
)
OPERATIONS["substring"] = OperationSpec("substring", 1, 1, _object(
	{"column": STRING, "start": {"type": "integer"}, "length": {"type": "integer", "minimum": 0}},
	**_COLUMN_OUTPUT,
))
OPERATIONS["replace"] = OperationSpec("replace", 1, 1, _object(
	{"column": STRING, "old_text": STRING, "new_text": STRING}, **_COLUMN_OUTPUT,
))
OPERATIONS["split"] = OperationSpec("split", 1, 1, _object(
	{"column": STRING, "delimiter": STRING},
	index={"type": ["integer", "null"]},
	create_new_column=BOOLEAN,
	new_column_name=NULLABLE_STRING,
))
OPERATIONS["concat_column"] = OperationSpec("concat_column", 1, 1, _object(
	{"columns": {"type": "array", "items": STRING, "minItems": 1}},
	separator=STRING, create_new_column=BOOLEAN, new_column_name=NULLABLE_STRING,
))
OPERATIONS["concat_text"] = OperationSpec("concat_text", 1, 1, _object(
	{"column_name": STRING, "value": STRING}, **_COLUMN_OUTPUT,
))
for _name in ("contains", "starts_with", "ends_with"):
	OPERATIONS[_name] = OperationSpec(_name, 1, 1, _object(
		{"column": STRING, "search_text": STRING}, **_COLUMN_OUTPUT,
	))
for _name in ("transform_left", "transform_right"):
	OPERATIONS[_name] = OperationSpec(_name, 1, 1, _object(
		{"column": STRING, "limit": {"type": "integer", "minimum": 0}},
		**_COLUMN_OUTPUT,
	))

# Aliases are normalized before entering the IR.
ALIASES = {
	"drop-column": "drop_column",
	"rename-column": "rename_column",
	"change-data-type": "change_data_type",
	**{f"{how}_join": "join" for how in ("inner", "outer", "left", "right")},
	"abs": "absolute",
	"upper": "uppercase",
	"lower": "lowercase",
	"dateparse": "date_parse",
	"datetrunc": "date_trunc",
	"ifnull": "coalesce",
}

_OUTPUT_COLUMN = {"create_new_column": BOOLEAN, "new_column_name": NULLABLE_STRING}
for _name in (
	"day", "month", "year", "week", "quarter", "iso_quarter", "iso_week",
	"iso_week_day", "iso_year", "now", "today",
):
	OPERATIONS[_name] = OperationSpec(_name, 1, 1, _object(_DATE_COLUMN, **_OUTPUT_COLUMN))
for _name, _required in {
	"date_parser": {"column": STRING, "date_format": STRING},
	"date_parse": {"column": STRING, "date_format": STRING},
	"date_trunc": {"column": STRING, "part": STRING},
	"date_name": {"column": STRING, "part": STRING},
	"extract_date_part": {"column": STRING, "part": STRING},
	"date_sub": {"column": STRING, "unit": STRING, "amount": {"type": "integer"}},
}.items():
	OPERATIONS[_name] = OperationSpec(_name, 1, 1, _object(_required, **_OUTPUT_COLUMN))
OPERATIONS["date_add"] = OperationSpec("date_add", 1, 1, _object(
	_DATE_COLUMN, unit=NULLABLE_STRING, part=NULLABLE_STRING,
	amount={"type": ["integer", "null"]}, interval={"type": ["integer", "null"]}, **_OUTPUT_COLUMN,
))
OPERATIONS["date_diff"] = OperationSpec("date_diff", 1, 1, _object(
	{"start_column": STRING, "end_column": STRING}, unit=STRING, part=NULLABLE_STRING, **_OUTPUT_COLUMN,
))
OPERATIONS["coalesce"] = OperationSpec("coalesce", 1, 1, _object(
	{"column": STRING, "default_value": ANY}, **_OUTPUT_COLUMN,
))
OPERATIONS["conditional_map"] = OperationSpec("conditional_map", 1, 1, _object({
	"column": STRING,
	"condition_func": _object({"operator": _enum("==", "!=", ">", "<", ">=", "<=", "contains", "isnull")}, value=ANY),
	"true_value": ANY, "false_value": ANY,
}, **_OUTPUT_COLUMN))
OPERATIONS["logical"] = OperationSpec("logical", 1, 1, _object(
	{"operation": _enum("and", "or", "not", "if", "elseif", "case"), "column": STRING, "sentencia1": STRING},
	sentencia2=NULLABLE_STRING, reemplazar_campo=BOOLEAN, nombre_nueva_columna=NULLABLE_STRING,
))
OPERATIONS["fx"] = OperationSpec("fx", 1, 1, _object({"column_name": STRING, "expression": STRING}))
ALIASES.update({
	"function": "fx",
	"datetrunc": "date_trunc", "isoquarter": "iso_quarter", "isoweek": "iso_week",
	"isoweekday": "iso_week_day", "isoyear": "iso_year", "dateadd": "date_add",
	"datediff": "date_diff", "datename": "date_name",
	**{name: "logical" for name in ("and", "or", "not", "if", "elseif", "case")},
})

# Polars implements the same canonical operations as the Pandas compiler.
POLARS_OPERATIONS = set(OPERATIONS)
for _name, _spec in list(OPERATIONS.items()):
	OPERATIONS[_name] = replace(_spec, targets=(
		("python", "pandas"),
		("python", "polars"),
	))


def compatibility_matrix() -> dict[str, dict[str, bool]]:
	return {
		name: {framework: ("python", framework) in spec.targets for framework in ("pandas", "polars")}
		for name, spec in sorted(OPERATIONS.items())
	}


def get_operation(name: str) -> OperationSpec:
	normalized = name.lower()
	try:
		return OPERATIONS[ALIASES.get(normalized, normalized)]
	except KeyError as error:
		raise ValueError(f"Unsupported builder operation {name!r}") from error
