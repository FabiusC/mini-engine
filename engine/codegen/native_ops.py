"""Trusted native helpers; backend dependencies are imported only in generated code."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	import polars as pl
	import pyarrow as pa
	import pyarrow.compute as pc
	import pyarrow.csv as pacsv
	import pyarrow.parquet as pq
	from pyspark.sql import SparkSession, functions as F


class PolarsOps:
	def read_csv(self, filepath):
		return pl.read_csv(filepath)

	def write_csv(self, df, filepath, index=False):
		path = Path(filepath)
		path.parent.mkdir(parents=True, exist_ok=True)
		df.write_csv(path)
		return df

	def input(self, source_type, filepath_or_connection, table_or_sheet=None, encoding="utf-8", delimiter=","):
		if source_type == "csv":
			return pl.read_csv(filepath_or_connection, separator=delimiter)
		return pl.read_parquet(filepath_or_connection)

	def output(self, df, destination_type, output_path, write_mode="overwrite", encoding="utf-8", delimiter=","):
		path = Path(output_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		if destination_type == "csv":
			df.write_csv(path, separator=delimiter)
		else:
			df.write_parquet(path)
		return df

	def add_column(self, df, column_name, value=None):
		if column_name in df.columns:
			raise ValueError(f"Column {column_name!r} already exists")
		return df.with_columns(pl.lit(value).alias(column_name))

	def drop_column(self, df, column=None, *, columns=None):
		names = columns if columns is not None else column
		return df.drop(names)

	def rename_column(self, df, column, new_name):
		if column not in df.columns:
			raise ValueError(f"Column {column!r} does not exist")
		if column != new_name and new_name in df.columns:
			raise ValueError(f"Column {new_name!r} already exists")
		return df.rename({column: new_name})

	def target(self, df, column, create_new_column=False, new_column_name=None):
		if column not in df.columns:
			raise ValueError(f"Column {column!r} does not exist")
		if not create_new_column:
			return column
		if new_column_name:
			if new_column_name in df.columns:
				raise ValueError(f"Column {new_column_name!r} already exists")
			return new_column_name
		name, index = f"{column}_processed", 1
		while name in df.columns:
			name = f"{column}_processed_{index}"
			index += 1
		return name

	def change_data_type(self, df, column, new_type=None, *, target_type=None, create_new_column=False, new_column_name=None):
		dtypes = {"int": pl.Int64, "int64": pl.Int64, "float": pl.Float64, "float64": pl.Float64,
			"str": pl.String, "string": pl.String, "bool": pl.Boolean, "datetime": pl.Datetime}
		dtype = target_type or new_type
		target = self.target(df, column, create_new_column, new_column_name)
		value = pl.col(column).str.to_datetime(strict=True) if dtype == "datetime" and df.schema[column] == pl.String else pl.col(column).cast(dtypes[dtype], strict=True)
		return df.with_columns(value.alias(target))

	def join(self, left, right, how="inner", left_on=None, right_on=None, suffixes=("_x", "_y")):
		keys = [left_on] if isinstance(left_on, str) else left_on
		overlap = (set(left.columns) & set(right.columns)) - set(keys)
		left = left.rename({name: name + "_x" for name in overlap})
		right = right.rename({name: name + "_y" for name in overlap})
		columns = left.columns + [name for name in right.columns if name not in keys]
		return left.join(right, on=keys, how="full" if how == "outer" else how, nulls_equal=True, coalesce=True).select(columns)

	def union(self, df_list, match_type="auto"):
		frames = list(df_list)
		if match_type == "manual":
			if any(len(frame.columns) != len(frames[0].columns) for frame in frames):
				raise ValueError("manual union requires equal column counts")
			frames = [frame.rename(dict(zip(frame.columns, frames[0].columns))) for frame in frames]
		return pl.concat(frames, how="diagonal_relaxed")

	def filter(self, df, column, operator, value=None):
		item = pl.col(column)
		if operator == "isnull":
			mask = item.is_null()
		elif operator == "contains":
			mask = item.cast(pl.String).str.contains(str(value), literal=True)
		else:
			comparisons = {"==": item == value, "!=": item != value, ">": item > value,
				"<": item < value, ">=": item >= value, "<=": item <= value}
			mask = comparisons[operator]
		return df.filter(mask.fill_null(False))

	def limit(self, df, limit):
		return df.head(limit)

	def sort(self, df, column, direction="asc"):
		return df.sort(column, descending=direction.lower() != "asc", nulls_last=True)

	def year(self, df, column, create_new_column=False, new_column_name=None):
		target = self.target(df, column, create_new_column, new_column_name)
		return df.with_columns(pl.col(column).cast(pl.String).str.to_datetime(strict=True).dt.year().alias(target))

	def month(self, df, column, create_new_column=False, new_column_name=None):
		target = self.target(df, column, create_new_column, new_column_name)
		return df.with_columns(pl.col(column).cast(pl.String).str.to_datetime(strict=True).dt.month().alias(target))

	def day(self, df, column, create_new_column=False, new_column_name=None):
		target = self.target(df, column, create_new_column, new_column_name)
		return df.with_columns(pl.col(column).cast(pl.String).str.to_datetime(strict=True).dt.day().alias(target))


class SparkOps:
	def read_csv(self, filepath):
		return SparkSession.builder.getOrCreate().read.option("header", True).option("inferSchema", True).csv(str(filepath))

	def write_csv(self, df, filepath, index=False):
		df.write.mode("overwrite").option("header", True).csv(str(filepath))
		return df

	def input(self, source_type, filepath_or_connection, table_or_sheet=None, encoding="utf-8", delimiter=","):
		reader = SparkSession.builder.getOrCreate().read
		if source_type == "csv":
			return reader.option("header", True).option("inferSchema", True).option("sep", delimiter).csv(str(filepath_or_connection))
		return reader.parquet(str(filepath_or_connection))

	def output(self, df, destination_type, output_path, write_mode="overwrite", encoding="utf-8", delimiter=","):
		writer = df.write.mode("overwrite")
		if destination_type == "csv":
			writer.option("header", True).option("sep", delimiter).csv(str(output_path))
		else:
			writer.parquet(str(output_path))
		return df

	def add_column(self, df, column_name, value=None):
		if column_name in df.columns:
			raise ValueError(f"Column {column_name!r} already exists")
		return df.withColumn(column_name, F.lit(value))

	def drop_column(self, df, column=None, *, columns=None):
		names = columns if columns is not None else column
		names = [names] if isinstance(names, str) else names
		if set(names) - set(df.columns):
			raise ValueError("Missing drop columns")
		return df.drop(*names)

	def rename_column(self, df, column, new_name):
		if column not in df.columns or (column != new_name and new_name in df.columns):
			raise ValueError("Missing source or existing destination column")
		return df.withColumnRenamed(column, new_name)

	def target(self, df, column, create_new_column=False, new_column_name=None):
		if column not in df.columns:
			raise ValueError(f"Column {column!r} does not exist")
		if not create_new_column:
			return column
		if new_column_name:
			if new_column_name in df.columns:
				raise ValueError(f"Column {new_column_name!r} already exists")
			return new_column_name
		name, index = f"{column}_processed", 1
		while name in df.columns:
			name = f"{column}_processed_{index}"
			index += 1
		return name

	def change_data_type(self, df, column, new_type=None, *, target_type=None, create_new_column=False, new_column_name=None):
		dtypes = {"int": "long", "int64": "long", "float": "double", "float64": "double",
			"str": "string", "string": "string", "bool": "boolean", "datetime": "timestamp"}
		return df.withColumn(self.target(df, column, create_new_column, new_column_name), df[column].cast(dtypes[target_type or new_type]))

	def join(self, left, right, how="inner", left_on=None, right_on=None, suffixes=("_x", "_y")):
		keys = [left_on] if isinstance(left_on, str) else left_on
		left, right = left.alias("_l"), right.alias("_r")
		condition = left[keys[0]].eqNullSafe(right[keys[0]])
		for key in keys[1:]:
			condition = condition & left[key].eqNullSafe(right[key])
		overlap = (set(left.columns) & set(right.columns)) - set(keys)
		selected = [
			F.coalesce(left[name], right[name]).alias(name) if name in keys
			else left[name].alias(name + "_x" if name in overlap else name)
			for name in left.columns
		]
		selected += [right[name].alias(name + "_y" if name in overlap else name) for name in right.columns if name not in keys]
		return left.join(right, condition, how).select(*selected)

	def union(self, df_list, match_type="auto"):
		result = df_list[0]
		for frame in df_list[1:]:
			if match_type == "manual":
				if len(frame.columns) != len(result.columns):
					raise ValueError("manual union requires equal column counts")
				frame = frame.toDF(*result.columns)
			result = result.unionByName(frame, allowMissingColumns=True)
		return result

	def filter(self, df, column, operator, value=None):
		item = df[column]
		if operator == "isnull":
			mask = item.isNull()
		elif operator == "contains":
			mask = item.cast("string").contains(str(value))
		else:
			comparisons = {"==": lambda: item == value, "!=": lambda: item != value,
				">": lambda: item > value, "<": lambda: item < value,
				">=": lambda: item >= value, "<=": lambda: item <= value}
			mask = comparisons[operator]()
		return df.filter(mask)

	def limit(self, df, limit):
		return df.limit(limit)

	def sort(self, df, column, direction="asc"):
		value = df[column].asc_nulls_last() if direction.lower() == "asc" else df[column].desc_nulls_last()
		return df.orderBy(value)

	def year(self, df, column, create_new_column=False, new_column_name=None):
		return df.withColumn(self.target(df, column, create_new_column, new_column_name), F.year(F.to_timestamp(df[column])))

	def month(self, df, column, create_new_column=False, new_column_name=None):
		return df.withColumn(self.target(df, column, create_new_column, new_column_name), F.month(F.to_timestamp(df[column])))

	def day(self, df, column, create_new_column=False, new_column_name=None):
		return df.withColumn(self.target(df, column, create_new_column, new_column_name), F.dayofmonth(F.to_timestamp(df[column])))


class ArrowOps:
	def read_csv(self, filepath):
		return pacsv.read_csv(str(filepath))

	def write_csv(self, df, filepath, index=False):
		path = Path(filepath)
		path.parent.mkdir(parents=True, exist_ok=True)
		pacsv.write_csv(df, str(path))
		return df

	def input(self, source_type, filepath_or_connection, table_or_sheet=None, encoding="utf-8", delimiter=","):
		if source_type == "csv":
			return pacsv.read_csv(str(filepath_or_connection), parse_options=pacsv.ParseOptions(delimiter=delimiter))
		return pq.read_table(str(filepath_or_connection))

	def output(self, df, destination_type, output_path, write_mode="overwrite", encoding="utf-8", delimiter=","):
		path = Path(output_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		if destination_type == "csv":
			pacsv.write_csv(df, str(path), write_options=pacsv.WriteOptions(delimiter=delimiter))
		else:
			pq.write_table(df, str(path))
		return df

	def add_column(self, df, column_name, value=None):
		if column_name in df.column_names:
			raise ValueError(f"Column {column_name!r} already exists")
		return df.append_column(column_name, pa.array([value] * df.num_rows))

	def drop_column(self, df, column=None, *, columns=None):
		names = columns if columns is not None else column
		return df.drop([names] if isinstance(names, str) else names)

	def rename_column(self, df, column, new_name):
		if column not in df.column_names or (column != new_name and new_name in df.column_names):
			raise ValueError("Missing source or existing destination column")
		return df.rename_columns([new_name if name == column else name for name in df.column_names])

	def filter(self, df, column, operator, value=None):
		item = df[column]
		if operator == "isnull":
			mask = pc.is_null(item)
		elif operator == "contains":
			mask = pc.match_substring(pc.cast(item, pa.string()), str(value))
		else:
			functions = {"==": pc.equal, "!=": pc.not_equal, ">": pc.greater, "<": pc.less,
				">=": pc.greater_equal, "<=": pc.less_equal}
			mask = functions[operator](item, value)
		return df.filter(pc.fill_null(mask, False))

	def limit(self, df, limit):
		return df.slice(0, limit)

	def sort(self, df, column, direction="asc"):
		return df.sort_by([(column, "ascending" if direction.lower() == "asc" else "descending")])

	def union(self, df_list, match_type="auto"):
		frames = list(df_list)
		if match_type == "manual":
			if any(frame.num_columns != frames[0].num_columns for frame in frames):
				raise ValueError("manual union requires equal column counts")
			frames = [frame.rename_columns(frames[0].column_names) for frame in frames]
		return pa.concat_tables(frames, promote_options="permissive")


def spark_stats(frame):
	return {"rows": frame.count(), "columns": len(frame.columns)}


def arrow_stats(frame):
	return {"rows": frame.num_rows, "columns": frame.num_columns}
