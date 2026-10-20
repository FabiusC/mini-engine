"""Read a CSV, apply the text DAG, and save the result."""

import json
from pathlib import Path

from tableau_engine.core.dag_graph import load_dag
from tableau_engine.core.dag_runner import DAGRunner
from tableau_engine.io import read_datasource


def main() -> None:
	"""Join South and Central orders, then run the text DAG."""
	project_root = Path(__file__).resolve().parent
	dag = load_dag(project_root / "dag")
	print("Execution order:")
	for node in dag.nodes:
		print(f"  {node.name}: {node.operation}")

	config_path = project_root / "dag" / "runtime.json"
	if not config_path.exists():
		print(f"DAG built. Add datasource bindings and operation parameters to {config_path} to execute it.")
		for node_id, port in dag.missing_inputs:
			print(f"  Missing input: node={node_id}, port={port.port_id} ({port.description})")
		return

	config = json.loads(config_path.read_text(encoding="utf-8"))
	datasources = {
		port_id: read_datasource(project_root / filepath)
		for port_id, filepath in config.get("datasources", {}).items()
	}
	results = DAGRunner(dag).run(datasources, config.get("parameters", {}))
	for node in dag.nodes:
		result = results[node.node_id]
		print(f"Executed {node.name}: {len(result)} rows, {len(result.columns)} columns")


if __name__ == "__main__":
	main()
