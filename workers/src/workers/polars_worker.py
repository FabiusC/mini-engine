"""Emulates the worker image that runs generated polars scripts."""

from workers.base import Worker


class PolarsWorker(Worker):
	framework = "polars"
	required_modules = ("polars",)
