"""Translate a clean DAG into an ordered, serializable logical execution plan."""

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from script_builder.dag.pipeline_graph import collect_nodes, topological_order
from script_builder.ir.catalog import get_operation
from script_builder.ir.validate import parameter_reference, validate_constraints, validate_value
from script_builder.ir.expressions import expression_parameters, parse_expression
from script_builder.ir.targets import validate_target_parameters


@dataclass(frozen=True)
class InputBinding:
	"""An upstream node output or an external dataframe port, never both."""

	node_id: str | None = None
	port_id: str | None = None


@dataclass(frozen=True)
class Step:
	id: str
	operation: str
	inputs: tuple[InputBinding, ...]
	parameters: dict[str, Any]
	expression: dict[str, Any] | None = None


@dataclass(frozen=True)
class ExecutionPlan:
	steps: tuple[Step, ...]
	output_node_ids: tuple[str, ...]
	datasource_port_ids: tuple[str, ...]
	runtime_parameters: tuple[str, ...]
	schema_version: str = "2"
	engine: str = "python"
	framework: str = "pandas"

	def to_dict(self) -> dict[str, Any]:
		"""Return a detached JSON-compatible representation."""
		return json.loads(json.dumps(asdict(self), allow_nan=False))


def _references(value: Any) -> set[str]:
	reference = parameter_reference(value)
	if reference is not None:
		return {reference}
	if isinstance(value, dict):
		return set().union(*(_references(item) for item in value.values()))
	if isinstance(value, list):
		return set().union(*(_references(item) for item in value))
	return set()


def _ports(nodes: Mapping[str, Any], kind: str) -> dict[str, tuple[str, int]]:
	ports: dict[str, tuple[str, int]] = {}
	for node_id, node in nodes.items():
		ordinals: set[int] = set()
		if not isinstance(node.get(kind, []), list):
			raise ValueError(f"Node {node_id!r} {kind} must be a list")
		for port in node.get(kind, []):
			if not isinstance(port, dict):
				raise ValueError(f"Node {node_id!r} has an invalid {kind} port")
			port_id, ordinal = port.get("id"), port.get("ordinal", 0)
			if not isinstance(port_id, str) or not port_id or port_id in ports:
				raise ValueError(f"Invalid or duplicate {kind} port ID {port_id!r}")
			if isinstance(ordinal, bool) or not isinstance(ordinal, int) or ordinal < 0 or ordinal in ordinals:
				raise ValueError(f"Node {node_id!r} has invalid or duplicate {kind} ordinal")
			ports[port_id] = (node_id, ordinal)
			ordinals.add(ordinal)
	return ports


def build_plan(
	pipeline: Mapping[str, Any],
	*,
	engine: str = "python",
	framework: str = "pandas",
) -> ExecutionPlan:
	"""Validate and compile without loading data or importing a dataframe framework."""
	if engine != "python" or framework not in ("pandas", "polars"):
		raise ValueError(f"Unsupported target {engine}/{framework}")
	if not isinstance(pipeline, Mapping):
		raise ValueError("Pipeline must be an object")
	if "nodes" in pipeline:
		declared = pipeline["nodes"]
		if not isinstance(declared, list) or not all(isinstance(node, dict) for node in declared):
			raise ValueError("Pipeline nodes must be a list of objects")
		if any(not isinstance(node.get("id"), str) or not node["id"] for node in declared):
			raise ValueError("Node must have a nonempty string ID")
	if not isinstance(pipeline.get("edges"), list) or not all(isinstance(edge, dict) for edge in pipeline["edges"]):
		raise ValueError("Pipeline edges must be a list of objects")
	nodes = collect_nodes(pipeline)
	if not nodes:
		raise ValueError("Pipeline must contain at least one node")
	if any(not isinstance(node_id, str) or not node_id for node_id in nodes):
		raise ValueError("Node must have a nonempty string ID")
	input_ports = _ports(nodes, "input_ports")
	output_ports = _ports(nodes, "output_ports")
	if any(len(node.get("output_ports", [])) > 1 for node in nodes.values()):
		raise ValueError("This builder supports only one output dataframe per node")
	incoming: dict[str, str] = {}
	has_consumers: set[str] = set()
	for edge in pipeline["edges"]:
		source, target = edge.get("source_node_id"), edge.get("target_node_id")
		if not isinstance(source, str) or not isinstance(target, str) or source not in nodes or target not in nodes:
			raise ValueError(f"Edge {edge.get('id')!r} references an unknown node")
		source_port, target_port = edge.get("source_output_port_id"), edge.get("target_input_port_id")
		if not isinstance(source_port, str) or source_port not in output_ports or output_ports[source_port][0] != source:
			raise ValueError(f"Edge {edge.get('id')!r} has an invalid source port")
		if not isinstance(target_port, str) or target_port not in input_ports or input_ports[target_port][0] != target:
			raise ValueError(f"Edge {edge.get('id')!r} has an invalid target port")
		if target_port in incoming:
			raise ValueError(f"Multiple edges target input port {target_port!r}")
		incoming[target_port] = source
		has_consumers.add(source)
	order = topological_order(dict(sorted(nodes.items())), pipeline["edges"])
	steps = []
	references: set[str] = set()
	for node_id in order:
		node = nodes[node_id]
		operation = node.get("operation")
		if not isinstance(operation, dict) or not isinstance(operation.get("name"), str):
			raise ValueError(f"Node {node_id!r} requires an operation name")
		name = operation["name"].lower()
		spec = get_operation(name)
		if (engine, framework) not in spec.targets:
			raise ValueError(f"Node {node_id!r}: {name} is unsupported on {engine}/{framework}")
		ports = sorted(node.get("input_ports", []), key=lambda port: port.get("ordinal", 0))
		if len(ports) < spec.min_inputs or (spec.max_inputs is not None and len(ports) > spec.max_inputs):
			raise ValueError(f"Node {node_id!r}: {name} has invalid input arity ({len(ports)})")
		raw = node.get("parameters", {})
		if not isinstance(raw, dict):
			raise ValueError(f"Node {node_id!r} parameters must be an object")
		try:
			parameters = json.loads(json.dumps(raw, allow_nan=False, sort_keys=True))
		except (TypeError, ValueError) as error:
			raise ValueError(f"Node {node_id!r} parameters must be finite JSON values") from error
		if name.endswith("_join") and name != "join":
			parameters.setdefault("how", name.removesuffix("_join"))
		if spec.name == "logical" and name != "logical":
			parameters.setdefault("operation", name)
		validate_value(parameters, spec.parameters, f"Node {node_id!r}", allow_references=True)
		expression = None
		if spec.name == "fx":
			expression = parse_expression(parameters["expression"])
			references.update(expression_parameters(expression))
		node_references = _references(parameters)
		if not node_references:
			validate_constraints(spec.name, parameters)
			validate_target_parameters(framework, spec.name, parameters)
		references.update(node_references)
		bindings = tuple(
			InputBinding(node_id=incoming[port["id"]]) if port["id"] in incoming
			else InputBinding(port_id=port["id"])
			for port in ports
		)
		steps.append(Step(node_id, spec.name, bindings, parameters, expression))
	return ExecutionPlan(
		tuple(steps),
		tuple(node_id for node_id in order if node_id not in has_consumers),
		tuple(sorted(set(input_ports) - set(incoming))),
		tuple(sorted(references)),
		engine=engine,
		framework=framework,
	)
