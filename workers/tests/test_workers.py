"""Worker emulation: verify manifest.json, pick the matching worker and run the generated main.py."""

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from script_builder.codegen.builder import build_artifact
from workers import WORKERS, PandasWorker, PolarsWorker
from workers.__main__ import main as worker_main
from workers.artifact import load_artifact

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = json.loads((ROOT / "dag" / "pipeline_test.json").read_text(encoding="utf-8"))
OUTPUT = Path("output") / "processed_orders.csv"


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
	shutil.copytree(ROOT / "data", tmp_path / "data")
	return tmp_path


def make_artifact(directory: Path, framework: str) -> Path:
	build_artifact(PIPELINE, directory, pipeline_id="pipeline_test", pipeline_version="1", framework=framework)
	return directory


@pytest.mark.parametrize("worker", [PandasWorker, PolarsWorker])
def test_worker_runs_artifact_for_its_framework(workspace: Path, worker) -> None:
	artifact = make_artifact(workspace / "artifact", worker.framework)
	assert worker().run(artifact, base_dir=workspace) == 0
	assert len(pd.read_csv(workspace / OUTPUT)) == 1627


def test_worker_rejects_artifact_for_another_framework(workspace: Path) -> None:
	artifact = make_artifact(workspace / "artifact", "polars")
	with pytest.raises(ValueError, match="pandas worker cannot run a polars artifact"):
		PandasWorker().run(artifact, base_dir=workspace)
	assert not (workspace / OUTPUT).exists()


def test_tampered_or_incomplete_artifacts_are_not_executed(workspace: Path) -> None:
	artifact = make_artifact(workspace / "artifact", "pandas")
	with (artifact / "main.py").open("a", encoding="utf-8") as script:
		script.write("\nraise SystemExit('tampered')\n")
	with pytest.raises(ValueError, match="integrity check failed"):
		PandasWorker().run(artifact, base_dir=workspace)
	(artifact / "manifest.json").unlink()
	with pytest.raises(FileNotFoundError, match="No manifest.json"):
		load_artifact(artifact)


def test_cli_selects_worker_from_manifest_and_reports_exit_code(workspace: Path) -> None:
	assert set(WORKERS) == {"pandas", "polars"}
	artifact = make_artifact(workspace / "artifact", "polars")
	assert worker_main([str(artifact), "--base-dir", str(workspace)]) == 0
	assert (workspace / OUTPUT).is_file()
	assert worker_main([str(artifact), "--base-dir", str(workspace / "missing-data")]) != 0
