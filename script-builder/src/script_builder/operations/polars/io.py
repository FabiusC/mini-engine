from pathlib import Path


class PolarsIOOperations:
	def read_csv(self, filepath):
		"""Read a CSV as UTF-8, falling back to Latin-1 when decoding fails."""
		try:
			return pl.read_csv(filepath)
		except pl.exceptions.ComputeError as error:
			if "utf-8" not in str(error).lower():
				raise
			return pl.read_csv(filepath, encoding="latin1")

	def write_csv(self, df, filepath, index=False):
		path = Path(filepath)
		path.parent.mkdir(parents=True, exist_ok=True)
		df.write_csv(path)
		return df

	def input(self, source_type, filepath_or_connection, table_or_sheet=None, encoding="utf-8", delimiter=","):
		if source_type == "csv":
			polars_encoding = "utf8" if encoding.lower().replace("-", "") in ("utf8", "utf8sig") else encoding
			return pl.read_csv(filepath_or_connection, separator=delimiter, encoding=polars_encoding)
		if source_type != "parquet":
			raise ValueError("Polars input supports only csv and parquet")
		return pl.read_parquet(filepath_or_connection)

	def output(self, df, destination_type, output_path, write_mode="overwrite", encoding="utf-8", delimiter=","):
		path = Path(output_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		if destination_type not in ("csv", "parquet"):
			raise ValueError("Polars output supports only csv and parquet")
		if write_mode not in ("overwrite", "append"):
			raise ValueError("write_mode must be 'overwrite' or 'append'")
		if write_mode == "append" and path.exists():
			existing = pl.read_csv(path, separator=delimiter) if destination_type == "csv" else pl.read_parquet(path)
			if existing.columns != df.columns:
				raise ValueError("append requires matching column names and order")
			df = pl.concat([existing, df], how="vertical")
		if destination_type == "csv":
			df.write_csv(path, separator=delimiter)
		else:
			df.write_parquet(path)
		return df
