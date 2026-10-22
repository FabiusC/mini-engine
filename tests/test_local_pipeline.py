"""Run the local pipeline definition against small temporary CSV files."""

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

import main as app_main
from engine.core.pipeline_runner import PipelineRunner

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("pipeline_file", ["pipeline.json", "pipeline_test.json"])
def test_main_can_skip_building_pipeline_clean(monkeypatch, pipeline_file) -> None:
	"""Skipping the clean DAG build does not skip local pipeline execution."""
	run_calls = []
	monkeypatch.setattr(
		app_main,
		"export_clean_pipeline",
		lambda _: (_ for _ in ()).throw(AssertionError("unexpected DAG build")),
	)
	monkeypatch.setattr(app_main, "run_pipeline", lambda *args, **kwargs: run_calls.append((args, kwargs)))

	app_main.main(build_pipeline_clean=False, pipeline_file=pipeline_file)

	assert len(run_calls) == 1
	assert run_calls[0][0][1].name == pipeline_file


def test_main_passes_external_inputs_and_runtime_parameters(monkeypatch) -> None:
	datasources = {"external_input": pd.DataFrame({"id": [1]})}
	parameters = {"join": {"left_on": "id", "right_on": "id"}}
	run_calls = []
	monkeypatch.setattr(app_main, "export_clean_pipeline", lambda _: None)
	monkeypatch.setattr(
		app_main, "run_pipeline", lambda *args, **kwargs: run_calls.append((args, kwargs))
	)

	app_main.main(
		build_pipeline_clean=False,
		pipeline_file="pipeline_test.json",
		datasources=datasources,
		parameters=parameters,
	)

	assert run_calls[0][0][1].name == "pipeline_test.json"
	assert run_calls[0][1] == {"datasources": datasources, "parameters": parameters}


def test_local_pipeline_runs_structural_operations_and_overwrites_output(tmp_path: Path) -> None:
	(tmp_path / "data").mkdir()
	pd.DataFrame({
		"Customer ID": ["A", "B"],
		"Sales": [10.245, 20.0],
		"Discount": [0.2, 0.0],
		"Profit": [-1.234, 3.0],
		"Postal Code": [12345, 67890],
	}).to_csv(tmp_path / "data" / "orders_south_2018.csv", index=False)
	pd.DataFrame({
		"Customer ID": ["A", "B"],
		"Sales": [1.239, 2.0],
		"Discounts": [0.3, 0.1],
		"Profit": [-2.7, 4.0],
		"Postal Code": [12345, 67890],
	}).to_csv(tmp_path / "data" / "Orders_Central.csv", index=False)
	output_path = tmp_path / "output" / "processed_orders.csv"
	output_path.parent.mkdir()
	output_path.write_text("stale\n", encoding="utf-8")
	shutil.copy(ROOT / "dag" / "pipeline.json", tmp_path / "pipeline.json")

	pipeline = json.loads((tmp_path / "pipeline.json").read_text(encoding="utf-8"))
	PipelineRunner(pipeline, base_dir=tmp_path).run()
	result = pd.read_csv(output_path, dtype={"Postal Code_south": "string"})

	assert result["Customer ID"].tolist() == ["B", "A"]
	assert result["Sales_south"].tolist() == [20.0, 10.245]
	assert "Discount" not in result.columns
	assert result["Profit Margin"].tolist() == [3.0, -1.234]
	assert result["Postal Code_south"].tolist() == ["67890", "12345"]
	assert result["Postal Code_south"].dtype == pd.StringDtype()
	assert result["source"].tolist() == ["south_central_join", "south_central_join"]
