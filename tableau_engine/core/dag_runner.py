"""Topologically execute category-based DAG operations directly."""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from tableau_engine.interfaces.io import IOInterface
from tableau_engine.interfaces.structural import StructuralInterface
from tableau_engine.interfaces.text import TextInterface


class DAGRunner:
	"""Resolve dependencies and dispatch each node through its category interface."""

	_interfaces = {
		"io": IOInterface,
		"input": IOInterface,
		"text": TextInterface,
		"structural": StructuralInterface,
	}

	def __init__(
		self,
		dag_nodes: Mapping[str, object] | None,
		execution_plan: Sequence[Mapping[str, object]],
		outputs: Sequence[str] | None = None,
		base_dir: str | Path | None = None,
	) -> None:
		self.dag_nodes = dict(dag_nodes or {})
		self.execution_plan = list(execution_plan)
		if outputs is not None and not all(
			isinstance(output_id, str) and output_id for output_id in outputs
		):
			raise ValueError("DAG outputs must be non-empty node IDs")
		self.outputs = tuple(outputs or ())
		self.base_dir = Path(base_dir) if base_dir is not None else None
		self._ordered_plan = self._topological_order()

	def _topological_order(self) -> list[Mapping[str, object]]:
		nodes: dict[str, Mapping[str, object]] = {}
		for node in self.execution_plan:
			node_id = node.get("id")
			if not isinstance(node_id, str) or not node_id:
				raise ValueError("Every execution node must have a non-empty string id")
			if node_id in nodes or node_id in self.dag_nodes:
				raise ValueError(f"Duplicate DAG node id: {node_id!r}")
			nodes[node_id] = node

		ordered: list[Mapping[str, object]] = []
		visiting: set[str] = set()
		visited: set[str] = set()

		def visit(node_id: str) -> None:
			if node_id in visiting:
				raise ValueError(f"Cycle detected at DAG node {node_id!r}")
			if node_id in visited:
				return
			if node_id not in nodes:
				if node_id in self.dag_nodes:
					return
				raise ValueError(f"Unknown DAG input node: {node_id!r}")
			visiting.add(node_id)
			inputs = nodes[node_id].get("inputs", [])
			if not isinstance(inputs, list) or not all(
				isinstance(input_id, str) for input_id in inputs
			):
				raise ValueError(f"Inputs for DAG node {node_id!r} must be string IDs")
			for input_id in inputs:
				visit(input_id)
			visiting.remove(node_id)
			visited.add(node_id)
			ordered.append(nodes[node_id])

		for node_id in nodes:
			visit(node_id)
		return ordered

	def _parameters(self, node: Mapping[str, object]) -> dict[str, Any]:
		params = node.get("params", {})
		if not isinstance(params, Mapping):
			raise ValueError(f"Parameters for node {node.get('id')!r} must be an object")
		result = dict(params)
		filepath = result.get("filepath")
		if (
			self.base_dir is not None
			and isinstance(filepath, str)
			and not Path(filepath).is_absolute()
		):
			result["filepath"] = self.base_dir / filepath
		return result

	def run(self) -> dict[str, object]:
		"""Execute the plan and return the full node-result context."""
		for node in self._ordered_plan:
			node_id = node["id"]
			category = node.get("category")
			operation = node.get("operation")
			inputs = node.get("inputs", [])
			if not isinstance(category, str) or not isinstance(operation, str):
				raise ValueError(f"Node {node_id!r} requires category and operation strings")
			if not isinstance(inputs, list):
				raise ValueError(f"Inputs for node {node_id!r} must be a list")
			try:
				interface = self._interfaces[category.lower()]
			except KeyError as error:
				raise ValueError(f"Unknown interface category: {category!r}") from error

			input_dfs = [self.dag_nodes[input_id] for input_id in inputs]
			if not all(isinstance(dataframe, pd.DataFrame) for dataframe in input_dfs):
				raise TypeError(f"Inputs for node {node_id!r} must be dataframes")
			current_df = input_dfs[0] if len(input_dfs) == 1 else None
			params = self._parameters(node)
			if category.lower() == "structural" and len(input_dfs) > 0:
				params["input_dfs"] = input_dfs
			result = interface.execute(operation, current_df, **params)
			if not isinstance(result, pd.DataFrame):
				raise TypeError(f"Node {node_id!r} did not return a DataFrame")
			self.dag_nodes[node_id] = result

		if self.outputs:
			missing_outputs = [node_id for node_id in self.outputs if node_id not in self.dag_nodes]
			if missing_outputs:
				raise ValueError(f"Unknown DAG output node(s): {missing_outputs}")
		return self.dag_nodes

	def to_ast_dict(self) -> dict[str, object]:
		"""Export a generic call/reference AST without using it for execution."""
		outputs = self.outputs or self._terminal_node_ids()
		return {
			"format": "mini-engine.ast",
			"version": 1,
			"nodes": [
				{
					"id": node["id"],
					"type": "call",
					"category": node.get("category"),
					"operation": node.get("operation"),
					"inputs": [{"ref": input_id} for input_id in node.get("inputs", [])],
					"arguments": node.get("params", {}),
				}
				for node in self._ordered_plan
			],
			"outputs": [{"ref": node_id} for node_id in outputs],
		}

	def _terminal_node_ids(self) -> tuple[str, ...]:
		consumed = {
			input_id
			for node in self._ordered_plan
			for input_id in node.get("inputs", [])
		}
		return tuple(
			node["id"] for node in self._ordered_plan if node["id"] not in consumed
		)