"""Destination constraints checked both before generation and before execution."""

from collections.abc import Mapping
from typing import Any

RUNTIMES: dict[str, dict[str, Any]] = {
	"pandas": {"requirements": ["pandas>=2.0.0", "openpyxl>=3.1.0", "pyarrow>=12.0.0", "SQLAlchemy>=2.0.0"], "python_requires": ">=3.10"},
	"polars": {"requirements": ["polars>=1.24,<2"], "python_requires": ">=3.10"},
}


def validate_target_parameters(framework: str, operation: str, parameters: Mapping[str, Any]) -> None:
	# pandas supports everything the catalog allows; the checks below restrict other backends (polars).
	if framework == "pandas":
		return
	if operation == "input" and parameters["source_type"] not in ("csv", "parquet"):
		raise ValueError(f"{framework} input supports only csv and parquet")
	if operation == "output":
		if parameters["destination_type"] not in ("csv", "parquet"):
			raise ValueError(f"{framework} output supports only csv and parquet")
		if parameters.get("write_mode", "overwrite") not in ("overwrite", "append"):
			raise ValueError(f"{framework} output supports only overwrite or append")
	if operation in ("input", "output"):
		if parameters.get("encoding", "utf-8").lower() not in ("utf-8", "utf8"):
			raise ValueError(f"{framework} IO requires UTF-8")
		if len(parameters.get("delimiter", ",")) != 1:
			raise ValueError(f"{framework} delimiter must be one character")
	if operation == "write_csv" and parameters.get("index", False):
		raise ValueError(f"{framework} has no pandas index; index=True is unsupported")
	if framework == "polars" and operation == "join":
		if parameters.get("how", "inner") not in ("inner", "left", "right", "outer", "cross"):
			raise ValueError("polars join supports inner, left, right, outer and cross")
	if operation == "change_data_type":
		dtype = parameters.get("target_type") or parameters.get("new_type")
		if dtype not in ("int", "int64", "float", "float64", "str", "string", "bool", "datetime"):
			raise ValueError(f"{framework} unsupported target_type {dtype!r}")
	if operation == "add_column" and isinstance(parameters.get("value"), (list, dict)):
		raise ValueError(f"{framework} add_column requires a scalar literal")
