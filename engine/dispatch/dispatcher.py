"""Resolve approved runtime profiles and prepare Jobs without contacting Kubernetes."""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from engine.dispatch.artifacts import ArtifactStore, load_manifest
from engine.dispatch.contracts import ExecutionRequest


@dataclass(frozen=True)
class RuntimeProfile:
	image: str
	framework: str
	command: tuple[str, ...] = ("python",)

	def __post_init__(self) -> None:
		expected = ("python",)
		if self.framework not in ("pandas", "polars") or self.command != expected or not self.image:
			raise ValueError("Invalid approved runtime profile")


class Dispatcher:
	"""The submit callback must be idempotent for a deterministic Job name."""

	def __init__(
		self,
		store: ArtifactStore,
		profiles: Mapping[str, RuntimeProfile],
		*,
		namespace: str = "default",
		artifact_root: str = "/artifacts",
		submit: Callable[[dict[str, Any]], None] | None = None,
		worker_secret_name: str | None = None,
	) -> None:
		self.store, self.profiles = store, dict(profiles)
		self.namespace, self.artifact_root, self.submit = namespace, artifact_root, submit
		self.worker_secret_name = worker_secret_name

	def prepare(self, request: ExecutionRequest) -> dict[str, Any]:
		manifest = load_manifest(self.store, request)
		target = manifest.get("target", {})
		profile_id = target.get("runtime_profile")
		profile = self.profiles.get(profile_id)
		if profile is None or profile_id != f"python-{profile.framework}-v1" or target.get("engine") != "python" or target.get("framework") != profile.framework:
			raise ValueError("Artifact target does not match an approved runtime profile")
		return {
			"apiVersion": "batch/v1", "kind": "Job",
			"metadata": {"name": request.job_name, "namespace": self.namespace},
			"spec": {
				"backoffLimit": 0, "activeDeadlineSeconds": 3600,
				"template": {"spec": {
					"restartPolicy": "Never",
					"containers": [{
						"name": "pipeline", "image": profile.image,
						"command": ["python", "-m", "engine.dispatch.worker"],
						"env": [
							{"name": "EXECUTION_REQUEST", "value": json.dumps(request.to_dict(), allow_nan=False)},
							{"name": "RUNTIME_PROFILE", "value": profile_id},
							{"name": "ARTIFACT_ROOT", "value": self.artifact_root},
						],
						"volumeMounts": [{"name": "artifacts", "mountPath": self.artifact_root, "readOnly": True}],
						**({"envFrom": [{"secretRef": {"name": self.worker_secret_name}}]} if self.worker_secret_name else {}),
					}],
					"volumes": [{"name": "artifacts", "persistentVolumeClaim": {"claimName": "pipeline-artifacts"}}],
				}},
			},
		}

	def dispatch(self, request: ExecutionRequest) -> dict[str, Any]:
		job = self.prepare(request)
		if self.submit is None:
			raise RuntimeError("No Kubernetes submit adapter configured; use prepare() for an isolated preview")
		self.submit(job)
		return job
