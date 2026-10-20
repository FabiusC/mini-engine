"""Generate a compact DAG JSON from the saved API response files."""

import json
from pathlib import Path

from tableau_engine.core.pipeline_clean import merge_pipeline_clean


def main() -> None:
	"""Merge local node, edge, and operation responses into one JSON file."""
	# Keep inputs and generated output beside the saved API snapshots.
	project_root = Path(__file__).resolve().parent
	dag_directory = project_root / "dag"
	# Load the API envelopes that describe nodes and their connections.
	nodes_json = json.loads((dag_directory / "nodes.json").read_text(encoding="utf-8"))
	edges_json = json.loads((dag_directory / "edges.json").read_text(encoding="utf-8"))
	# Only active nodes determine which operation snapshots are needed.
	operation_ids = {
		node["operation_id"]
		for node in nodes_json.get("data", [])
		if not node.get("is_deleted") and node.get("operation_id")
	}
	operations_json = {"data": []}
	for operation_id in sorted(operation_ids):
		# Read operation contracts by ID instead of scanning unrelated JSON files.
		operation_path = dag_directory / f"{operation_id}.json"
		operation_response = json.loads(operation_path.read_text(encoding="utf-8"))
		operations_json["data"].append(operation_response["data"])

	# Compact the API responses into the requested edge-centric DAG shape.
	clean_dag = merge_pipeline_clean(edges_json, nodes_json, operations_json)
	output_path = dag_directory / "pipeline_clean.json"
	# Write stable, readable JSON for inspection or downstream consumers.
	output_path.write_text(
		json.dumps(clean_dag, indent=4, ensure_ascii=False) + "\n",
		encoding="utf-8",
	)
	print(f"Generated {len(clean_dag['edges'])} edges in {output_path}")


if __name__ == "__main__":
	main()
