"""Explicit compiler targets and approved runtime metadata."""

from script_builder.codegen.polars import PolarsEmitter
from script_builder.codegen.pandas import PandasEmitter

EMITTERS = {
	"pandas": PandasEmitter,
	"polars": PolarsEmitter,
}
