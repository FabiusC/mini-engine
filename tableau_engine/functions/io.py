"""Pandas-backed dataset input and output operations."""

from pathlib import Path

import pandas as pd

from tableau_engine.interfaces.io import IOInterface


class IOProcessor(IOInterface):
	"""Stateless io operations for dataframe pipelines."""

	@staticmethod
	def read_csv(filepath: str | Path) -> pd.DataFrame:
		"""Read a CSV as UTF-8, falling back to Latin-1 when decoding fails."""
		try:
			return pd.read_csv(filepath, encoding="utf-8-sig")
		except UnicodeDecodeError:
			return pd.read_csv(filepath, encoding="latin1")

	@staticmethod
	def write_csv(df: pd.DataFrame, filepath: str | Path, index: bool = False) -> pd.DataFrame:
		"""Overwrite the target CSV and return the dataframe unchanged."""
		path = Path(filepath)
		path.parent.mkdir(parents=True, exist_ok=True)
		df.to_csv(path, index=index)
		return df

	@staticmethod
	def input_data(
		source_type: str,
		filepath_or_connection: str | Path,
		table_or_sheet: str | None = None,
		encoding: str = "utf-8",
		delimiter: str = ",",
	) -> pd.DataFrame:
		"""Read a file or a SQL table, propagating pandas/driver errors."""
		if source_type == "csv":
			return pd.read_csv(filepath_or_connection, encoding=encoding, sep=delimiter)
		if source_type == "excel":
			return pd.read_excel(filepath_or_connection, sheet_name=table_or_sheet if table_or_sheet is not None else 0)
		if source_type == "parquet":
			return pd.read_parquet(filepath_or_connection)
		if source_type == "sql":
			if not table_or_sheet:
				raise ValueError("SQL input requires table_or_sheet")
			return pd.read_sql_table(table_or_sheet, con=str(filepath_or_connection))
		raise ValueError(f"Unsupported source_type: {source_type!r}")

	@staticmethod
	def output_data(
		df: pd.DataFrame,
		destination_type: str,
		output_path: str | Path,
		write_mode: str = "overwrite",
		*,
		encoding: str = "utf-8",
		delimiter: str = ",",
	) -> pd.DataFrame:
		"""Persist data; append preserves existing rows and validates column names/order."""
		if destination_type not in ("csv", "excel", "parquet"):
			raise ValueError(f"Unsupported destination_type: {destination_type!r}")
		if write_mode not in ("overwrite", "append"):
			raise ValueError("write_mode must be 'overwrite' or 'append'")
		path = Path(output_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		append = write_mode == "append" and path.exists() and path.stat().st_size > 0
		if append:
			existing = IOProcessor.input_data(destination_type, path, encoding=encoding, delimiter=delimiter)
			if list(existing.columns) != list(df.columns):
				raise ValueError("append requires matching column names and order")
			values = pd.concat([existing, df], ignore_index=True)
		else:
			values = df
		if destination_type == "csv":
			values.to_csv(path, index=False, encoding=encoding, sep=delimiter)
		elif destination_type == "excel":
			if append:
				with pd.ExcelFile(path) as workbook:
					sheet = workbook.sheet_names[0]
				with pd.ExcelWriter(path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
					values.to_excel(writer, sheet_name=sheet, index=False)
			else:
				values.to_excel(path, index=False)
		else:
			values.to_parquet(path, index=False)
		return df
