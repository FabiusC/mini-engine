"""Emitter for the Polars backend."""

from script_builder.codegen.pandas import PandasEmitter
from script_builder.ir.catalog import POLARS_OPERATIONS
from script_builder.operations.polars import PolarsOperations


def _methods(owner: type, framework: str) -> dict[str, tuple[type, str]]:
	return {
		name: (owner, "round_column" if name == "round" else name)
		for name in POLARS_OPERATIONS
		if name != "fx"
	}


class PolarsEmitter(PandasEmitter):
	framework = "polars"
	implementations = _methods(PolarsOperations, framework)
	backend_imports = "import polars as pl\nimport re\nfrom datetime import date, datetime"
	frame_type = "pl.DataFrame"
	reader = (PolarsOperations, "read_csv")
