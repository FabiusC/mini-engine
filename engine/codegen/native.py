"""Native emitters share graph wiring, not dataframe implementations."""

from engine.codegen.native_ops import ArrowOps, PolarsOps, SparkOps, arrow_stats, spark_stats
from engine.codegen.pandas import PandasEmitter
from engine.ir.catalog import NATIVE_OPERATIONS


def _methods(owner: type, framework: str) -> dict[str, tuple[type, str]]:
	return {name: (owner, name) for name in NATIVE_OPERATIONS[framework] if name != "fx"}


class PolarsEmitter(PandasEmitter):
	framework = "polars"
	implementations = _methods(PolarsOps, framework)
	backend_imports = "import polars as pl"
	frame_type = "pl.DataFrame"
	reader = (PolarsOps, "read_csv")


class PySparkEmitter(PandasEmitter):
	framework = "pyspark"
	implementations = _methods(SparkOps, framework)
	backend_imports = "from pyspark.sql import DataFrame, SparkSession, functions as F"
	frame_type = "DataFrame"
	reader = (SparkOps, "read_csv")
	stats = staticmethod(spark_stats)


class PyArrowEmitter(PandasEmitter):
	framework = "pyarrow"
	implementations = _methods(ArrowOps, framework)
	backend_imports = "import pyarrow as pa\nimport pyarrow.compute as pc\nimport pyarrow.csv as pacsv\nimport pyarrow.parquet as pq"
	frame_type = "pa.Table"
	reader = (ArrowOps, "read_csv")
	stats = staticmethod(arrow_stats)
