"""Local emulation of the pandas and polars workers that execute generated scripts."""

from workers.base import Worker
from workers.pandas_worker import PandasWorker
from workers.polars_worker import PolarsWorker

WORKERS: dict[str, type[Worker]] = {"pandas": PandasWorker, "polars": PolarsWorker}

__all__ = ["WORKERS", "PandasWorker", "PolarsWorker", "Worker"]
