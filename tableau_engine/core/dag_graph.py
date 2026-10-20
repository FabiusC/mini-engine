"""Build an ordered in-memory DAG from pipeline API response snapshots."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InputPort:
	"""An operation input and the edge connected to it, if any."""

	port_id: str
	ordinal: int
	required: bool
	description: str
	source_node_id: str | None = None
	source_port_id: str | None = None


@dataclass(frozen=True)
class OperationNode:
	"""A pipeline node enriched with its operation definition and inputs."""

	node_id: str
	name: str
	operation_id: str
	operation: str
	inputs: tuple[InputPort, ...]
	output_port_ids: tuple[str, ...]
	parameters: Any


@dataclass(frozen=True)
class PipelineDAG:
	"""A validated, topologically ordered operation graph."""

	nodes: tuple[OperationNode, ...]

	@property
	def missing_inputs(self) -> tuple[tuple[str, InputPort], ...]:
		"""Required input ports that have neither an edge nor a datasource."""
		return tuple(
			(node.node_id, port)
			for node in self.nodes
			for port in node.inputs
			if port.required and port.source_node_id is None
		)


def _response_data(response: Any, label: str) -> Any:
	if not isinstance(response, dict) or response.get("success") is not True:
		raise ValueError(f"Invalid {label} API response")
	if "data" not in response:
		raise ValueError(f"{label} API response has no data field")
	return response["data"]


def build_dag(
	nodes_response: dict[str, Any],
	edges_response: dict[str, Any],
	operations: dict[str, dict[str, Any]],
) -> PipelineDAG:
	"""Connect node ports by edge IDs and topologically order the resulting DAG."""
	raw_nodes = _response_data(nodes_response, "nodes")
	raw_edges = _response_data(edges_response, "edges")
	if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
		raise ValueError("Nodes and edges data must be lists")

	nodes_by_id = {node["id"]: node for node in raw_nodes if not node.get("is_deleted")}
	if len(nodes_by_id) != sum(not node.get("is_deleted") for node in raw_nodes):
		raise ValueError("Node IDs must be unique")

	input_ports: dict[str, tuple[str, dict[str, Any]]] = {}
	output_ports: dict[str, str] = {}
	for node_id, node in nodes_by_id.items():
		for port in node.get("input_ports", []):
			if port["id"] in input_ports:
				raise ValueError(f"Duplicate input port ID: {port['id']!r}")
			input_ports[port["id"]] = (node_id, port)
		for port in node.get("output_ports", []):
			if port["id"] in output_ports:
				raise ValueError(f"Duplicate output port ID: {port['id']!r}")
			output_ports[port["id"]] = node_id

	connections: dict[str, tuple[str, str]] = {}
	for edge in raw_edges:
		if edge.get("is_deleted"):
			continue
		source_node = edge["source_node_id"]
		target_node = edge["target_node_id"]
		source_port = edge["source_output_port_id"]
		target_port = edge["target_input_port_id"]
		if source_node not in nodes_by_id or target_node not in nodes_by_id:
			raise ValueError(f"Edge {edge['id']!r} references an unknown node")
		if output_ports.get(source_port) != source_node:
			raise ValueError(f"Edge {edge['id']!r} references an invalid output port")
		if target_port not in input_ports or input_ports[target_port][0] != target_node:
			raise ValueError(f"Edge {edge['id']!r} references an invalid input port")
		if target_port in connections:
			raise ValueError(f"Input port {target_port!r} has multiple edges")
		connections[target_port] = (source_node, source_port)

	ordered_ids: list[str] = []
	visiting: set[str] = set()
	visited: set[str] = set()

	def visit(node_id: str) -> None:
		if node_id in visiting:
			raise ValueError(f"Cycle detected at node {node_id!r}")
		if node_id in visited:
			return
		visiting.add(node_id)
		for port in nodes_by_id[node_id].get("input_ports", []):
			connection = connections.get(port["id"])
			if connection is not None:
				visit(connection[0])
		visiting.remove(node_id)
		visited.add(node_id)
		ordered_ids.append(node_id)

	for node_id in nodes_by_id:
		visit(node_id)

	plan: list[OperationNode] = []
	for node_id in ordered_ids:
		raw_node = nodes_by_id[node_id]
		operation_id = raw_node["operation_id"]
		operation_response = operations.get(operation_id)
		if operation_response is None:
			raise ValueError(f"Missing operation definition {operation_id!r}")
		operation = _response_data(operation_response, f"operation {operation_id}")
		ports = []
		for port in sorted(raw_node.get("input_ports", []), key=lambda item: item["ordinal"]):
			connection = connections.get(port["id"])
			source_node, source_port = connection if connection else (None, None)
			ports.append(
				InputPort(
					port_id=port["id"],
					ordinal=port["ordinal"],
					required=port["required"],
					description=port.get("description", ""),
					source_node_id=source_node,
					source_port_id=source_port,
				)
			)
		plan.append(
			OperationNode(
				node_id=node_id,
				name=raw_node["name"],
				operation_id=operation_id,
				operation=operation["name"],
				inputs=tuple(ports),
				output_port_ids=tuple(
					port["id"]
					for port in sorted(
						raw_node.get("output_ports", []), key=lambda item: item["ordinal"]
					)
				),
				parameters=raw_node.get("parameters", []),
			)
		)
	return PipelineDAG(tuple(plan))


def load_dag(directory: str | Path) -> PipelineDAG:
	"""Load nodes, edges, and operation snapshots from a directory."""
	root = Path(directory)
	nodes_response = json.loads((root / "nodes.json").read_text(encoding="utf-8"))
	edges_response = json.loads((root / "edges.json").read_text(encoding="utf-8"))
	operations = {}
	for path in root.glob("*.json"):
		if path.name in {"nodes.json", "edges.json", "runtime.json"}:
			continue
		response = json.loads(path.read_text(encoding="utf-8"))
		operations[response["data"]["id"]] = response
	return build_dag(nodes_response, edges_response, operations)