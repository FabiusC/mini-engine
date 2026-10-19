"""Sequential execution engine for dataframe transformation pipelines."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
from pathlib import Path

import pandas as pd

from src.operations import (
	aggregate_data,
	drop_columns,
	filter_data,
	join_datasets,
	load_csv,
	transform_string,
	union_datasets,
)


PipelineOperation = Callable[..., pd.DataFrame]
GraphOperation = Callable[..., object]


def _union_inputs(*dataframes: pd.DataFrame) -> pd.DataFrame:
	"""Adapt union_datasets to the graph's multi-input operation model."""
	return union_datasets(dataframes)


DEFAULT_GRAPH_OPERATIONS: dict[str, GraphOperation] = {
	"load_csv": load_csv,
	"join_datasets": join_datasets,
	"union_datasets": _union_inputs,
	"aggregate_data": aggregate_data,
	"drop_columns": drop_columns,
	"filter_data": filter_data,
	"transform_string": transform_string,
}


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


@dataclass(frozen=True)
class DAGNode:
	"""An operation in a DAG, connected to its input node identifiers."""

	node_id: str
	operation: str
	inputs: tuple[str, ...]
	parameters: Mapping[str, object]


@dataclass(frozen=True)
class ASTReference:
	"""A reference to the result produced by another AST node."""

	node_id: str


@dataclass(frozen=True)
class ASTNode:
	"""An operation call and references to its input expressions."""

	node_id: str
	operation: str
	inputs: tuple[ASTReference, ...]
	parameters: Mapping[str, object]


