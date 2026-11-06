"""pipeline_clean: read the saved API responses in dag/ and turn them into a buildable pipeline."""

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from builder_testing import compile_pipeline
from script_builder.dag.pipeline_clean import (
	export_clean_pipeline, load_api_pipeline, merge_pipeline_clean, read_snapshots,
)
from script_builder.ir import build_plan


ROOT = Path(__file__).resolve().parents[2]
DAG = ROOT / "dag"
PIPELINE_ID = "e6b4f425-1133-4cae-97ec-442f4cf2a24b"
VERSION_ID = "ecf87031-be86-4cf4-8942-90612749e1fa"
FILE_ID = "4e1786d0-9903-49b0-8cfd-964319e85bae"
READ, LOWER, WRITE = (
	"e389d4af-a583-45c2-9999-b2b2f7f2c432",
	"0a4ed244-6adb-4b67-a009-8d9d8c629582",
	"198e4b46-3715-4890-bb19-41ba6ccd81e2",
)


def _value(**typed):
	return {
		"value_string": None, "value_text": None, "value_int": None,
		"value_float": None, "value_bool": None, **typed,
	}


def _node(id: str = "source", operation_id: str = "op", **extra) -> dict:
	return {
		"id": id, "operation_id": operation_id, "parameters": [],
		"input_ports": [], "output_ports": [], **extra,
	}


def test_snapshots_are_classified_by_response_code_not_file_name() -> None:
	snapshots = read_snapshots(DAG)
	assert [item["id"] for item in snapshots["pipelines"]] == [PIPELINE_ID]
	assert len(snapshots["nodes"]) == 3
	assert len(snapshots["edges"]) == 2
	# "operation-templates-eeb4...json" holds an operation; templates and the empty file are ignored.
	assert {item["name"] for item in snapshots["operations"]} == {"read_csv", "lowercase", "write_csv"}


def test_real_snapshots_load_as_a_clean_pipeline() -> None:
	api = load_api_pipeline(DAG)
	assert (api.id, api.name, api.version_id) == (PIPELINE_ID, "Netflix0", VERSION_ID)
	nodes = {node["id"]: node for node in api.pipeline["nodes"]}
	reference = f"file_{FILE_ID}"
	assert nodes[READ]["parameters"] == {"filepath": {"$param": reference}}
	assert nodes[LOWER]["operation"]["name"] == "lowercase"
	assert nodes[LOWER]["parameters"] == {"column": "title", "create_new_column": True, "new_column_name": "title_lower"}
	assert nodes[WRITE]["parameters"] == {"filepath": f"output/{PIPELINE_ID}/{WRITE}.csv"}
	assert api.pipeline["input_files"] == {reference: FILE_ID}
	assert all(set(edge) == {
		"id", "source_node_id", "target_node_id", "source_output_port_id", "target_input_port_id",
	} for edge in api.pipeline["edges"])
	plan = build_plan(api.pipeline)
	assert [step.id for step in plan.steps] == [READ, LOWER, WRITE]
	assert plan.runtime_parameters == (reference,)


def test_pipeline_selection_requires_a_known_id(tmp_path: Path) -> None:
	with pytest.raises(ValueError, match="No pipeline missing"):
		load_api_pipeline(DAG, "missing")
	for path in DAG.glob("*.json"):
		shutil.copy(path, tmp_path / path.name)
	second = json.loads((DAG / f"pipeline-{PIPELINE_ID}.json").read_text(encoding="utf-8"))
	second["data"] = {**second["data"], "id": "other", "current_version_id": "other-version"}
	(tmp_path / "pipeline-other.json").write_text(json.dumps(second), encoding="utf-8")
	with pytest.raises(ValueError, match="--pipeline-id"):
		load_api_pipeline(tmp_path)
	assert load_api_pipeline(tmp_path, PIPELINE_ID).id == PIPELINE_ID
	# The other pipeline has no nodes for its current version.
	with pytest.raises(ValueError, match="no nodes"):
		load_api_pipeline(tmp_path, "other")


def test_invalid_or_unsuccessful_snapshots_are_reported(tmp_path: Path) -> None:
	(tmp_path / "broken.json").write_text("{", encoding="utf-8")
	with pytest.raises(ValueError, match="broken.json is not valid JSON"):
		read_snapshots(tmp_path)
	(tmp_path / "broken.json").write_text(json.dumps({"success": False, "code": "PIPELINE_RETRIEVED"}), encoding="utf-8")
	with pytest.raises(ValueError, match="unsuccessful"):
		read_snapshots(tmp_path)
	with pytest.raises(FileNotFoundError):
		read_snapshots(tmp_path / "missing")


