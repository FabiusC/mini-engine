"""Structural operations that combine or reshape dataframes."""

from collections.abc import Sequence

import pandas as pd


def add_column(df: pd.DataFrame, column_name: str, value: object = None) -> pd.DataFrame:
	"""Return a copy with a new column filled with a constant value."""
	if column_name in df.columns:
		raise ValueError(f"Column {column_name!r} already exists")
	result = df.copy()
	result[column_name] = value
	return result


def change_data_type(
	df: pd.DataFrame,
	column: str,
	new_type: str | None = None,
	*,
	target_type: str | None = None,
	create_new_column: bool | None = None,
	new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Return a copy with the selected column cast to ``new_type``."""
	if new_type is not None and target_type is not None and new_type != target_type:
		raise ValueError("new_type and target_type must agree")
	dtype = target_type if target_type is not None else new_type
	if dtype is None:
		raise ValueError("target_type is required")
	target = resolve_output_column(
		df, column, new_column, new_column_name, create_new_column=create_new_column
	)
	result = df.copy()
	result[target] = pd.to_datetime(df[column], errors="raise") if dtype == "datetime" else df[column].astype(dtype)
	return result


def drop_column(
	df: pd.DataFrame,
	column: str | Sequence[str] | None = None,
	*,
	columns: Sequence[str] | None = None,
) -> pd.DataFrame:
	"""Return a copy without the requested column or columns."""
	if column is not None and columns is not None:
		raise ValueError("Use column or columns, not both")
	selected = columns if columns is not None else column
	if selected is None:
		raise ValueError("columns is required")
	names = [selected] if isinstance(selected, str) else list(selected)
	missing = [name for name in names if name not in df.columns]
	if missing:
		raise ValueError(f"Columns {missing!r} are not present in the input")
	return df.drop(columns=names)


def join(
	left: pd.DataFrame,
	right: pd.DataFrame,
	how: str = "inner",
	left_on: str | list[str] | None = None,
	right_on: str | list[str] | None = None,
	suffixes: Sequence[str] = ("_x", "_y"),
) -> pd.DataFrame:
	"""Join two dataframes, inferring the key only when exactly one column is shared."""
	if left_on is None and right_on is None:
		shared = [column for column in left.columns if column in right.columns]
		if len(shared) != 1:
			raise ValueError(f"Join needs join keys; shared columns are {shared}")
		left_on = right_on = shared[0]
	if left_on is None or right_on is None:
		raise ValueError("Join needs both left_on and right_on")
	return left.merge(
		right,
		left_on=left_on,
		right_on=right_on,
		how=how,
		suffixes=tuple(suffixes),
	)


def resolve_output_column(
	df: pd.DataFrame,
	column: str,
	new_column: bool = False,
	new_column_name: str | None = None,
	*,
	create_new_column: bool | None = None,
) -> str:
	"""Resolve modern processed names while retaining legacy indexed names."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	if create_new_column is not None:
		if not isinstance(create_new_column, bool):
			raise ValueError("create_new_column must be a boolean")
		if new_column and not create_new_column:
			raise ValueError("new_column and create_new_column must agree")
		new_column = create_new_column
	if new_column_name is not None and (not isinstance(new_column_name, str) or not new_column_name):
		raise ValueError("new_column_name must be a nonempty string")
	if not new_column:
		if new_column_name is not None:
			raise ValueError("new_column_name requires new_column to be true")
		return column
	if new_column_name is not None:
		if new_column_name in df.columns:
			raise ValueError(f"Column {new_column_name!r} already exists")
		return new_column_name
	if create_new_column:
		base = f"{column}_processed"
		target = base
		index = 1
		while target in df.columns:
			target = f"{base}_{index}"
			index += 1
		return target
	index = 1
	while f"{column}_{index}" in df.columns:
		index += 1
	return f"{column}_{index}"


def assign_result(
	df: pd.DataFrame,
	column: str,
	values: pd.Series,
	create_new_column: bool = False,
	new_column_name: str | None = None,
) -> pd.DataFrame:
	"""Assign an aligned transformation result without changing the input."""
	target = resolve_output_column(
		df, column, new_column_name=new_column_name, create_new_column=create_new_column
	)
	result = df.copy()
	result[target] = values
	return result


def union(df_list: Sequence[pd.DataFrame], match_type: str = "auto") -> pd.DataFrame:
	"""Concatenate by column name or by position using the first frame's names."""
	if len(df_list) < 2:
		raise ValueError("union requires at least 2 input dataframes")
	if match_type not in ("auto", "manual"):
		raise ValueError("match_type must be 'auto' or 'manual'")
	frames = list(df_list)
	if match_type == "manual":
		if any(len(frame.columns) != len(frames[0].columns) for frame in frames):
			raise ValueError("manual union requires the same number of columns")
		frames = [frame.set_axis(frames[0].columns, axis=1) for frame in frames]
	return pd.concat(frames, ignore_index=True, sort=False)


def aggregate(
	df: pd.DataFrame,
	group_by: list[str],
	aggregations: dict[str, str | list[str]],
) -> pd.DataFrame:
	"""Aggregate with pandas functions, retaining null grouping keys."""
	if not aggregations:
		raise ValueError("aggregations must not be empty")
	if not group_by:
		return df.groupby(lambda _: 0).agg(aggregations).reset_index(drop=True)
	return df.groupby(group_by, dropna=False, as_index=False).agg(aggregations)


def pivot(
	df: pd.DataFrame,
	pivot_type: str,
	index_cols: list[str],
	target_col: str,
	values_col: str,
) -> pd.DataFrame:
	"""Pivot unique keys or melt all non-index columns into name/value columns."""
	if pivot_type == "columns_to_rows":
		return df.melt(id_vars=index_cols, var_name=target_col, value_name=values_col)
	if pivot_type == "rows_to_columns":
		return df.pivot(index=index_cols, columns=target_col, values=values_col).reset_index()
	raise ValueError("pivot_type must be 'columns_to_rows' or 'rows_to_columns'")


def rename_column(df: pd.DataFrame, column: str, new_name: str) -> pd.DataFrame:
	"""Return a copy with ``column`` renamed to ``new_name``."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	if new_name != column and new_name in df.columns:
		raise ValueError(f"Column {new_name!r} already exists")
	return df.rename(columns={column: new_name})


def sort_rows(
	df: pd.DataFrame,
	column: str,
	direction: str = "asc",
) -> pd.DataFrame:
	"""Return a copy sorted by ``column`` in ascending or descending order."""
	if column not in df.columns:
		raise ValueError(f"Column {column!r} is not present in the input")
	directions = {"asc": True, "desc": False, "des": False}
	try:
		ascending = directions[direction.lower()]
	except (AttributeError, KeyError) as error:
		raise ValueError("direction must be 'asc' or 'desc'") from error
	return df.sort_values(by=column, ascending=ascending)