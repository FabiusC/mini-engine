"""Compile and execute the DAG declared in pipeline.dag.json."""

from pathlib import Path

import pandas as pd

from src.engine import DAG


def main() -> None:
	"""Load the DAG JSON, export its AST, and write the processed data."""
	project_root = Path(__file__).resolve().parent
	dag_path = project_root / "pipeline.dag.json"
	dag = DAG.from_json(dag_path.read_text(encoding="utf-8"), base_dir=project_root)
	pipeline_ast = dag.to_ast()
	result = pipeline_ast.run()
	if not isinstance(result, pd.DataFrame):
		raise TypeError("The pipeline AST did not produce a DataFrame")

	output_directory = project_root / "output"
	output_directory.mkdir(parents=True, exist_ok=True)
	output_path = output_directory / "processed_orders.csv"
	result.to_csv(output_path, index=False)
	ast_path = project_root / "pipeline.ast.json"
	ast_path.write_text(pipeline_ast.to_json() + "\n", encoding="utf-8")

	print(f"Processed {len(result)} rows across {len(result.columns)} columns.")
	print(f"Saved output to {output_path}")
	print(f"Compiled AST to {ast_path}")


if __name__ == "__main__":
	main()
