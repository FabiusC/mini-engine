"""Read a CSV, apply the text DAG, and save the result."""

import json
from pathlib import Path

from tableau_engine.core.dag_runner import DAGRunner
from tableau_engine.io import read_datasource


def main() -> None:
	"""Join South and Central orders, then run the text DAG."""
	project_root = Path(__file__).resolve().parent
	dag_path = project_root / "pipeline.dag.json"
	dag = json.loads(dag_path.read_text(encoding="utf-8"))
	datasources = {
		"south": read_datasource(project_root / "data" / "orders_south_2018.csv"),
		"central": read_datasource(project_root / "data" / "Orders_Central.csv"),
	}
	result = DAGRunner(dag["nodes"]).run(datasources, dag["output"])
	output_path = project_root / "output" / "processed_orders.csv"
	output_path.parent.mkdir(parents=True, exist_ok=True)
	result.to_csv(output_path, index=False)

	print(f"Processed {len(result)} rows across {len(result.columns)} columns.")
	print(f"Saved output to {output_path}")


if __name__ == "__main__":
	main()
