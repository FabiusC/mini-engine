"""Test helpers: compile tiny DAGs and run the generated script in-process."""

import types
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from script_builder.codegen.pandas import PandasEmitter
from script_builder.codegen.registry import EMITTERS
from script_builder.ir import build_plan


def single_node_pipeline(operation: str, parameters: Mapping[str, Any], inputs: int) -> dict[str, Any]:
	return {
		"nodes": [{
			"id": "op",
			"operation": {"name": operation},
			"parameters": dict(parameters),
			"input_ports": [{"id": f"op_in_{index}", "ordinal": index} for index in range(inputs)],
			"output_ports": [{"id": "op_out", "ordinal": 0}],
		}],
		"edges": [],
	}


def compile_pipeline(pipeline: Mapping[str, Any], framework: str = "pandas") -> types.ModuleType:
	"""Emit the standalone script for ``pipeline`` and load it as a module."""
	source = EMITTERS[framework]().emit(build_plan(pipeline, framework=framework))
	module = types.ModuleType(f"generated_{framework}_pipeline")
	exec(compile(source, module.__name__, "exec"), module.__dict__)
	return module


def run_operation(
	operation: str,
	frames: Sequence[Any],
	parameters: Mapping[str, Any] | None = None,
	*,
	framework: str = "pandas",
	**overrides: Any,
) -> Any:
	"""Run one operation exactly as a worker would: through the generated script."""
	arguments = {
		key: str(value) if isinstance(value, Path) else value
		for key, value in {**(parameters or {}), **overrides}.items()
	}
	module = compile_pipeline(single_node_pipeline(operation, arguments, len(frames)), framework)
	return module.run({f"op_in_{index}": frame for index, frame in enumerate(frames)})["op"]


def reference_run(
	pipeline: Mapping[str, Any],
	datasources: Mapping[str, Any] | None = None,
	*,
	base_dir: str | Path | None = None,
) -> dict[str, Any]:
	"""Call the pandas operation sources directly, without code generation, as a parity oracle."""
	datasources = datasources or {}
	results: dict[str, Any] = {}
	for step in build_plan(pipeline).steps:
		inputs = [
			results[binding.node_id] if binding.node_id is not None else datasources[binding.port_id]
			for binding in step.inputs
		]
		parameters = dict(step.parameters)
		for key in ("filepath", "filepath_or_connection", "output_path"):
			if key == "filepath_or_connection" and parameters.get("source_type") == "sql":
				continue
			value = parameters.get(key)
			if base_dir is not None and isinstance(value, str) and not Path(value).is_absolute():
				parameters[key] = Path(base_dir) / value
		owner, method = PandasEmitter.implementations[step.operation]
		function = getattr(owner(), method)
		results[step.id] = function(inputs, **parameters) if step.operation == "union" else function(*inputs, **parameters)
	return results