def test_typed_values_and_api_labels_become_canonical_parameters() -> None:
	parameters = [
		{"name": "column", "required": True, "value": _value(value_string="v")},
		{"name": "Nueva columna", "required": True, "value": _value(value_bool=False)},
		{"name": "Nombre nueva columna", "required": False, "value": _value()},
	]
	clean = merge_pipeline_clean([], [_node(parameters=parameters)], {"id": "op", "name": "absolute"})
	# The empty optional new column name is dropped so the operation default applies.
	assert clean["nodes"][0]["parameters"] == {"column": "v", "create_new_column": False}


def test_array_items_and_children_are_unwrapped() -> None:
	parameters = [
		{"name": "columns", "value": None, "array_items": [
			{"ordinal": 1, "value": _value(value_string="b")},
			{"ordinal": 0, "value": _value(value_string="a")},
			{"ordinal": 2, "value": _value(value_string="deleted"), "is_deleted": True},
		]},
		{"name": "nested", "value": None, "children": [{"name": "inner", "value": _value(value_int=3)}]},
	]
	clean = merge_pipeline_clean([], [_node(parameters=parameters)], {"id": "op", "name": "concat_column"})
	assert clean["nodes"][0]["parameters"] == {"columns": ["a", "b"], "nested": {"inner": 3}}


def test_file_parameter_is_rejected_by_operations_that_do_not_read_files() -> None:
	parameters = [{"name": "archivo", "value": _value(value_string=FILE_ID)}]
	with pytest.raises(ValueError, match="does not read files"):
		merge_pipeline_clean([], [_node(parameters=parameters)], {"id": "op", "name": "lowercase"})


def test_merge_keeps_only_the_current_version_and_active_records() -> None:
	source = _node(version_id="v2")
	source["input_ports"] = [
		{"id": "active", "ordinal": None},
		{"id": "deleted_port", "ordinal": 1, "is_deleted": True},
	]
	result = merge_pipeline_clean(
		{"data": [
			{"id": "old_edge", "source_node_id": "source", "target_node_id": "old", "version_id": "v2"},
			{"id": "deleted_node_edge", "source_node_id": "source", "target_node_id": "deleted"},
			{"id": "deleted_edge", "is_deleted": True},
			{"id": "other_version", "version_id": "v1"},
		]},
		{"data": [
			source, _node("old", version_id="v1"),
			{**_node("deleted"), "is_deleted": True}, _node("isolated"),
		]},
		{"data": {"id": "op", "name": "example"}},
		version_id="v2",
	)
	assert result["edges"] == []
	assert [node["id"] for node in result["nodes"]] == ["source", "isolated"]
	assert result["nodes"][0]["input_ports"] == [{"id": "active", "ordinal": 0}]


@pytest.mark.parametrize("parameters", [
	{"column": "v", "create_new_column": True, "new_column_name": None, "value": 0},
	[{"name": "column", "value": "v"}, {"name": "create_new_column", "value": False}],
	None, [],
])
def test_merge_preserves_typed_parameters_without_mutating_inputs(parameters) -> None:
	nodes = {"data": [{**_node(), "parameters": parameters}]}
	before = deepcopy(nodes)
	clean = merge_pipeline_clean({"data": []}, nodes, {"id": "op", "name": "absolute"})
	expected = (
		{item["name"]: item["value"] for item in parameters}
		if isinstance(parameters, list) else parameters or {}
	)
	assert clean["nodes"][0]["parameters"] == expected
	assert nodes == before


@pytest.mark.parametrize("parameters", [
	"value", [1], [{"name": "column"}], [{"value": "v"}],
	[{"name": "column", "value": "v"}, {"name": "column", "value": "other"}],
	[{"name": "Nueva columna", "value": True}, {"name": "create_new_column", "value": False}],
])
def test_merge_rejects_invalid_or_duplicate_parameters(parameters) -> None:
	with pytest.raises(ValueError, match="parameter"):
		merge_pipeline_clean([], [{**_node(), "parameters": parameters}], {"id": "op", "name": "upper"})


