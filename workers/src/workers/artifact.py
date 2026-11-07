"""Read an artifact directory and verify its manifest before anything is executed."""

import hashlib
import json
from pathlib import Path
from typing import Any

# Artifact files are plain file names (no directories) with one of these extensions.
ALLOWED_SUFFIXES = (".py", ".ipynb")


def _is_artifact_file(name: Any) -> bool:
	return (
		isinstance(name, str) and Path(name).name == name and "\\" not in name
		and not name.startswith(".") and Path(name).suffix in ALLOWED_SUFFIXES
	)


def load_artifact(directory: str | Path) -> dict[str, Any]:
	"""Return the manifest once every listed file matches its SHA-256 hash."""
	directory = Path(directory)
	manifest_path = directory / "manifest.json"
	if not manifest_path.is_file():
		raise FileNotFoundError(f"No manifest.json in {directory}")
	manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
	if not isinstance(manifest, dict) or manifest.get("manifest_version") != "1":
		raise ValueError("Unsupported artifact manifest")
	# The entrypoint is the generated script, named after the pipeline id (<pipeline_id>.py).
	entrypoint = manifest.get("entrypoint")
	if not _is_artifact_file(entrypoint) or not entrypoint.endswith(".py"):
		raise ValueError(f"Invalid entrypoint: {entrypoint!r}")
	files = manifest.get("files")
	if not isinstance(files, list) or entrypoint not in [item.get("path") for item in files if isinstance(item, dict)]:
		raise ValueError(f"Manifest must list its entrypoint {entrypoint}")
	for item in files:
		if not isinstance(item, dict) or not _is_artifact_file(item.get("path")):
			raise ValueError(f"Unexpected artifact file record: {item!r}")
		# Tolerate CRLF: the files are text, and Windows editors/copy-paste rewrite LF as CRLF. Any other byte must match.
		content = (directory / item["path"]).read_bytes().replace(b"\r\n", b"\n")
		if hashlib.sha256(content).hexdigest() != item.get("sha256"):
			raise ValueError(f"Artifact integrity check failed: {item['path']}")
	input_files = manifest.get("input_files", {})
	if not isinstance(input_files, dict) or not all(
		isinstance(name, str) and isinstance(file_id, str) for name, file_id in input_files.items()
	):
		raise ValueError("Manifest input_files must map parameter names to file ids")
	target = manifest.get("target")
	if not isinstance(target, dict) or target.get("engine") != "python":
		raise ValueError("Manifest target must be a python engine")
	return manifest
