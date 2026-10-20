"""Execute a PipelineDAG built from the saved API responses."""

from collections.abc import Mapping
from typing import Any

import pandas as pd

from tableau_engine.core.dag_graph import OperationNode, PipelineDAG
from tableau_engine.interfaces.row import RowInterface
from tableau_engine.interfaces.structural import StructuralInterface
from tableau_engine.interfaces.text import TextInterface


class DAGRunner:
	"""Resolve input ports and execute operations in the DAG's topological order."""

	_interfaces = {
		"inner_join": StructuralInterface,
		"outer_join": StructuralInterface,
		"limit": RowInterface,
		"filter": RowInterface,
		"upper": TextInterface,
		"lower": TextInterface,
	}

	def __init__(self, dag: PipelineDAG) -> None:
		self.dag = dag

	def run(
		self,
		datasources: Mapping[str, pd.DataFrame],
		parameters: Mapping[str, Mapping[str, Any]] | None = None,
	) -> dict[str, pd.DataFrame]:
		"""Execute nodes using datasource data keyed by unconnected input-port ID."""
		parameters = parameters or {}
		outputs_by_port: dict[str, pd.DataFrame] = {}
		outputs_by_node: dict[str, pd.DataFrame] = {}

		for node in self.dag.nodes:
			input_frames: list[pd.DataFrame] = []
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
								f"Missing datasource for required input port "
								f"{port.port_id!r} on node {node.name!r}"
							)
						continue
				if not isinstance(dataframe, pd.DataFrame):
					raise TypeError(f"Input port {port.port_id!r} must receive a DataFrame")
				input_frames.append(dataframe)

			node_parameters = node.parameters
			if not isinstance(node_parameters, Mapping):
				node_parameters = {}
			resolved_parameters = {**node_parameters, **parameters.get(node.node_id, {})}
			try:
				interface = self._interfaces[node.operation.lower()]
			except KeyError as error:
				raise ValueError(f"Unsupported operation {node.operation!r}") from error
			if interface is StructuralInterface:
				result = interface.execute(node.operation, input_frames, **resolved_parameters)
			else:
				if len(input_frames) != 1:
					raise ValueError(f"{node.name} requires one input dataframe")
				result = interface.execute(
					node.operation, input_frames[0], **resolved_parameters
				)
			outputs_by_node[node.node_id] = result
			for port_id in node.output_port_ids:
				outputs_by_port[port_id] = result
		return outputs_by_node
