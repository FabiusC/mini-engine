"""Build an immutable local artifact ready for publication to workers."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from engine.artifacts.manifest import build_manifest
from engine.codegen.registry import EMITTERS
from engine.codegen.notebook import emit_notebook
from engine.ir.plan import build_plan


def build_artifact(
	pipeline: Mapping[str, Any],
	output_dir: str | Path,
	*,
	pipeline_id: str,
	pipeline_version: str,
	engine: str = "python",
	framework: str = "pandas",
	notebook: bool = False,
) -> dict[str, Any]:
	"""Validate before writing; an existing artifact directory is never overwritten."""
	plan = build_plan(pipeline, engine=engine, framework=framework)
	script = EMITTERS[framework]().emit(plan)
	notebook_source = emit_notebook(script, framework) if notebook else None
	manifest = build_manifest(
		plan, script, pipeline_id=pipeline_id, pipeline_version=pipeline_version, notebook=notebook_source,
	)
	directory = Path(output_dir)
	directory.mkdir(parents=True, exist_ok=False)
	(directory / "main.py").write_text(script, encoding="utf-8")
	if notebook_source is not None:
		(directory / "pipeline.ipynb").write_text(notebook_source, encoding="utf-8")
	# Write the manifest last: it is the publication marker for a complete artifact.
	(directory / "manifest.json").write_text(
		json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8",
	)
	return manifest
