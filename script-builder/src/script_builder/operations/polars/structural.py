class PolarsStructuralOperations:
	def resolve_output_column(self, df, column, create_new_column=False, new_column_name=None):
		if not isinstance(create_new_column, bool):
			raise ValueError("create_new_column must be a boolean")
		if new_column_name is not None and (not isinstance(new_column_name, str) or not new_column_name):
			raise ValueError("new_column_name must be a nonempty string")
		if not create_new_column:
			if new_column_name is not None:
				raise ValueError("new_column_name requires create_new_column to be true")
			return column
		if new_column_name is not None:
			if new_column_name in df.columns:
				raise ValueError(f"Column {new_column_name!r} already exists")
			return new_column_name
		name, index = f"{column}_processed", 1
		while name in df.columns:
			name = f"{column}_processed_{index}"
			index += 1
		return name

	def assign_result(self, df, source, values, create_new_column=False, new_column_name=None):
		target = self.resolve_output_column(df, source, create_new_column, new_column_name)
		return df.with_columns(values.alias(target))

	def add_column(self, df, column_name, value=None):
		if column_name in df.columns:
			raise ValueError(f"Column {column_name!r} already exists")
		return df.with_columns(pl.lit(value).alias(column_name))

	def drop_column(self, df, column=None, *, columns=None):
		if column is not None and columns is not None:
			raise ValueError("Use column or columns, not both")
		names = columns if columns is not None else column
		if names is None:
			raise ValueError("columns is required")
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
		if new_type is not None and target_type is not None and new_type != target_type:
			raise ValueError("new_type and target_type must agree")
		dtypes = {"int": pl.Int64, "int64": pl.Int64, "float": pl.Float64, "float64": pl.Float64,
			"str": pl.String, "string": pl.String, "bool": pl.Boolean, "datetime": pl.Datetime}
		dtype = target_type or new_type
		if dtype not in dtypes:
			raise ValueError(f"Unsupported target_type {dtype!r}")
		target = self.target(df, column, create_new_column, new_column_name)
		value = pl.col(column).str.to_datetime(strict=True) if dtype == "datetime" and df.schema[column] == pl.String else pl.col(column).cast(dtypes[dtype], strict=True)
		return df.with_columns(value.alias(target))

	def join(self, left, right, how="inner", left_on=None, right_on=None, suffixes=("_x", "_y")):
		if left_on is None and right_on is None:
			shared = [name for name in left.columns if name in right.columns]
			if len(shared) != 1:
				raise ValueError(f"Join needs join keys; shared columns are {shared}")
			left_on = right_on = shared[0]
		if left_on is None or right_on is None:
			raise ValueError("Join needs both left_on and right_on")
		keys = [left_on] if isinstance(left_on, str) else left_on
		right_keys = [right_on] if isinstance(right_on, str) else right_on
		if len(keys) != len(right_keys):
			raise ValueError("Join key lists must have the same length")
		if len(suffixes) != 2:
			raise ValueError("suffixes must contain exactly two values")
		left_suffix = suffixes[0] or ""
		right_suffix = suffixes[1] or ""
		if how == "cross":
			overlap = set(left.columns) & set(right.columns)
			left = left.rename({name: name + left_suffix for name in overlap})
			right = right.rename({name: name + right_suffix for name in overlap})
			return left.join(right, how="cross")
		overlap = (set(left.columns) & set(right.columns)) - set(keys) - set(right_keys)
		if overlap and any(name + left_suffix in left.columns for name in overlap):
			raise ValueError("left join suffix creates duplicate column names")
		left = left.rename({name: name + left_suffix for name in overlap})
		right = right.rename({name: name + right_suffix for name in overlap})
		# Match pandas.merge row order: inner/left keep left order, right keeps right order, outer sorts keys.
		joined = left.join(
			right, left_on=keys, right_on=right_keys,
			how="full" if how == "outer" else how,
			nulls_equal=True, coalesce=keys == right_keys,
			maintain_order="right_left" if how == "right" else "left_right",
		)
		if keys == right_keys:
			joined = joined.select([*left.columns, *(name for name in right.columns if name not in right_keys)])
		if how == "outer" and keys == right_keys:
			joined = joined.sort(keys, nulls_last=True, maintain_order=True)
		return joined

	def union(self, df_list, match_type="auto"):
		frames = list(df_list)
		if match_type == "manual":
			if any(len(frame.columns) != len(frames[0].columns) for frame in frames):
				raise ValueError("manual union requires equal column counts")
			frames = [frame.rename(dict(zip(frame.columns, frames[0].columns))) for frame in frames]
		return pl.concat(frames, how="diagonal_relaxed")

	def aggregate(self, df, group_by, aggregations):
		if not aggregations:
			raise ValueError("aggregations must not be empty")
		expressions = []
		for column, functions in aggregations.items():
			for function in ([functions] if isinstance(functions, str) else functions):
				value = pl.col(column)
				aggregate = {
					"sum": value.sum, "min": value.min, "max": value.max,
					"mean": value.mean, "avg": value.mean, "count": value.count,
					"median": value.median, "first": value.first, "last": value.last,
					"nunique": value.n_unique, "std": value.std, "var": value.var,
				}.get(function)
				if aggregate is None:
					raise ValueError(f"Unsupported aggregation: {function!r}")
				expression = aggregate()
				if not isinstance(functions, str):
					expression = expression.alias(f"{column}_{function}")
				expressions.append(expression)
		if group_by:
			return df.group_by(group_by, maintain_order=True).agg(expressions)
		return df.select(expressions)

	def pivot(self, df, pivot_type, index_cols, target_col, values_col):
		if pivot_type == "columns_to_rows":
			return df.unpivot(
				on=[name for name in df.columns if name not in index_cols],
				index=index_cols,
				variable_name=target_col,
				value_name=values_col,
			)
		if pivot_type == "rows_to_columns":
			return df.pivot(
				on=target_col,
				index=index_cols,
				values=values_col,
				aggregate_function=None,
			)
		raise ValueError("pivot_type must be 'columns_to_rows' or 'rows_to_columns'")