@dataclass(frozen=True)
class PipelineAST:
	"""Topologically ordered AST compiled from a DAG."""

	nodes: tuple[ASTNode, ...]
	operations: Mapping[str, GraphOperation]
	outputs: tuple[str, ...]
	base_dir: Path | None = None

	def run(self, output_node_id: str | None = None) -> object:
		"""Evaluate the AST and return the selected node's result."""
		if not self.nodes:
			raise ValueError("Cannot run an empty pipeline AST")

		values: dict[str, object] = {}
		for node in self.nodes:
			try:
				operation = self.operations[node.operation]
			except KeyError as error:
				raise ValueError(
					f"Operation {node.operation!r} is not registered"
				) from error
			arguments = [values[reference.node_id] for reference in node.inputs]
			parameters = dict(node.parameters)
			filepath = parameters.get("filepath")
			if (
				self.base_dir is not None
				and node.operation == "load_csv"
				and isinstance(filepath, (str, Path))
				and not Path(filepath).is_absolute()
			):
				parameters["filepath"] = self.base_dir / filepath
			values[node.node_id] = operation(*arguments, **parameters)

		if output_node_id is not None:
			if output_node_id not in values:
				raise ValueError(f"Unknown AST output node {output_node_id!r}")
			return values[output_node_id]
		if len(self.outputs) == 1:
			return values[self.outputs[0]]
		return {node_id: values[node_id] for node_id in self.outputs}

	def to_dict(self) -> dict[str, object]:
		"""Serialize the AST to a generic, JSON-compatible call/reference format."""
		return {
			"format": "mini-engine.ast",
			"version": 1,
			"nodes": [
				{
					"id": node.node_id,
					"type": "call",
					"operation": node.operation,
					"inputs": [
						{"ref": reference.node_id} for reference in node.inputs
					],
					"arguments": _json_value(dict(node.parameters)),
				}
				for node in self.nodes
			],
			"outputs": [{"ref": node_id} for node_id in self.outputs],
		}

	def to_json(self, indent: int = 2) -> str:
		"""Return this AST as formatted JSON text."""
		return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class DAG:
	"""Editable directed acyclic graph that compiles into an executable AST."""

	def __init__(
		self,
		operations: Mapping[str, GraphOperation] | None = None,
		base_dir: str | Path | None = None,
	) -> None:
		self._operations = {**DEFAULT_GRAPH_OPERATIONS, **(operations or {})}
		self._nodes: dict[str, DAGNode] = {}
		self._base_dir = Path(base_dir) if base_dir is not None else None

	@property
	def nodes(self) -> tuple[DAGNode, ...]:
		"""Return the graph nodes in insertion order."""
		return tuple(self._nodes.values())

	@property
	def output_node_ids(self) -> tuple[str, ...]:
		"""Return graph nodes that are not consumed by another node."""
		input_ids = {
			input_id for node in self._nodes.values() for input_id in node.inputs
		}
		return tuple(node_id for node_id in self._nodes if node_id not in input_ids)

	def add_node(
		self,
		node_id: str,
		operation: str,
		inputs: Sequence[str] = (),
		**parameters: object,
	) -> DAGNode:
		"""Add a node whose inputs must already exist in the graph."""
		if node_id in self._nodes:
			raise ValueError(f"DAG node {node_id!r} already exists")
		if operation not in self._operations:
			raise ValueError(f"Operation {operation!r} is not registered")
		missing_inputs = [input_id for input_id in inputs if input_id not in self._nodes]
		if missing_inputs:
			raise ValueError(f"Unknown DAG input node(s): {missing_inputs}")
		node = DAGNode(node_id, operation, tuple(inputs), dict(parameters))
		self._nodes[node_id] = node
		return node

	def update_operation(
		self,
		node_id: str,
		operation: str,
		**parameters: object,
	) -> DAGNode:
		"""Replace a node's operation and its parameters without changing its edges."""
		if node_id not in self._nodes:
			raise ValueError(f"Unknown DAG node {node_id!r}")
		if operation not in self._operations:
			raise ValueError(f"Operation {operation!r} is not registered")
		previous = self._nodes[node_id]
		updated = DAGNode(node_id, operation, previous.inputs, dict(parameters))
		self._nodes[node_id] = updated
		return updated

	def set_inputs(self, node_id: str, inputs: Sequence[str]) -> DAGNode:
		"""Replace a node's incoming edges while rejecting cycles and missing nodes."""
		if node_id not in self._nodes:
			raise ValueError(f"Unknown DAG node {node_id!r}")
		missing_inputs = [input_id for input_id in inputs if input_id not in self._nodes]
		if missing_inputs:
			raise ValueError(f"Unknown DAG input node(s): {missing_inputs}")

		previous = self._nodes[node_id]
		self._nodes[node_id] = DAGNode(
			node_id, previous.operation, tuple(inputs), dict(previous.parameters)
		)
		try:
			self._topological_order()
		except ValueError:
			self._nodes[node_id] = previous
			raise
		return self._nodes[node_id]

	def _topological_order(self) -> list[DAGNode]:
		ordered: list[DAGNode] = []
		visiting: set[str] = set()
		visited: set[str] = set()

		def visit(node_id: str) -> None:
			if node_id in visiting:
				raise ValueError(f"Cycle detected at DAG node {node_id!r}")
			if node_id in visited:
				return
			if node_id not in self._nodes:
				raise ValueError(f"Unknown DAG node {node_id!r}")
			visiting.add(node_id)
			node = self._nodes[node_id]
			for input_id in node.inputs:
				visit(input_id)
			visiting.remove(node_id)
			visited.add(node_id)
			ordered.append(node)

		for node_id in self._nodes:
			visit(node_id)
		return ordered

	def to_ast(self) -> PipelineAST:
		"""Compile graph nodes into topologically ordered AST operation calls."""
		ast_nodes = tuple(
			ASTNode(
				node_id=node.node_id,
				operation=node.operation,
				inputs=tuple(ASTReference(input_id) for input_id in node.inputs),
				parameters=dict(node.parameters),
			)
			for node in self._topological_order()
		)
		return PipelineAST(
			ast_nodes, dict(self._operations), self.output_node_ids, self._base_dir
		)

	def to_dict(self) -> dict[str, object]:
		"""Serialize the DAG definition to a generic, JSON-compatible format."""
		return {
			"format": "mini-engine.dag",
			"version": 1,
			"nodes": [
				{
					"id": node.node_id,
					"operation": node.operation,
					"inputs": list(node.inputs),
					"parameters": _json_value(dict(node.parameters)),
				}
				for node in self.nodes
			],
			"outputs": list(self.output_node_ids),
		}

	def to_json(self, indent: int = 2) -> str:
		"""Return this DAG as formatted JSON text."""
		return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

	@classmethod
	def from_dict(
		cls,
		definition: Mapping[str, object],
		operations: Mapping[str, GraphOperation] | None = None,
		base_dir: str | Path | None = None,
	) -> "DAG":
		"""Build a DAG from its JSON-compatible definition."""
		if definition.get("format") != "mini-engine.dag":
			raise ValueError("Unsupported or missing DAG format")
		if definition.get("version") != 1:
			raise ValueError("Unsupported DAG format version")
		nodes = definition.get("nodes")
		if not isinstance(nodes, list):
			raise ValueError("DAG definition must contain a nodes list")

		graph = cls(operations, base_dir=base_dir)
		for raw_node in nodes:
			if not isinstance(raw_node, Mapping):
				raise ValueError("Each DAG node must be an object")
			node_id = raw_node.get("id")
			operation = raw_node.get("operation")
			inputs = raw_node.get("inputs", [])
			parameters = raw_node.get("parameters", {})
			if not isinstance(node_id, str) or not isinstance(operation, str):
				raise ValueError("Each DAG node must have string id and operation fields")
			if not isinstance(inputs, list) or not all(
				isinstance(input_id, str) for input_id in inputs
			):
				raise ValueError(f"Inputs for DAG node {node_id!r} must be string IDs")
			if not isinstance(parameters, Mapping):
				raise ValueError(f"Parameters for DAG node {node_id!r} must be an object")
			graph.add_node(
				node_id,
				operation,
				inputs=inputs,
				**dict(parameters),
			)
		declared_outputs = definition.get("outputs")
		if declared_outputs is not None:
			if not isinstance(declared_outputs, list) or not all(
				isinstance(output_id, str) for output_id in declared_outputs
			):
				raise ValueError("DAG outputs must be a list of node IDs")
			if tuple(declared_outputs) != graph.output_node_ids:
				raise ValueError("DAG outputs must match the graph's terminal nodes")
		return graph

	@classmethod
	def from_json(
		cls,
		json_text: str,
		operations: Mapping[str, GraphOperation] | None = None,
		base_dir: str | Path | None = None,
	) -> "DAG":
		"""Parse JSON text and construct its DAG."""
		definition = json.loads(json_text)
		if not isinstance(definition, Mapping):
			raise ValueError("DAG JSON must contain an object")
		return cls.from_dict(definition, operations=operations, base_dir=base_dir)

	def run(self, output_node_id: str | None = None) -> object:
		"""Compile the current graph and evaluate its AST."""
		return self.to_ast().run(output_node_id)


def _json_value(value: object) -> object:
	"""Convert common Python containers and paths to JSON-compatible values."""
	if isinstance(value, Path):
		return str(value)
	if isinstance(value, Mapping):
		return {str(key): _json_value(item) for key, item in value.items()}
	if isinstance(value, (list, tuple)):
		return [_json_value(item) for item in value]
	if value is None or isinstance(value, (str, int, float, bool)):
		return value
	raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")
