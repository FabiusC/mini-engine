"""Example pipeline that combines and normalizes the supplied order data."""

from pathlib import Path

import pandas as pd

from src.engine import PipelineEngine
from src.operations import load_csv, transform_string, union_datasets


def _union_with_right_dataset(
	df_left: pd.DataFrame, df_right: pd.DataFrame
) -> pd.DataFrame:
	"""Adapt the union operation to the engine's current-dataframe interface."""
	return union_datasets([df_left, df_right])


def main() -> None:
	"""Load both CSVs, run the pipeline, and write the processed result."""
	project_root = Path(__file__).resolve().parent
	south_data = load_csv(project_root / "data" / "orders_south_2018.csv")
	central_data = load_csv(project_root / "data" / "Orders_Central.csv")

	engine = PipelineEngine(south_data)
	engine.add_step("union datasets", _union_with_right_dataset, central_data)
	engine.add_step("uppercase segment", transform_string, "Segment", "upper")
	result = engine.run()

	output_directory = project_root / "output"
	output_directory.mkdir(parents=True, exist_ok=True)
	output_path = output_directory / "processed_orders.csv"
	result.to_csv(output_path, index=False)

	print(f"Processed {len(result)} rows across {len(result.columns)} columns.")
	print(f"Saved output to {output_path}")
	for state in engine.history:
		print(f"{state.step_name}: {state.row_count} rows, {len(state.columns)} columns")


if __name__ == "__main__":
	main()
