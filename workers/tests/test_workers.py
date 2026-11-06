"""Worker emulation: verify manifest.json, pick the matching worker and run the generated <pipeline_id>.py."""

import hashlib
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
PIPELINE = json.loads((ROOT / "script-builder" / "tests" / "fixtures" / "pipeline_test.json").read_text(encoding="utf-8"))
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


@pytest.mark.parametrize("notebook", [False, True])
def test_artifact_hashes_match_exact_written_bytes(workspace: Path, notebook: bool) -> None:
	artifact = workspace / "artifact"
	build_artifact(
		PIPELINE, artifact, pipeline_id="pipeline_test", pipeline_version="1",
		notebook=notebook,
	)
	manifest = load_artifact(artifact)
	for item in manifest["files"]:
		content = (artifact / item["path"]).read_bytes()
		assert hashlib.sha256(content).hexdigest() == item["sha256"]


def test_worker_rejects_artifact_for_another_framework(workspace: Path) -> None:
	artifact = make_artifact(workspace / "artifact", "polars")
	with pytest.raises(ValueError, match="pandas worker cannot run a polars artifact"):
		PandasWorker().run(artifact, base_dir=workspace)
	assert not (workspace / OUTPUT).exists()


def test_tampered_or_incomplete_artifacts_are_not_executed(workspace: Path) -> None:
	artifact = make_artifact(workspace / "artifact", "pandas")
	with (artifact / "pipeline_test.py").open("a", encoding="utf-8") as script:
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


def make_file_artifact(directory: Path) -> Path:
	"""Artifact whose read node takes its file from an input_files parameter, like the API DAGs."""
	pipeline = {
		"nodes": [
			{"id": "read", "operation": {"name": "read_csv"}, "input_ports": [],
			 "output_ports": [{"id": "read_out", "ordinal": 0}],
			 "parameters": {"filepath": {"$param": "file_abc"}}},
			{"id": "write", "operation": {"name": "write_csv"},
			 "input_ports": [{"id": "write_in", "ordinal": 0}], "output_ports": [],
			 "parameters": {"filepath": "output/copy.csv"}},
		],
		"edges": [{"id": "e", "source_node_id": "read", "target_node_id": "write",
			"source_output_port_id": "read_out", "target_input_port_id": "write_in"}],
		"input_files": {"file_abc": "abc"},
	}
	build_artifact(pipeline, directory, pipeline_id="file-pipeline")
	return directory


def test_worker_reads_input_files_from_the_hardcoded_settings(workspace: Path, monkeypatch) -> None:
	from workers import settings

	artifact = make_file_artifact(workspace / "artifact")
	assert load_artifact(artifact)["entrypoint"] == "file-pipeline.py"
	monkeypatch.setattr(settings, "INPUT_FILE_PATH", workspace / "missing.csv")
	with pytest.raises(FileNotFoundError, match="settings.py"):
		PandasWorker().run(artifact, base_dir=workspace)
	pd.DataFrame({"id": [1, 2]}).to_csv(workspace / "default.csv", index=False)
	pd.DataFrame({"id": [7]}).to_csv(workspace / "specific.csv", index=False)
	monkeypatch.setattr(settings, "INPUT_FILE_PATH", workspace / "default.csv")
	assert PandasWorker().run(artifact, base_dir=workspace) == 0
	assert pd.read_csv(workspace / "output/copy.csv")["id"].tolist() == [1, 2]
	monkeypatch.setattr(settings, "INPUT_FILE_PATHS", {"abc": workspace / "specific.csv"})
	assert PandasWorker().run(artifact, base_dir=workspace) == 0
	assert pd.read_csv(workspace / "output/copy.csv")["id"].tolist() == [7]
	# An explicit params file wins over the hardcoded location.
	params = workspace / "params.json"
	params.write_text(json.dumps({"file_abc": str(workspace / "default.csv")}), encoding="utf-8")
	assert PandasWorker().run(artifact, params_file=params, base_dir=workspace) == 0
	assert pd.read_csv(workspace / "output/copy.csv")["id"].tolist() == [1, 2]


@pytest.mark.parametrize("entrypoint", ["../evil.py", "sub/script.py", "script.sh", ".hidden.py", None])
def test_manifest_entrypoint_must_be_a_listed_plain_python_file(workspace: Path, entrypoint) -> None:
	artifact = make_artifact(workspace / "artifact", "pandas")
	manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
	manifest["entrypoint"] = entrypoint
	(artifact / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
	with pytest.raises(ValueError, match="entrypoint"):
		load_artifact(artifact)


def test_cli_resolves_a_pipeline_id_under_the_output_folder(workspace: Path, monkeypatch) -> None:
	from workers import __main__ as cli

	monkeypatch.setattr(cli, "OUTPUT_DIR", workspace / "output-artifacts")
	with pytest.raises(FileNotFoundError, match="run the script builder"):
		cli.resolve_artifact(None)
	artifact = make_artifact(workspace / "output-artifacts" / "pipeline_test", "pandas")
	assert cli.resolve_artifact("pipeline_test") == artifact
	assert cli.resolve_artifact(None) == artifact
	assert worker_main(["pipeline_test", "--base-dir", str(workspace)]) == 0
	assert (workspace / OUTPUT).is_file()
