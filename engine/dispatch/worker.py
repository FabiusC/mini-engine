"""Small launcher for an approved worker image; no operation implementations."""

import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from engine.dispatch.artifacts import ArtifactStore, LocalArtifactStore, load_files, load_manifest
from engine.dispatch.contracts import ExecutionRequest, execution_event


def execute(
	request: ExecutionRequest,
	store: ArtifactStore,
	runtime_profile: str,
	*,
	publish_event: Callable[[dict[str, Any]], None],
	base_dir: str | Path | None = None,
	timeout: float = 3500,
) -> int:
	"""Verify every byte before spawning; errors propagate after a failure event."""
	terminal = False
	try:
		manifest = load_manifest(store, request)
		target = manifest.get("target", {})
		framework = target.get("framework")
		if framework not in ("pandas", "polars", "pyarrow", "pyspark") or target.get("engine") != "python":
			raise ValueError("Unsupported worker runtime")
		if target.get("runtime_profile") != runtime_profile or runtime_profile != f"python-{framework}-v1":
			raise ValueError("Worker runtime does not match the artifact")
		files = load_files(store, request, manifest)
		publish_event(execution_event(request, "started"))
		with tempfile.TemporaryDirectory(prefix="pipeline-") as directory:
			path = Path(directory)
			for name, content in files.items():
				(path / name).write_bytes(content)
			(path / "params.json").write_text(json.dumps(request.parameters, allow_nan=False))
			(path / "datasources.json").write_text(json.dumps(request.datasources))
			executable = "spark-submit" if framework == "pyspark" else "python"
			command = [
				executable, str(path / "main.py"), "--params-file", str(path / "params.json"),
			]
			if request.datasources:
				command += ["--datasources-file", str(path / "datasources.json")]
			if base_dir is not None:
				command += ["--base-dir", str(Path(base_dir).resolve())]
			# Stream stdout/stderr to the worker logs; never use a shell or the manifest command.
			completed = subprocess.run(command, cwd=path, timeout=timeout, check=False)
		terminal = True
		publish_event(execution_event(request, "succeeded" if completed.returncode == 0 else "failed", exit_code=completed.returncode))
		return completed.returncode
	finally:
		if not terminal:
			publish_event(execution_event(request, "failed"))


def main() -> None:
	request = ExecutionRequest.from_dict(json.loads(os.environ["EXECUTION_REQUEST"]))
	publish_event: Callable[[dict[str, Any]], None]
	if os.environ.get("KAFKA_EVENTS_TOPIC"):
		from engine.dispatch.kafka import KafkaPublisher, kafka_config_from_env
		publisher = KafkaPublisher(kafka_config_from_env(), os.environ["KAFKA_EVENTS_TOPIC"])
		publish_event = lambda event: publisher.publish(request.execution_id, event)
	else:
		publish_event = lambda event: print(json.dumps(event), flush=True)
	code = execute(
		request, LocalArtifactStore(os.environ["ARTIFACT_ROOT"]), os.environ["RUNTIME_PROFILE"],
		publish_event=publish_event, base_dir=os.environ.get("PIPELINE_BASE_DIR"),
	)
	raise SystemExit(code)


if __name__ == "__main__":
	main()
