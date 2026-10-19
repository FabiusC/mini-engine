"""Compile and execute the DAG declared in pipeline.dag.json."""

import json
from pathlib import Path

import pandas as pd

from tableau_engine.core.dag_runner import DAGRunner


def main() -> None:
	"""Run the category-based DAG directly and export its generic AST."""
	project_root = Path(__file__).resolve().parent
	dag_path = project_root / "pipeline.dag.json"
	dag_definition = json.loads(dag_path.read_text(encoding="utf-8"))
	if dag_definition.get("format") != "tableau-engine.dag":
		raise ValueError("Unsupported DAG format")
	if dag_definition.get("version") != 1:
		raise ValueError("Unsupported DAG format version")
	nodes = dag_definition.get("nodes")
	outputs = dag_definition.get("outputs")
	if not isinstance(nodes, list) or not isinstance(outputs, list) or not outputs:
		raise ValueError("DAG JSON must define nodes and at least one output")
	runner = DAGRunner({}, nodes, outputs=outputs, base_dir=project_root)
	context = runner.run()
	if len(outputs) != 1:
		raise ValueError("main.py expects exactly one output node")
	result = context[outputs[0]]
	if not isinstance(result, pd.DataFrame):
		raise TypeError("The pipeline DAG did not produce a DataFrame")

	output_directory = project_root / "output"
	output_path = output_directory / "processed_orders.csv"
	ast_path = project_root / "pipeline.ast.json"
	ast_path.write_text(
		json.dumps(runner.to_ast_dict(), indent=2, ensure_ascii=False) + "\n",
		encoding="utf-8",
	)

	print(f"Processed {len(result)} rows across {len(result.columns)} columns.")
	print(f"Saved output to {output_path}")
	print(f"Compiled AST to {ast_path}")


if __name__ == "__main__":
	main()
