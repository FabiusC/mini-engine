"""Run the local pipeline definition against small temporary CSV files."""

import json
import shutil
from pathlib import Path

import pandas as pd

import main as app_main
from tableau_engine.core.pipeline_runner import PipelineRunner

ROOT = Path(__file__).resolve().parents[1]


def test_main_can_skip_building_pipeline_clean(monkeypatch) -> None:
	"""Skipping the clean DAG build does not skip local pipeline execution."""
	run_calls = []
	monkeypatch.setattr(
		app_main,
		"export_clean_pipeline",
		lambda _: (_ for _ in ()).throw(AssertionError("unexpected DAG build")),
	)
	monkeypatch.setattr(app_main, "run_pipeline", lambda *args: run_calls.append(args))

	app_main.main(build_pipeline_clean=False)

	assert len(run_calls) == 1
	assert run_calls[0][1].name == "pipeline.json"


def test_local_pipeline_reads_joins_transforms_and_overwrites_output(tmp_path: Path) -> None:
	(tmp_path / "data").mkdir()
	pd.DataFrame({
		"Customer ID": ["A", "B"],
		"Segment": ["consumer", "corporate"],
		"Customer Name": ["Ana Ruiz", "Bo Li"],
		"City": ["Austin", "Boston"],
	}).to_csv(tmp_path / "data" / "orders_south_2018.csv", index=False)
	pd.DataFrame({
		"Customer ID": ["A", "C"],
		"Segment": ["home office", "consumer"],
		"Customer Name": ["Ana Ruiz", "Cy Ho"],
		"City": ["Austin", "Chicago"],
	}).to_csv(tmp_path / "data" / "Orders_Central.csv", index=False)
	output_path = tmp_path / "output" / "processed_orders.csv"
	output_path.parent.mkdir()
	output_path.write_text("stale\n", encoding="utf-8")
	shutil.copy(ROOT / "dag" / "pipeline.json", tmp_path / "pipeline.json")

	pipeline = json.loads((tmp_path / "pipeline.json").read_text(encoding="utf-8"))
	PipelineRunner(pipeline, base_dir=tmp_path).run()
	result = pd.read_csv(output_path)

	assert result["Customer ID"].tolist() == ["A"]
	assert result["Segment_south"].tolist() == ["CONSUMER"]
	assert result["Customer Name_south"].tolist() == ["Ana Ruiz"]
	assert result["Customer Name_south_1"].tolist() == ["ana ruiz"]
	assert result["city_south_upper"].tolist() == ["AUSTIN"]
	assert result["source"].tolist() == ["south_central_join"]
