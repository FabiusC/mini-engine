"""Common worker behaviour: verify the artifact, check the runtime, run main.py in a subprocess."""

import importlib.util
import subprocess
import sys
from pathlib import Path

from workers.artifact import load_artifact


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
