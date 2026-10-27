"""CLI: python -m engine.codegen DAG --output-dir PATH --pipeline-id ID --pipeline-version VERSION."""

import argparse
import json
from pathlib import Path

from engine.codegen.builder import build_artifact


def main() -> None:
	parser = argparse.ArgumentParser(description="Compile a clean DAG into a standalone worker artifact")
	parser.add_argument("pipeline", type=Path)
	parser.add_argument("--output-dir", type=Path, required=True)
	parser.add_argument("--pipeline-id", required=True)
	parser.add_argument("--pipeline-version", required=True)
	parser.add_argument("--engine", default="python")
	parser.add_argument("--framework", default="pandas")
	parser.add_argument("--notebook", action="store_true", help="Also generate an executable Jupyter notebook")
	args = parser.parse_args()
	manifest = build_artifact(
		json.loads(args.pipeline.read_text(encoding="utf-8")),
		args.output_dir,
		pipeline_id=args.pipeline_id,
		pipeline_version=args.pipeline_version,
		engine=args.engine,
		framework=args.framework,
		notebook=args.notebook,
	)
	print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
	main()
