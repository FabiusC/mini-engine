"""Emitter for the Polars backend."""

from engine.codegen.pandas import PandasEmitter
from engine.ir.catalog import POLARS_OPERATIONS
from engine.operations.polars import PolarsOperations


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
