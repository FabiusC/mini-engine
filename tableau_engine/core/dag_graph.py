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
	"""Return the API payload after checking its success envelope."""
	if not isinstance(response, dict) or response.get("success") is not True:
		raise ValueError(f"Invalid {label} API response")
	if "data" not in response:
		raise ValueError(f"{label} API response has no data field")
	return response["data"]


def _index_nodes(raw_nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
	"""Keep active nodes in an ID lookup and reject duplicate IDs."""
	nodes_by_id: dict[str, dict[str, Any]] = {}
	for node in raw_nodes:
		if node.get("is_deleted"):
			continue
		node_id = node["id"]
		if node_id in nodes_by_id:
			raise ValueError(f"Duplicate node ID: {node_id!r}")
		nodes_by_id[node_id] = node
	return nodes_by_id


def _index_ports(
	nodes_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, tuple[str, dict[str, Any]]], dict[str, str]]:
	"""Map input and output port IDs back to their owning nodes."""
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
	return input_ports, output_ports


def _connect_edges(
	raw_edges: list[dict[str, Any]],
	nodes_by_id: dict[str, dict[str, Any]],
	input_ports: dict[str, tuple[str, dict[str, Any]]],
	output_ports: dict[str, str],
) -> dict[str, tuple[str, str]]:
	"""Validate edges and map each target input port to its producer node/port."""
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
	return connections


def _topological_order(
	nodes_by_id: dict[str, dict[str, Any]],
	connections: dict[str, tuple[str, str]],
) -> list[str]:
	"""Return node IDs with every upstream producer before its consumers."""
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
	return ordered_ids


def _build_operation_node(
	node_id: str,
	nodes_by_id: dict[str, dict[str, Any]],
	connections: dict[str, tuple[str, str]],
	operations: dict[str, dict[str, Any]],
) -> OperationNode:
	"""Combine one node snapshot with its operation contract and connected ports."""
	raw_node = nodes_by_id[node_id]
	operation_id = raw_node["operation_id"]
	operation_response = operations.get(operation_id)
	if operation_response is None:
		raise ValueError(f"Missing operation definition {operation_id!r}")
	operation = _response_data(operation_response, f"operation {operation_id}")

	inputs = []
	for port in sorted(raw_node.get("input_ports", []), key=lambda item: item["ordinal"]):
		connection = connections.get(port["id"])
		source_node, source_port = connection if connection else (None, None)
		inputs.append(
			InputPort(
				port_id=port["id"],
				ordinal=port["ordinal"],
				required=port["required"],
				description=port.get("description", ""),
				source_node_id=source_node,
				source_port_id=source_port,
			)
		)
	output_port_ids = tuple(
		port["id"]
		for port in sorted(
			raw_node.get("output_ports", []), key=lambda item: item["ordinal"]
		)
	)
	return OperationNode(
		node_id=node_id,
		name=raw_node["name"],
		operation_id=operation_id,
		operation=operation["name"],
		inputs=tuple(inputs),
		output_port_ids=output_port_ids,
		parameters=raw_node.get("parameters", []),
	)


def build_dag(
	nodes_response: dict[str, Any],
	edges_response: dict[str, Any],
	operations: dict[str, dict[str, Any]],
) -> PipelineDAG:
	"""Build a validated PipelineDAG from API response envelopes.

	The function coordinates four steps: unwrap responses, index nodes/ports,
	validate and connect edges, then build operation nodes in topological order.
	"""
	raw_nodes = _response_data(nodes_response, "nodes")
	raw_edges = _response_data(edges_response, "edges")
	if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
		raise ValueError("Nodes and edges data must be lists")
	nodes_by_id = _index_nodes(raw_nodes)
	input_ports, output_ports = _index_ports(nodes_by_id)
	connections = _connect_edges(raw_edges, nodes_by_id, input_ports, output_ports)
	ordered_ids = _topological_order(nodes_by_id, connections)
	plan = [
		_build_operation_node(node_id, nodes_by_id, connections, operations)
		for node_id in ordered_ids
	]
	return PipelineDAG(tuple(plan))


def load_dag(directory: str | Path) -> PipelineDAG:
	"""Load nodes, edges, and operation snapshots from a directory."""
	root = Path(directory)
	# Nodes and edges define topology; per-operation files define operation behavior.
	nodes_response = json.loads((root / "nodes.json").read_text(encoding="utf-8"))
	edges_response = json.loads((root / "edges.json").read_text(encoding="utf-8"))
	operations = {}
	for path in root.glob("*.json"):
		if path.name in {"nodes.json", "edges.json", "runtime.json"}:
			continue
		response = json.loads(path.read_text(encoding="utf-8"))
		operations[response["data"]["id"]] = response
	return build_dag(nodes_response, edges_response, operations)