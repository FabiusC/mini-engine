"""Read a CSV, apply the text DAG, and save the result."""

import json
from pathlib import Path

import pandas as pd

from tableau_engine.core.dag_runner import DAGRunner


def main() -> None:
	"""Process South orders using the editable text DAG."""
	project_root = Path(__file__).resolve().parent
	dag_path = project_root / "pipeline.dag.json"
	dag = json.loads(dag_path.read_text(encoding="utf-8"))
	input_path = project_root / "data" / "orders_south_2018.csv"
	try:
		data = pd.read_csv(input_path, encoding="utf-8-sig")
	except UnicodeDecodeError:
		data = pd.read_csv(input_path, encoding="latin1")
	result = DAGRunner(dag["nodes"]).run(data, dag["output"])
	output_path = project_root / "output" / "processed_orders.csv"
	output_path.parent.mkdir(parents=True, exist_ok=True)
	result.to_csv(output_path, index=False)

	print(f"Processed {len(result)} rows across {len(result.columns)} columns.")
	print(f"Saved output to {output_path}")


if __name__ == "__main__":
	main()
