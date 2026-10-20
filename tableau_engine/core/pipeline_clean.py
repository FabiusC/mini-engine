"""Merge API node, edge, and operation responses into a compact graph."""

from collections.abc import Mapping
from typing import Any


def _records(response: Any, label: str) -> list[dict[str, Any]]:
	"""Normalize an API envelope, one record, or a record list to a list."""
	if isinstance(response, Mapping):
		response = response.get("data", [])
	if response is None:
		return []
	if isinstance(response, Mapping):
		return [dict(response)]
	if isinstance(response, list) and all(isinstance(item, Mapping) for item in response):
		return [dict(item) for item in response]
	raise ValueError(f"{label} must contain an object or a list of objects")


def merge_pipeline_clean(
	edges_json: Mapping[str, Any],
	nodes_json: Mapping[str, Any],
	operations_json: Any,
) -> dict[str, list[dict[str, Any]]]:
	"""Return edges enriched with compact source and target node definitions.

	Each embedded node contains its ID, simplified ports, and the operation ID/name.
	The function does not execute or reorder operations; it only joins API responses.
	"""
	operations = {
		operation.get("id"): {
			"id": operation.get("id"),
			"name": operation.get("name"),
		}
		for operation in _records(operations_json, "operations")
		if operation.get("id") is not None
	}

	nodes: dict[str, dict[str, Any]] = {}
	for node in _records(nodes_json, "nodes"):
		if node.get("is_deleted"):
			continue
		node_id = node.get("id")
		if node_id is None:
			continue
		nodes[node_id] = {
			"id": node_id,
			"input_ports": [
				{
					"id": port.get("id"),
					"description": port.get("description"),
					"ordinal": port.get("ordinal"),
				}
				for port in node.get("input_ports", [])
			],
			"output_ports": [
				{
					"id": port.get("id"),
					"description": port.get("description"),
					"ordinal": port.get("ordinal"),
				}
				for port in node.get("output_ports", [])
			],
			"operation": operations.get(node.get("operation_id")),
		}

	clean_edges = []
	for edge in _records(edges_json, "edges"):
		if edge.get("is_deleted"):
			continue
		source_id = edge.get("source_node_id")
		target_id = edge.get("target_node_id")
		clean_edges.append(
			{
				"id": edge.get("id"),
				"source_node_id": source_id,
				"target_node_id": target_id,
				"source_output_port_id": edge.get("source_output_port_id"),
				"target_input_port_id": edge.get("target_input_port_id"),
				"source_node": nodes.get(source_id),
				"target_node": nodes.get(target_id),
			}
		)
	return {"edges": clean_edges}