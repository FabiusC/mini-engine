"""CLI: read the API snapshots in dag/ (or a clean DAG JSON), validate the topology and write
<pipeline_id>.py + manifest.json under output/<pipeline_id>/."""

import argparse
import json
from pathlib import Path

from script_builder.codegen.builder import build_artifact
from script_builder.dag.pipeline_clean import load_api_pipeline

# parents[3] climbs script_builder -> src -> script-builder -> repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DAG = REPOSITORY_ROOT / "dag"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "output"


def main(argv: list[str] | None = None) -> dict:
	# Step 1: declare and parse the CLI arguments (the source is optional and falls back to the dag/ folder).
	parser = argparse.ArgumentParser(description="Compile a DAG into a standalone worker script")
	parser.add_argument(
		"pipeline", type=Path, nargs="?", default=DEFAULT_DAG,
		help="Folder with the API JSON responses (default: dag/) or a clean pipeline JSON file",
	)
	parser.add_argument("--output-dir", type=Path, help="Artifact directory (default: output/<pipeline id>/)")
	parser.add_argument(
		"--pipeline-id",
		help="Folder: pipeline to build when it holds several. File: default is its pipeline_id or the file name",
	)
	parser.add_argument("--pipeline-version", help="Default: the pipeline's current version id, else 1")
	parser.add_argument("--engine", default="python")
	parser.add_argument("--framework", default="pandas", choices=("pandas", "polars"))
	parser.add_argument("--notebook", action="store_true", help="Also generate an executable Jupyter notebook")
	args = parser.parse_args(argv)
	# Step 2: load the pipeline. A folder holds raw API responses; a file holds an already clean pipeline.
	if args.pipeline.is_dir():
		api = load_api_pipeline(args.pipeline, args.pipeline_id)
		pipeline, pipeline_id, pipeline_version = api.pipeline, api.id, args.pipeline_version or api.version_id
	else:
		pipeline = json.loads(args.pipeline.read_text(encoding="utf-8"))
		metadata = pipeline if isinstance(pipeline, dict) else {}
		pipeline_id = args.pipeline_id or metadata.get("pipeline_id") or args.pipeline.stem
		pipeline_version = args.pipeline_version or metadata.get("pipeline_version")
	# Step 3: default output is output/<pipeline id>/; the script inside is named <pipeline id>.py.
	output_dir = args.output_dir or DEFAULT_OUTPUT / pipeline_id
	manifest = build_artifact(
		pipeline,
		output_dir,
		pipeline_id=pipeline_id,
		pipeline_version=pipeline_version or "1",
		engine=args.engine,
		framework=args.framework,
		notebook=args.notebook,
		overwrite=True,
	)
	# Step 4: report where the artifact was written and return the manifest for programmatic callers/tests.
	print(f"Generated {output_dir / manifest['entrypoint']} and {output_dir / 'manifest.json'}")
	return manifest


if __name__ == "__main__":
	main()
