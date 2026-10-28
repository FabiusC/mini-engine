"""Explicit compiler targets and approved runtime metadata."""

from script_builder.codegen.polars import PolarsEmitter
from script_builder.codegen.pandas import PandasEmitter

# Maps the --framework value to the emitter class that renders its script.
EMITTERS = {
	"pandas": PandasEmitter,
	"polars": PolarsEmitter,
}
