"""Explicit compiler targets and approved runtime metadata."""

from engine.codegen.polars import PolarsEmitter
from engine.codegen.pandas import PandasEmitter

EMITTERS = {
	"pandas": PandasEmitter,
	"polars": PolarsEmitter,
}
