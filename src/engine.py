"""Sequential execution engine for dataframe transformation pipelines."""

from dataclasses import dataclass
from typing import Callable

import pandas as pd


PipelineOperation = Callable[..., pd.DataFrame]


@dataclass(frozen=True)
class PipelineState:
	"""Snapshot of the dataframe produced after a pipeline step."""

	step_name: str
	data: pd.DataFrame

	@property
	def row_count(self) -> int:
		"""Number of rows recorded in this state."""
		return len(self.data)

	@property
	def columns(self) -> tuple[str, ...]:
		"""Column names recorded in this state."""
		return tuple(str(column) for column in self.data.columns)


class PipelineEngine:
	"""Register and execute dataframe operations in sequence."""

	def __init__(self, initial_data: pd.DataFrame | None = None) -> None:
		self._initial_data = initial_data.copy() if initial_data is not None else None
		self._steps: list[
			tuple[str, PipelineOperation, tuple[object, ...], dict[str, object]]
		] = []
		self.history: list[PipelineState] = []

	def add_step(
		self,
		name: str,
		operation: PipelineOperation,
		*args: object,
		**kwargs: object,
	) -> "PipelineEngine":
		"""Add an operation, called with the current dataframe as its first argument."""
		self._steps.append((name, operation, args, kwargs))
		return self

	def run(self, data: pd.DataFrame | None = None) -> pd.DataFrame:
		"""Execute all steps and retain a dataframe snapshot after each one."""
		starting_data = data if data is not None else self._initial_data
		if starting_data is None:
			raise ValueError("Provide initial data in the constructor or to run()")

		current_data = starting_data.copy()
		self.history = []
		for step_name, operation, args, kwargs in self._steps:
			current_data = operation(current_data, *args, **kwargs)
			if not isinstance(current_data, pd.DataFrame):
				raise TypeError(f"Pipeline step {step_name!r} did not return a DataFrame")
			self.history.append(PipelineState(step_name, current_data.copy()))
		return current_data
