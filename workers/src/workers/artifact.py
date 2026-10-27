"""Read an artifact directory and verify its manifest before anything is executed."""

import hashlib
import json
from pathlib import Path
from typing import Any

ALLOWED_FILES = ("main.py", "pipeline.ipynb")


def load_artifact(directory: str | Path) -> dict[str, Any]:
	"""Return the manifest once every listed file matches its SHA-256 hash."""
	directory = Path(directory)
	manifest_path = directory / "manifest.json"
	if not manifest_path.is_file():
		raise FileNotFoundError(f"No manifest.json in {directory}")
	manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
	if not isinstance(manifest, dict) or manifest.get("manifest_version") != "1":
		raise ValueError("Unsupported artifact manifest")
	if manifest.get("entrypoint") != "main.py":
		raise ValueError("Only main.py entrypoints are supported")
	files = manifest.get("files")
	if not isinstance(files, list) or "main.py" not in [item.get("path") for item in files if isinstance(item, dict)]:
		raise ValueError("Manifest must list main.py")
	for item in files:
		if not isinstance(item, dict) or item.get("path") not in ALLOWED_FILES:
			raise ValueError(f"Unexpected artifact file record: {item!r}")
		content = (directory / item["path"]).read_bytes()
		if hashlib.sha256(content).hexdigest() != item.get("sha256"):
			raise ValueError(f"Artifact integrity check failed: {item['path']}")
	target = manifest.get("target")
	if not isinstance(target, dict) or target.get("engine") != "python":
		raise ValueError("Manifest target must be a python engine")
	return manifest
