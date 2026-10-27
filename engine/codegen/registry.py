"""Explicit compiler targets and approved runtime metadata."""

from engine.codegen.native import PolarsEmitter, PyArrowEmitter, PySparkEmitter
from engine.codegen.pandas import PandasEmitter

EMITTERS = {
	"pandas": PandasEmitter,
	"polars": PolarsEmitter,
	"pyarrow": PyArrowEmitter,
	"pyspark": PySparkEmitter,
}
