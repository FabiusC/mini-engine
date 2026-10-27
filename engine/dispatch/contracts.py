"""Versioned JSON messages shared by dispatcher and worker launchers."""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class ExecutionRequest:
	execution_id: str
	manifest_uri: str
	manifest_sha256: str
	parameters: dict[str, Any]
	datasources: dict[str, str]
	message_version: str = "1"

	def __post_init__(self) -> None:
		if self.message_version != "1":
			raise ValueError("Unsupported execution message version")
		if not isinstance(self.execution_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", self.execution_id) is None:
			raise ValueError("Invalid execution_id")
		if not isinstance(self.manifest_uri, str) or urlparse(self.manifest_uri).scheme not in ("file", "https", "s3"):
			raise ValueError("manifest_uri must use file, https or s3")
		if not isinstance(self.manifest_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", self.manifest_sha256) is None:
			raise ValueError("manifest_sha256 must be a SHA-256 hex digest")
		if not isinstance(self.parameters, dict) or not all(isinstance(key, str) for key in self.parameters):
			raise ValueError("parameters must be an object with string keys")
		if not isinstance(self.datasources, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in self.datasources.items()):
			raise ValueError("datasources must map port IDs to paths")
		json.dumps(self.to_dict(), allow_nan=False)

	def to_dict(self) -> dict[str, Any]:
		return asdict(self)

	@classmethod
	def from_dict(cls, value: Any) -> "ExecutionRequest":
		fields = {"execution_id", "manifest_uri", "manifest_sha256", "parameters", "datasources", "message_version"}
		if not isinstance(value, dict) or set(value) != fields:
			raise ValueError(f"Execution request must contain exactly {sorted(fields)}")
		return cls(**value)

	@property
	def job_name(self) -> str:
		return "pipeline-" + hashlib.sha256(self.execution_id.encode()).hexdigest()[:40]


def execution_event(request: ExecutionRequest, status: str, *, exit_code: int | None = None) -> dict[str, Any]:
	if status not in ("started", "succeeded", "failed"):
		raise ValueError("Invalid execution status")
	return {
		"message_version": "1", "execution_id": request.execution_id,
		"manifest_sha256": request.manifest_sha256, "status": status, "exit_code": exit_code,
	}
