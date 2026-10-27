"""CLI: run a generated artifact (main.py + manifest.json) with the matching worker."""

import argparse
from pathlib import Path

from workers import WORKERS
from workers.artifact import load_artifact

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT = REPOSITORY_ROOT / "output" / "pipeline_test"


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Run a generated script with the pandas or polars worker")
	parser.add_argument("artifact", type=Path, nargs="?", default=DEFAULT_ARTIFACT)
	parser.add_argument("--worker", choices=sorted(WORKERS), help="Default: the framework in manifest.json")
	parser.add_argument("--params-file", type=Path)
	parser.add_argument("--datasources-file", type=Path)
	parser.add_argument(
		"--base-dir", type=Path, default=REPOSITORY_ROOT,
		help="Base for relative data paths in the DAG (default: repository root)",
	)
	args = parser.parse_args(argv)
	worker_name = args.worker or load_artifact(args.artifact)["target"]["framework"]
	return WORKERS[worker_name]().run(
		args.artifact,
		params_file=args.params_file,
		datasources_file=args.datasources_file,
		base_dir=args.base_dir,
	)


if __name__ == "__main__":
	raise SystemExit(main())
