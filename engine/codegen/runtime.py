"""Launcher helpers copied into generated scripts, not imported by workers."""

import argparse
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from engine.ir.validate import parameter_reference, validate_constraints, validate_value
from engine.ir.targets import validate_target_parameters


def resolve_parameters(value: Any, parameters: Mapping[str, Any]) -> Any:
	reference = parameter_reference(value)
	if reference is not None:
		return parameters[reference]
	if isinstance(value, dict):
		return {key: resolve_parameters(item, parameters) for key, item in value.items()}
	if isinstance(value, list):
		return [resolve_parameters(item, parameters) for item in value]
	return value


def step_parameters(
	stored: dict[str, Any],
	parameters: Mapping[str, Any],
	schema: dict[str, Any],
	operation: str,
	node_id: str,
	base_dir: str | Path | None,
	framework: str = "pandas",
) -> dict[str, Any]:
	resolved = resolve_parameters(stored, parameters)
	validate_value(resolved, schema, f"Node {node_id!r}")
	validate_constraints(operation, resolved)
	validate_target_parameters(framework, operation, resolved)
	for key in ("filepath", "filepath_or_connection", "output_path"):
		if key == "filepath_or_connection" and resolved.get("source_type") == "sql":
			continue
		filepath = resolved.get(key)
		if base_dir is not None and isinstance(filepath, str) and "://" not in filepath and not Path(filepath).is_absolute():
			resolved[key] = Path(base_dir) / filepath
	return resolved


def check_context(
	datasources: Mapping[str, Any],
	parameters: Mapping[str, Any],
	required_ports: tuple[str, ...],
	required_parameters: tuple[str, ...],
	frame_type: type,
) -> None:
	if not isinstance(parameters, Mapping) or not isinstance(datasources, Mapping):
		raise ValueError("parameters and datasources must be mappings")
	if not all(isinstance(name, str) for name in parameters):
		raise ValueError("Runtime parameter names must be strings")
	try:
		json.dumps(dict(parameters), allow_nan=False)
	except (TypeError, ValueError) as error:
		raise ValueError("Runtime parameters must be finite JSON values") from error
	missing = set(required_parameters) - set(parameters)
	unknown = set(parameters) - set(required_parameters)
	if missing or unknown:
		raise ValueError(f"Invalid runtime parameters: missing={sorted(missing)}, unknown={sorted(unknown)}")
	for port_id in required_ports:
		if port_id not in datasources:
			raise ValueError(f"Missing datasource for input port {port_id!r}")
		if not isinstance(datasources[port_id], frame_type):
			raise ValueError(f"Datasource {port_id!r} must be a {frame_type.__name__}")


def script_main(
	run_pipeline: Callable[..., dict[str, Any]],
	read_datasource: Callable[[str | Path], Any] | None = None,
	frame_stats: Callable[[Any], dict[str, int]] | None = None,
) -> None:
	parser = argparse.ArgumentParser(description="Execute a generated pandas pipeline")
	parser.add_argument("--params-file", type=Path)
	parser.add_argument("--datasources-file", type=Path, help="JSON object mapping external port IDs to CSV paths")
	parser.add_argument("--base-dir", type=Path)
	args = parser.parse_args()
	parameters = json.loads(args.params_file.read_text(encoding="utf-8")) if args.params_file else {}
	datasources = {}
	if args.datasources_file:
		if read_datasource is None:
			raise ValueError("This pipeline does not declare external datasources")
		paths = json.loads(args.datasources_file.read_text(encoding="utf-8"))
		if not isinstance(paths, dict) or not all(isinstance(path, str) for path in paths.values()):
			raise ValueError("datasources-file must map port IDs to CSV paths")
		for port_id, path in paths.items():
			filepath = Path(path)
			if args.base_dir is not None and not filepath.is_absolute():
				filepath = args.base_dir / filepath
			datasources[port_id] = read_datasource(filepath)
	results = run_pipeline(datasources=datasources, parameters=parameters, base_dir=args.base_dir)
	print(json.dumps({
		node_id: frame_stats(frame) if frame_stats else {"rows": len(frame), "columns": len(frame.columns)}
		for node_id, frame in results.items()
	}, sort_keys=True))


def _as_series(value: Any, frame: pd.DataFrame) -> pd.Series:
	return value if isinstance(value, pd.Series) else pd.Series(value, index=frame.index)
