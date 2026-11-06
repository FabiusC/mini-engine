"""CLI: run a generated artifact (<pipeline_id>.py + manifest.json) with the matching worker."""

import argparse
from pathlib import Path

from workers import WORKERS
from workers.artifact import load_artifact
from workers.settings import OUTPUT_DIR, REPOSITORY_ROOT


def resolve_artifact(value: str | None) -> Path:
	"""Accept an artifact folder or a pipeline id (output/<id>/); default to the latest built artifact."""
	if value is None:
		manifests = sorted(OUTPUT_DIR.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime)
		if not manifests:
			raise FileNotFoundError(f"No artifact under {OUTPUT_DIR}; run the script builder first")
		return manifests[-1].parent
	path = Path(value)
	if not path.exists() and (OUTPUT_DIR / value).is_dir():
		return OUTPUT_DIR / value
	return path


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description="Run a generated script with the pandas or polars worker")
	parser.add_argument(
		"artifact", nargs="?",
		help="Artifact folder or pipeline id under output/ (default: the most recently built artifact)",
	)
	parser.add_argument("--worker", choices=sorted(WORKERS), help="Default: the framework in manifest.json")
	parser.add_argument("--params-file", type=Path)
	parser.add_argument("--datasources-file", type=Path)
	parser.add_argument(
		"--base-dir", type=Path, default=REPOSITORY_ROOT,
		help="Base for relative data paths in the DAG (default: repository root)",
	)
	args = parser.parse_args(argv)
	artifact = resolve_artifact(args.artifact)
	worker_name = args.worker or load_artifact(artifact)["target"]["framework"]
	return WORKERS[worker_name]().run(
		artifact,
		params_file=args.params_file,
		datasources_file=args.datasources_file,
		base_dir=args.base_dir,
	)


if __name__ == "__main__":
	raise SystemExit(main())
