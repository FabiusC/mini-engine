"""Emulates the worker image that runs generated pandas scripts."""

from workers.base import Worker


class PandasWorker(Worker):
	framework = "pandas"
	required_modules = ("pandas", "numpy")
