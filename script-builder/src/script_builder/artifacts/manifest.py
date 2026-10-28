"""Describe generated code, required inputs and the approved runtime profile."""

import hashlib
import json
from typing import Any

from script_builder.ir.catalog import OPERATIONS
from script_builder.ir.plan import ExecutionPlan
from script_builder.ir.validate import parameter_reference
from script_builder.ir.targets import RUNTIMES
from script_builder.ir.expressions import expression_parameters


def sha256(content: str) -> str:
	return hashlib.sha256(content.encode("utf-8")).hexdigest()


def parameter_schema(plan: ExecutionPlan) -> dict[str, Any]:
	# One list of constraints per runtime parameter, collected from every place it is referenced.
	constraints: dict[str, list[dict[str, Any]]] = {name: [] for name in plan.runtime_parameters}

	def visit(value: Any, schema: dict[str, Any]) -> None:
		# Walks a parameter value and its schema in parallel; when it finds {"$param": name}, the sub-schema at
		# that position becomes a constraint for `name` (e.g. a column parameter must be a string).
		reference = parameter_reference(value)
		if reference is not None:
			if schema not in constraints[reference]:
				constraints[reference].append(schema)
		elif isinstance(value, dict):
			for key, item in value.items():
				# Child schema: declared property, else additionalProperties when it is a schema, else unconstrained.
				additional = schema.get("additionalProperties", {})
				child = schema.get("properties", {}).get(key, additional if isinstance(additional, dict) else {})
				visit(item, child)
		elif isinstance(value, list):
			for item in value:
				visit(item, schema.get("items", {}))

	# Visit every step's parameters against its operation schema; fx expressions carry params too.
	for step in plan.steps:
		visit(step.parameters, OPERATIONS[step.operation].parameters)
		if step.expression is not None:
			for name in expression_parameters(step.expression):
				# An expression param has no schema; an empty one still registers the name.
				if not constraints[name]:
					constraints[name].append({})
	# allOf: a value must satisfy every constraint gathered for its parameter.
	return {
		"type": "object",
		"properties": {name: {"allOf": schemas} for name, schemas in constraints.items()},
		"required": list(plan.runtime_parameters),
		"additionalProperties": False,
	}


def build_manifest(
	plan: ExecutionPlan,
	script: str,
	*,
	pipeline_id: str,
	pipeline_version: str,
	notebook: str | None = None,
) -> dict[str, Any]:
	if not isinstance(pipeline_id, str) or not pipeline_id:
		raise ValueError("pipeline_id must be a nonempty string")
	if not isinstance(pipeline_version, str) or not pipeline_version:
		raise ValueError("pipeline_version must be a nonempty string")
	# Hash of the canonical (sorted keys, compact separators) plan JSON, so equal plans always give equal hashes.
	return {
		"manifest_version": "1",
		"pipeline_id": pipeline_id,
		"pipeline_version": pipeline_version,
		"plan_schema_version": plan.schema_version,
		"plan_hash": sha256(json.dumps(plan.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)),
		"target": {
			"engine": plan.engine,
			"framework": plan.framework,
			"runtime_profile": f"python-{plan.framework}-v1",
			**RUNTIMES[plan.framework],  # adds requirements and python_requires for the worker
		},
		"entrypoint": "main.py",
		"files": [
			{"path": "main.py", "sha256": sha256(script)},
			# The notebook entry is added only when a notebook was generated.
			*([{"path": "pipeline.ipynb", "sha256": sha256(notebook)}] if notebook is not None else []),
		],
		"parameters_schema": parameter_schema(plan),
		"datasource_port_ids": list(plan.datasource_port_ids),
		"output_node_ids": list(plan.output_node_ids),
		# How a worker must launch the script: command plus the CLI flags handled by runtime.script_main.
		"execution": {
			"command": ["python", "main.py"],
			"parameters_argument": "--params-file",
			"datasources_argument": "--datasources-file",
			"base_dir_argument": "--base-dir",
		},
	}
