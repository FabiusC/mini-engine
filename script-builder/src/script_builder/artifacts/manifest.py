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
	constraints: dict[str, list[dict[str, Any]]] = {name: [] for name in plan.runtime_parameters}

	def visit(value: Any, schema: dict[str, Any]) -> None:
		reference = parameter_reference(value)
		if reference is not None:
			if schema not in constraints[reference]:
				constraints[reference].append(schema)
		elif isinstance(value, dict):
			for key, item in value.items():
				additional = schema.get("additionalProperties", {})
				child = schema.get("properties", {}).get(key, additional if isinstance(additional, dict) else {})
				visit(item, child)
		elif isinstance(value, list):
			for item in value:
				visit(item, schema.get("items", {}))

	for step in plan.steps:
		visit(step.parameters, OPERATIONS[step.operation].parameters)
		if step.expression is not None:
			for name in expression_parameters(step.expression):
				if not constraints[name]:
					constraints[name].append({})
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
			**RUNTIMES[plan.framework],
		},
		"entrypoint": "main.py",
		"files": [
			{"path": "main.py", "sha256": sha256(script)},
			*([{"path": "pipeline.ipynb", "sha256": sha256(notebook)}] if notebook is not None else []),
		],
		"parameters_schema": parameter_schema(plan),
		"datasource_port_ids": list(plan.datasource_port_ids),
		"output_node_ids": list(plan.output_node_ids),
		"execution": {
			"command": ["python", "main.py"],
			"parameters_argument": "--params-file",
			"datasources_argument": "--datasources-file",
			"base_dir_argument": "--base-dir",
		},
	}
