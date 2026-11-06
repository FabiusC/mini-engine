"""Turn saved API responses (pipeline, nodes, edges, operations) into the builder's clean pipeline schema.

No endpoint is ever queried: the responses are read from JSON snapshots in a folder (``dag/`` by default).
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from script_builder.ir.catalog import canonical_parameter_name, get_operation

# Response ``code`` -> snapshot kind. Files are classified by content because their names are not reliable
# (e.g. an "operation-templates-*.json" file may hold an operation). Other codes (templates...) are ignored.
RESPONSE_KINDS = {
	"PIPELINE_RETRIEVED": "pipelines",
	"PIPELINE_NODES_LIST_RETRIEVED": "nodes",
	"PIPELINE_EDGES_LIST_RETRIEVED": "edges",
	"OPERATION_RETRIEVED": "operations",
}
# Typed columns of an API parameter value, in lookup order.
VALUE_FIELDS = ("value_string", "value_text", "value_int", "value_float", "value_bool")
# Operation -> parameter that receives the path of the file referenced by an API "archivo" (file_id) parameter.
FILE_PARAMETERS = {"read_csv": "filepath", "input": "filepath_or_connection"}
# write_csv nodes without a destination write here (relative to the worker's --base-dir).
DEFAULT_WRITE_PATH = "output/{pipeline_id}/{node_id}.csv"
# Written by export_clean_pipeline next to the snapshots; never read back as a snapshot.
CLEAN_FILE_NAME = "pipeline_clean.json"


@dataclass(frozen=True)
class ApiPipeline:
	id: str
	name: str | None
	version_id: str | None
	pipeline: dict[str, Any]


def _records(response: Any, label: str) -> list[dict[str, Any]]:
	"""Normalize an API envelope, one record, or a record list to a list.

	The result is always a list of dictionaries, regardless of the input form.
	"""
	if isinstance(response, Mapping) and "data" in response:
		response = response["data"]
	if response is None:
		return []
	if isinstance(response, Mapping):
		return [dict(response)]
	if isinstance(response, list) and all(isinstance(item, Mapping) for item in response):
		return [dict(item) for item in response]
	raise ValueError(f"{label} must contain an object or a list of objects")


def _typed_value(raw: Any) -> Any:
	"""Unwrap ``{"value_string": ..., "value_bool": ...}`` to its single non-null value; other values pass through."""
	if isinstance(raw, Mapping) and any(field in raw for field in VALUE_FIELDS):
		return next((raw[field] for field in VALUE_FIELDS if raw.get(field) is not None), None)
	return raw


def _ordinal(record: Mapping[str, Any]) -> int:
	return record.get("ordinal") if isinstance(record.get("ordinal"), int) else 0


def _parameter_value(parameter: Mapping[str, Any], node_id: str, operation: str) -> Any:
	items = [item for item in parameter.get("array_items") or [] if not item.get("is_deleted")]
	if items:
		return [_typed_value(item.get("value", item)) for item in sorted(items, key=_ordinal)]
	children = parameter.get("children") or []
	if children:
		return _parameters(children, node_id, operation)
	return _typed_value(parameter.get("value"))


def _parameters(raw: Any, node_id: str, operation: str = "") -> dict[str, Any]:
	"""Keep parameter values typed; normalize API name/value lists to objects with canonical names."""
	if raw is None:
		return {}
	if isinstance(raw, Mapping):
		return dict(raw)
	if not isinstance(raw, list):
		raise ValueError(f"Node {node_id!r} parameters must be an object or a name/value list")
	parameters = {}
	# API format: [{"name": ..., "value": ..., "is_deleted": ...}] -> {name: value}, skipping deleted entries.
	for parameter in raw:
		if not isinstance(parameter, Mapping):
			raise ValueError(f"Node {node_id!r} parameter must be an object")
		if parameter.get("is_deleted"):
			continue
		name = parameter.get("name")
		if not isinstance(name, str) or not name or not (
			"value" in parameter or parameter.get("array_items") or parameter.get("children")
		):
			raise ValueError(f"Node {node_id!r} parameter requires name and value")
		key = canonical_parameter_name(operation, name)
		if key in parameters:
			raise ValueError(f"Node {node_id!r} has duplicate parameter {key!r}")
		value = _parameter_value(parameter, node_id, operation)
		# An empty optional parameter is omitted so the operation default applies.
		if value is None and parameter.get("required") is False:
			continue
		parameters[key] = value
	return parameters


def _canonical_operation(name: str) -> str:
	try:
		return get_operation(name).name
	except ValueError:
		return name  # build_plan reports the unsupported operation with its node id


def merge_pipeline_clean(
	edges_json: Any,
	nodes_json: Any,
	operations_json: Any,
	*,
	version_id: str | None = None,
	pipeline_id: str | None = None,
) -> dict[str, Any]:
	"""Build the runner's nodes/edges schema from API responses.

	``version_id`` keeps only nodes/edges of that pipeline version. ``pipeline_id`` enables the default
	write_csv destination. File references ("archivo") become ``{"$param": "file_<id>"}`` runtime parameters,
	listed in ``input_files`` so the worker can supply their paths.
	"""

	def current(record: Mapping[str, Any]) -> bool:
		return version_id is None or record.get("version_id") in (None, version_id)

	# Index active operations by id, keeping only id and name, so nodes can look up their operation.
	operations = {
		operation.get("id"): {
			"id": operation.get("id"),
			"name": operation.get("name"),
		}
		for operation in _records(operations_json, "operations")
		if operation.get("id") is not None and not operation.get("is_deleted")
	}
	# Pass 1 - nodes: skip deleted/other-version ones (remembering their ids), validate ids/operations.
	nodes: dict[str, dict[str, Any]] = {}
	skipped_nodes = set()
	input_files: dict[str, str] = {}
	for node in _records(nodes_json, "nodes"):
		node_id = node.get("id")
		if node.get("is_deleted") or not current(node):
			skipped_nodes.add(node_id)
			continue
		if not isinstance(node_id, str) or not node_id:
			raise ValueError("Node must have a nonempty string ID")
		if node_id in nodes:
			raise ValueError(f"Duplicate node ID {node_id!r}")
		operation = operations.get(node.get("operation_id"))
		if operation is None or not operation.get("name"):
			raise ValueError(f"Node {node_id!r} references a missing operation {node.get('operation_id')!r}")
		operation_name = _canonical_operation(operation["name"])
		parameters = _parameters(node.get("parameters"), node_id, operation["name"])
		if "file_id" in parameters:
			file_id = parameters.pop("file_id")
			if operation_name not in FILE_PARAMETERS:
				raise ValueError(f"Node {node_id!r}: {operation['name']} does not read files")
			if not isinstance(file_id, str) or not file_id:
				raise ValueError(f"Node {node_id!r} requires a file")
			reference = f"file_{file_id}"
			parameters[FILE_PARAMETERS[operation_name]] = {"$param": reference}
			input_files[reference] = file_id
		if operation_name == "write_csv" and "filepath" not in parameters and pipeline_id:
			parameters["filepath"] = DEFAULT_WRITE_PATH.format(pipeline_id=pipeline_id, node_id=node_id)
		nodes[node_id] = {
			"id": node_id,
			"input_ports": [
				{"id": port.get("id"), "ordinal": _ordinal(port)}
				for port in node.get("input_ports") or []
				if not port.get("is_deleted")
			],
			"output_ports": [
				{"id": port.get("id"), "ordinal": _ordinal(port)}
				for port in node.get("output_ports") or []
				if not port.get("is_deleted")
			],
			"operation": operation,
			"parameters": parameters,
		}
	# Pass 2 - edges: drop deleted/other-version edges and edges touching skipped nodes; other unknown endpoints fail.
	clean_edges = []
	for edge in _records(edges_json, "edges"):
		if edge.get("is_deleted") or not current(edge):
			continue
		source_id = edge.get("source_node_id")
		target_id = edge.get("target_node_id")
		if source_id in skipped_nodes or target_id in skipped_nodes:
			continue
		if source_id not in nodes or target_id not in nodes:
			raise ValueError(f"Edge {edge.get('id')!r} references an unknown node")
		clean_edges.append(
			{
				"id": edge.get("id"),
				"source_node_id": source_id,
				"target_node_id": target_id,
				"source_output_port_id": edge.get("source_output_port_id"),
				"target_input_port_id": edge.get("target_input_port_id"),
			}
		)
	return {"nodes": list(nodes.values()), "edges": clean_edges, "input_files": dict(sorted(input_files.items()))}


def read_snapshots(dag_directory: str | Path) -> dict[str, list[dict[str, Any]]]:
	"""Group every API response saved in ``dag_directory`` by kind (pipelines, nodes, edges, operations)."""
	dag_directory = Path(dag_directory)
	if not dag_directory.is_dir():
		raise FileNotFoundError(f"DAG folder not found: {dag_directory}")
	snapshots: dict[str, list[dict[str, Any]]] = {kind: [] for kind in RESPONSE_KINDS.values()}
	for path in sorted(dag_directory.glob("*.json")):
		if path.name == CLEAN_FILE_NAME:
			continue
		text = path.read_text(encoding="utf-8-sig").strip()
		if not text:
			continue  # an endpoint that returned no body
		try:
			response = json.loads(text)
		except json.JSONDecodeError as error:
			raise ValueError(f"{path.name} is not valid JSON") from error
		kind = RESPONSE_KINDS.get(response.get("code")) if isinstance(response, Mapping) else None
		if kind is None:
			continue
		if response.get("success") is False:
			raise ValueError(f"{path.name} holds an unsuccessful API response: {response.get('message')!r}")
		snapshots[kind].extend(_records(response, path.name))
	return snapshots


def load_api_pipeline(dag_directory: str | Path, pipeline_id: str | None = None) -> ApiPipeline:
	"""Read the snapshots of one pipeline and return its id, current version and clean pipeline."""
	snapshots = read_snapshots(dag_directory)
	pipelines = [item for item in snapshots["pipelines"] if not item.get("is_deleted")]
	available = sorted(str(item.get("id")) for item in pipelines)
	if pipeline_id is not None:
		pipelines = [item for item in pipelines if item.get("id") == pipeline_id]
	if not pipelines:
		raise ValueError(f"No pipeline {pipeline_id or ''} snapshot in {dag_directory} (available: {available})")
	if len(pipelines) > 1:
		raise ValueError(f"Several pipelines in {dag_directory}; choose one with --pipeline-id: {available}")
	metadata = pipelines[0]
	identifier = metadata.get("id")
	if not isinstance(identifier, str) or not identifier:
		raise ValueError("Pipeline snapshot must have a nonempty string ID")
	version_id = metadata.get("current_version_id")
	clean = merge_pipeline_clean(
		snapshots["edges"], snapshots["nodes"], snapshots["operations"],
		version_id=version_id, pipeline_id=identifier,
	)
	if not clean["nodes"]:
		raise ValueError(f"Pipeline {identifier!r} has no nodes for version {version_id!r}")
	return ApiPipeline(identifier, metadata.get("name"), version_id, clean)


def export_clean_pipeline(dag_directory: str | Path, pipeline_id: str | None = None) -> dict[str, Any]:
	"""Offline utility: write the clean pipeline (with its id and version) to ``<dag_directory>/pipeline_clean.json``."""
	api = load_api_pipeline(dag_directory, pipeline_id)
	clean_dag = {"pipeline_id": api.id, "pipeline_version": api.version_id, **api.pipeline}
	(Path(dag_directory) / CLEAN_FILE_NAME).write_text(
		json.dumps(clean_dag, indent=4, ensure_ascii=False) + "\n", encoding="utf-8",
	)
	return clean_dag