def test_merge_rejects_dangling_edges_missing_operations_and_duplicate_nodes() -> None:
	with pytest.raises(ValueError, match="unknown node"):
		merge_pipeline_clean(
			[{"id": "edge", "source_node_id": "source", "target_node_id": "missing"}],
			[_node()], {"id": "op", "name": "upper"},
		)
	with pytest.raises(ValueError, match="missing operation"):
		merge_pipeline_clean([], [_node()], [])
	with pytest.raises(ValueError, match="Duplicate node"):
		merge_pipeline_clean([], [_node(), _node()], {"id": "op", "name": "upper"})


def test_export_writes_the_clean_pipeline_deterministically(tmp_path: Path) -> None:
	for path in DAG.glob("*.json"):
		shutil.copy(path, tmp_path / path.name)
	path = tmp_path / "pipeline_clean.json"
	path.write_text("stale content", encoding="utf-8")
	clean = export_clean_pipeline(tmp_path)
	first = path.read_text(encoding="utf-8")
	assert json.loads(first) == clean
	assert (clean["pipeline_id"], clean["pipeline_version"]) == (PIPELINE_ID, VERSION_ID)
	# The exported file sits next to the snapshots and does not disturb a second export.
	export_clean_pipeline(tmp_path)
	assert path.read_text(encoding="utf-8") == first


def test_cleaned_api_responses_compile_and_run_as_a_script(tmp_path: Path) -> None:
	pd.DataFrame({"v": [-2, 3]}).to_csv(tmp_path / "input.csv", index=False)
	clean = merge_pipeline_clean(
		[
			{"id": "e1", "source_node_id": "read", "target_node_id": "absolute",
			 "source_output_port_id": "read_out", "target_input_port_id": "abs_in"},
			{"id": "e2", "source_node_id": "absolute", "target_node_id": "write",
			 "source_output_port_id": "abs_out", "target_input_port_id": "write_in"},
		],
		[
			_node("read", "read_op", output_ports=[{"id": "read_out", "ordinal": 0}],
				parameters=[{"name": "archivo", "required": True, "value": _value(value_string="input-id")}]),
			_node("absolute", "abs_op", input_ports=[{"id": "abs_in", "ordinal": 0}],
				output_ports=[{"id": "abs_out", "ordinal": 0}],
				parameters=[{"name": "column", "value": _value(value_string="v")},
					{"name": "Nueva columna", "value": _value(value_bool=True)}]),
			_node("write", "write_op", input_ports=[{"id": "write_in", "ordinal": 0}]),
		],
		[{"id": "read_op", "name": "read_csv"}, {"id": "abs_op", "name": "absolute"}, {"id": "write_op", "name": "write_csv"}],
		pipeline_id="api",
	)
	results = compile_pipeline(clean).run(parameters={"file_input-id": "input.csv"}, base_dir=tmp_path)
	assert pd.read_csv(tmp_path / "output/api/write.csv")["v_processed"].tolist() == [2, 3]
	assert results["write"].shape == (2, 2)


@pytest.mark.parametrize("framework", ["pandas", "polars"])
def test_real_snapshots_build_a_script_named_after_the_pipeline_that_a_worker_runs(
	tmp_path: Path, framework: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
	from script_builder.__main__ import main as builder_main
	from workers import WORKERS, settings

	artifact = tmp_path / "artifact"
	manifest = builder_main([str(DAG), "--framework", framework, "--output-dir", str(artifact)])
	assert manifest["pipeline_id"] == PIPELINE_ID
	assert manifest["pipeline_version"] == VERSION_ID
	assert manifest["entrypoint"] == f"{PIPELINE_ID}.py"
	assert manifest["input_files"] == {f"file_{FILE_ID}": FILE_ID}
	assert sorted(path.name for path in artifact.iterdir()) == sorted(["manifest.json", f"{PIPELINE_ID}.py"])
	# The worker reads the file from its hardcoded location (patched here to a small copy of the data).
	source = tmp_path / "netflix.xlsx"
	pd.read_excel(ROOT / "data" / "netflix_titles.xlsx", nrows=25).to_excel(source, index=False)
	monkeypatch.setattr(settings, "INPUT_FILE_PATH", source)
	assert WORKERS[framework]().run(artifact, base_dir=tmp_path) == 0
	output = pd.read_csv(tmp_path / "output" / PIPELINE_ID / f"{WRITE}.csv")
	assert len(output) == 25
	assert output["title_lower"].tolist() == output["title"].str.lower().tolist()
