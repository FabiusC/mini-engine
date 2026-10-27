"""End to end: dag/pipeline_test.json -> generated script (pandas and polars) -> identical CSV output."""

import json
import runpy
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from script_builder.__main__ import main as builder_main
from script_builder.ir import build_plan

ROOT = Path(__file__).resolve().parents[2]
PIPELINE = ROOT / "dag" / "pipeline_test.json"
EXPECTED_COLUMNS = [
	"Profit_south", "Order Date", "Customer Name_south", "Postal Code_south", "profit_in_range",
	"absolute_profit", "postal_code_text", "postal_code_concat", "customer_name_lower", "order_month",
]


def generate_and_run(tmp_path: Path, framework: str) -> pd.DataFrame:
	"""Generate the artifact with the CLI and execute main.py as a worker would (python main.py ...)."""
	artifact = tmp_path / framework
	builder_main([str(PIPELINE), "--framework", framework, "--output-dir", str(artifact)])
	argv = sys.argv
	sys.argv = [str(artifact / "main.py"), "--base-dir", str(tmp_path)]
	try:
		runpy.run_path(str(artifact / "main.py"), run_name="__main__")
	finally:
		sys.argv = argv
	return pd.read_csv(tmp_path / "output" / "processed_orders.csv")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
	shutil.copytree(ROOT / "data", tmp_path / "data")
	return tmp_path


def test_pipeline_test_topology_is_ordered_and_self_contained() -> None:
	plan = build_plan(json.loads(PIPELINE.read_text(encoding="utf-8")))
	order = [step.id for step in plan.steps]
	assert order.index("read_south") < order.index("join_orders") < order.index("write_output")
	assert order.index("read_central") < order.index("join_orders")
	assert plan.datasource_port_ids == ()
	assert plan.output_node_ids == ("write_output",)


@pytest.mark.parametrize("framework", ["pandas", "polars"])
def test_builder_cli_writes_only_main_and_manifest(workspace: Path, framework: str) -> None:
	artifact = workspace / "artifact"
	manifest = builder_main([str(PIPELINE), "--framework", framework, "--output-dir", str(artifact)])
	assert sorted(path.name for path in artifact.iterdir()) == ["main.py", "manifest.json"]
	assert manifest["pipeline_id"] == "pipeline_test"
	assert manifest["target"]["framework"] == framework
	assert "script_builder" not in (artifact / "main.py").read_text(encoding="utf-8")
	# Regenerating replaces the previous artifact.
	assert builder_main([str(PIPELINE), "--framework", framework, "--output-dir", str(artifact)]) == manifest


def test_pandas_and_polars_scripts_produce_the_same_output(workspace: Path) -> None:
	pandas_result = generate_and_run(workspace, "pandas")
	polars_result = generate_and_run(workspace, "polars")
	assert pandas_result.columns.tolist() == EXPECTED_COLUMNS
	assert len(pandas_result) == 1627
	assert_frame_equal(pandas_result, polars_result)
