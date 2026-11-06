"""Common worker behaviour: verify the artifact, check the runtime, run the generated script in a subprocess."""

import importlib.util
import json
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from workers import settings
from workers.artifact import load_artifact


def write_parameters(
	input_files: Mapping[str, str],
	params_file: str | Path | None,
	directory: Path,
) -> Path:
	"""Add the hardcoded path of every input file to the runtime parameters; explicit parameters win."""
	parameters = json.loads(Path(params_file).read_text(encoding="utf-8")) if params_file is not None else {}
	if not isinstance(parameters, dict):
		raise ValueError("params-file must contain a JSON object")
	for name, file_id in input_files.items():
		if name in parameters:
			continue
		path = settings.input_file_path(file_id).resolve()
		if not path.is_file():
			raise FileNotFoundError(f"Input file {file_id!r} not found at {path} (see workers/src/workers/settings.py)")
		parameters[name] = str(path)
	destination = directory / "params.json"
	destination.write_text(json.dumps(parameters), encoding="utf-8")
	return destination


class Worker:
	"""A worker only runs artifacts generated for its own framework."""

	framework: str = ""
	required_modules: tuple[str, ...] = ()

	def check_runtime(self) -> None:
		missing = [name for name in self.required_modules if importlib.util.find_spec(name) is None]
		if missing:
			raise RuntimeError(f"{self.framework} worker is missing modules: {', '.join(missing)}")

	def run(
		self,
		artifact_dir: str | Path,
		*,
		params_file: str | Path | None = None,
		datasources_file: str | Path | None = None,
		base_dir: str | Path | None = None,
		timeout: float | None = None,
	) -> int:
		"""Return the exit code of the generated script; its stdout/stderr go to the worker logs."""
		artifact_dir = Path(artifact_dir).resolve()
		manifest = load_artifact(artifact_dir)
		framework = manifest["target"].get("framework")
		if framework != self.framework:
			raise ValueError(f"{self.framework} worker cannot run a {framework} artifact")
		self.check_runtime()
		execution = manifest.get("execution", {})
		with tempfile.TemporaryDirectory(prefix="worker-") as scratch:
			# Files referenced by the DAG are read from the paths hardcoded in workers.settings.
			if manifest.get("input_files"):
				params_file = write_parameters(manifest["input_files"], params_file, Path(scratch))
			command = [sys.executable, str(artifact_dir / manifest["entrypoint"])]
			for argument, value in (
				(execution.get("parameters_argument", "--params-file"), params_file),
				(execution.get("datasources_argument", "--datasources-file"), datasources_file),
				(execution.get("base_dir_argument", "--base-dir"), base_dir),
			):
				if value is not None:
					command += [argument, str(Path(value).resolve())]
			# Never use a shell: the command is built only from verified paths.
			return subprocess.run(command, cwd=artifact_dir, timeout=timeout, check=False).returncode
