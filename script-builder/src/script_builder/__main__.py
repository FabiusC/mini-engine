"""CLI: read a DAG JSON, validate its topology and write main.py + manifest.json under output/."""

import argparse
import json
from pathlib import Path

from script_builder.codegen.builder import build_artifact

# parents[3] climbs script_builder -> src -> script-builder -> repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PIPELINE = REPOSITORY_ROOT / "dag" / "pipeline_test.json"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "output"


def main(argv: list[str] | None = None) -> dict:
	# Step 1: declare and parse the CLI arguments (pipeline path is optional and falls back to the default DAG).
	parser = argparse.ArgumentParser(description="Compile a DAG into a standalone worker script")
	parser.add_argument("pipeline", type=Path, nargs="?", default=DEFAULT_PIPELINE)
	parser.add_argument("--output-dir", type=Path, help="Artifact directory (default: output/<pipeline name>/)")
	parser.add_argument("--pipeline-id", help="Default: pipeline file name")
	parser.add_argument("--pipeline-version", default="1")
	parser.add_argument("--engine", default="python")
	parser.add_argument("--framework", default="pandas", choices=("pandas", "polars"))
	parser.add_argument("--notebook", action="store_true", help="Also generate an executable Jupyter notebook")
	args = parser.parse_args(argv)
	# Step 2: default output is output/<pipeline file name without extension>/.
	output_dir = args.output_dir or DEFAULT_OUTPUT / args.pipeline.stem
	# Step 3: load the DAG JSON and compile it into main.py + manifest.json (the whole pipeline lives in build_artifact).
	manifest = build_artifact(
		json.loads(args.pipeline.read_text(encoding="utf-8")),
		output_dir,
		pipeline_id=args.pipeline_id or args.pipeline.stem,
		pipeline_version=args.pipeline_version,
		engine=args.engine,
		framework=args.framework,
		notebook=args.notebook,
		overwrite=True,
	)
	# Step 4: report where the artifact was written and return the manifest for programmatic callers/tests.
	print(f"Generated {output_dir / 'main.py'} and {output_dir / 'manifest.json'}")
	return manifest


if __name__ == "__main__":
	main()
