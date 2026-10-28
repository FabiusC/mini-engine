"""Build an immutable local artifact ready for publication to workers."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from script_builder.artifacts.manifest import build_manifest
from script_builder.codegen.registry import EMITTERS
from script_builder.codegen.notebook import emit_notebook
from script_builder.ir.plan import build_plan


def build_artifact(
	pipeline: Mapping[str, Any],
	output_dir: str | Path,
	*,
	pipeline_id: str,
	pipeline_version: str,
	engine: str = "python",
	framework: str = "pandas",
	notebook: bool = False,
	overwrite: bool = False,
) -> dict[str, Any]:
	"""Validate before writing; an existing artifact is replaced only with ``overwrite``."""
	# 1. Validate the DAG and compile it into an ordered, backend-independent plan (nothing is written yet).
	plan = build_plan(pipeline, engine=engine, framework=framework)
	# 2. Pick the emitter class for the framework (pandas/polars) and render the standalone Python source.
	script = EMITTERS[framework]().emit(plan)
	# 3. Optionally derive a notebook from the same script.
	notebook_source = emit_notebook(script, framework) if notebook else None
	# 4. Describe the artifact (hashes, parameter schema, runtime requirements).
	manifest = build_manifest(
		plan, script, pipeline_id=pipeline_id, pipeline_version=pipeline_version, notebook=notebook_source,
	)
	# 5. Write to disk; exist_ok is only true when overwrite is requested, so an existing artifact raises otherwise.
	directory = Path(output_dir)
	directory.mkdir(parents=True, exist_ok=overwrite)
	# Remove the publication marker first so a partially replaced artifact is never seen as complete.
	for name in ("manifest.json", "main.py", "pipeline.ipynb"):
		(directory / name).unlink(missing_ok=True)
	(directory / "main.py").write_bytes(script.encode("utf-8"))
	if notebook_source is not None:
		(directory / "pipeline.ipynb").write_bytes(notebook_source.encode("utf-8"))
	# Write the manifest last: it is the publication marker for a complete artifact.
	(directory / "manifest.json").write_text(
		json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8",
	)
	return manifest
