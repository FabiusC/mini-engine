"""Hardcoded worker locations. Edit the paths below to point the worker at its input files."""

from pathlib import Path

# parents[3] climbs workers -> src -> workers -> repository root.
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPOSITORY_ROOT / "output"

# File read by every DAG "Leer archivo" node (its "archivo" parameter holds a DSM file id).
INPUT_FILE_PATH = REPOSITORY_ROOT / "data" / "96bea6b5-f60a-419b-ac7f-eba00eb685c5.xlsx"

# Optional per-file overrides keyed by DSM file id, for pipelines that read several files.
INPUT_FILE_PATHS: dict[str, Path] = {}


def input_file_path(file_id: str) -> Path:
	return Path(INPUT_FILE_PATHS.get(file_id, INPUT_FILE_PATH))
