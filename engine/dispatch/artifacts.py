"""Artifact retrieval is injected; the local adapter enforces an approved root."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

from engine.dispatch.contracts import ExecutionRequest
from engine.ir.validate import validate_value


class ArtifactStore(Protocol):
	def read(self, uri: str) -> bytes: ...


class LocalArtifactStore:
	def __init__(self, root: str | Path) -> None:
		self.root = Path(root).resolve(strict=True)

	def read(self, uri: str) -> bytes:
		parsed = urlparse(uri)
		if parsed.scheme != "file" or parsed.netloc not in ("", "localhost") or parsed.query or parsed.fragment:
			raise ValueError("Local artifact store requires a local file URI")
		path = Path(unquote(parsed.path)).resolve(strict=True)
		if not path.is_relative_to(self.root):
			raise ValueError("Artifact is outside the approved root")
		return path.read_bytes()


def load_manifest(store: ArtifactStore, request: ExecutionRequest) -> dict[str, Any]:
	content = store.read(request.manifest_uri)
	if hashlib.sha256(content).hexdigest() != request.manifest_sha256:
		raise ValueError("Manifest integrity check failed")
	manifest = json.loads(content)
	if not isinstance(manifest, dict) or manifest.get("manifest_version") != "1":
		raise ValueError("Unsupported artifact manifest")
	if manifest.get("entrypoint") != "main.py":
		raise ValueError("Only main.py entrypoints are supported")
	files = manifest.get("files")
	if not isinstance(files, list) or not files:
		raise ValueError("Manifest must contain files")
	names = set()
	for item in files:
		if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
			raise ValueError("Invalid manifest file record")
		if item["path"] not in ("main.py", "pipeline.ipynb") or item["path"] in names:
			raise ValueError("Unexpected or duplicate artifact file")
		if not isinstance(item["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None:
			raise ValueError("Invalid artifact file hash")
		names.add(item["path"])
	if "main.py" not in names:
		raise ValueError("Manifest is missing main.py")
	schema = manifest.get("parameters_schema")
	if not isinstance(schema, dict):
		raise ValueError("Missing parameters_schema")
	validate_value(request.parameters, schema, "Execution parameters")
	if set(request.datasources) != set(manifest.get("datasource_port_ids", [])):
		raise ValueError("External datasource ports do not match the manifest")
	return manifest


def load_files(store: ArtifactStore, request: ExecutionRequest, manifest: dict[str, Any]) -> dict[str, bytes]:
	base = request.manifest_uri.rsplit("/", 1)[0] + "/"
	files = {}
	for item in manifest["files"]:
		content = store.read(base + item["path"])
		if hashlib.sha256(content).hexdigest() != item["sha256"]:
			raise ValueError(f"Artifact integrity check failed: {item['path']}")
		files[item["path"]] = content
	return files
