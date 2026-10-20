"""Execute a PipelineDAG"""

from collections.abc import Mapping
from typing import Any

import pandas as pd

from tableau_engine.core.dag_graph import OperationNode, PipelineDAG
from tableau_engine.interfaces.row import RowInterface
from tableau_engine.interfaces.structural import StructuralInterface
from tableau_engine.interfaces.text import TextInterface


class DAGRunner:
	"""Run a topologically ordered DAG using datasource frames and node parameters."""

	_interfaces = {
		"inner_join": StructuralInterface,
		"outer_join": StructuralInterface,
		"limit": RowInterface,
		"filter": RowInterface,
		"upper": TextInterface,
		"lower": TextInterface,
	}

	def __init__(self, dag: PipelineDAG) -> None:
		"""Create a runner for an already-built and ordered graph."""
		self.dag = dag

	def _resolve_inputs(
		self,
		node: OperationNode,
		datasources: Mapping[str, pd.DataFrame],
		outputs_by_port: Mapping[str, pd.DataFrame],
	) -> list[pd.DataFrame]:
		"""Resolve each input port from an upstream output or external datasource."""
		input_frames = []
		for port in node.inputs:
			if port.source_port_id is not None:
				if port.source_port_id not in outputs_by_port:
					raise ValueError(
						f"Input {port.port_id!r} is not ready; producer "
						f"{port.source_node_id!r} has not run"
					)
				dataframe = outputs_by_port[port.source_port_id]
			else:
				dataframe = datasources.get(port.port_id)
				if dataframe is None:
					if port.required:
						raise ValueError(
							f"Missing datasource for required input "
							f"{port.port_id!r} on node {node.name!r}"
						)
					continue
			if not isinstance(dataframe, pd.DataFrame):
				raise TypeError(f"Input port {port.port_id!r} must receive a DataFrame")
			input_frames.append(dataframe)
		return input_frames

	def _node_parameters(
		self,
		node: OperationNode,
		overrides: Mapping[str, Mapping[str, Any]],
	) -> dict[str, Any]:
		"""Merge parameters stored on the node with runtime test overrides."""
		stored = node.parameters if isinstance(node.parameters, Mapping) else {}
		return {**stored, **overrides.get(node.node_id, {})}

	def _execute_node(
		self,
		node: OperationNode,
		input_frames: list[pd.DataFrame],
		parameters: Mapping[str, Any],
	) -> pd.DataFrame:
		"""Dispatch one operation through the facade for its category."""
		try:
			interface = self._interfaces[node.operation.lower()]
		except KeyError as error:
			raise ValueError(f"Unsupported operation {node.operation!r}") from error
		if interface is StructuralInterface:
			return interface.execute(node.operation, input_frames, **parameters)
		if len(input_frames) != 1:
			raise ValueError(f"{node.name} requires one input dataframe")
		return interface.execute(node.operation, input_frames[0], **parameters)

	def run(
		self,
		datasources: Mapping[str, pd.DataFrame],
		parameters: Mapping[str, Mapping[str, Any]] | None = None,
	) -> dict[str, pd.DataFrame]:
		"""Run nodes in dependency order and return dataframes keyed by node ID.

		External dataframes are keyed by unconnected input-port ID. Optional parameter
		overrides use node IDs; connected inputs always come from an earlier output port.
		"""
		parameter_overrides = parameters or {}
		outputs_by_port: dict[str, pd.DataFrame] = {}
		outputs_by_node: dict[str, pd.DataFrame] = {}

		for node in self.dag.nodes:
			input_frames = self._resolve_inputs(node, datasources, outputs_by_port)
			node_parameters = self._node_parameters(node, parameter_overrides)
			result = self._execute_node(node, input_frames, node_parameters)
			outputs_by_node[node.node_id] = result
			for port_id in node.output_port_ids:
				outputs_by_port[port_id] = result
		return outputs_by_node
