"""Map pipeline operation names directly to concrete processor methods."""

from collections.abc import Mapping, Sequence
from functools import partial
from typing import Any, Callable

import pandas as pd

from engine.processors.conversion_processor import ConversionProcessor
from engine.processors.date_processor import DateTimeProcessor
from engine.processors.io_processor import IOProcessor
from engine.processors.logical_processor import LogicalProcessor
from engine.processors.numeric_processor import NumericProcessor
from engine.processors.row_processor import RowProcessor
from engine.processors.structural_processor import StructuralProcessor
from engine.processors.text_processor import TextProcessor

Operation = Callable[..., pd.DataFrame]

_conversion = ConversionProcessor()
_date_time = DateTimeProcessor()
_io = IOProcessor()
_logical = LogicalProcessor()
_numeric = NumericProcessor()
_row = RowProcessor()
_structural = StructuralProcessor()
_text = TextProcessor()

OPERATION_PROCESSORS: dict[str, Operation] = {
	"input": _io.input_data,
	"output": _io.output_data,
	"read_csv": _io.read_csv,
	"write_csv": _io.write_csv,
	"date": _conversion.date,
	"datetime": _conversion.datetime,
	"float": _conversion.float,
	"int": _conversion.int,
	"str": _conversion.str,
	"make_date": _conversion.make_date,
	"make_time": _conversion.make_time,
	"make_date_time": _conversion.make_date_time,
	"date_parser": _date_time.date_parser,
	"date_parse": _date_time.date_parse,
	"dateparse": _date_time.date_parse,
	"date_trunc": _date_time.date_trunc,
	"datetrunc": _date_time.date_trunc,
	"day": _date_time.day,
	"iso_quarter": _date_time.iso_quarter,
	"isoquarter": _date_time.iso_quarter,
	"iso_week": _date_time.iso_week,
	"isoweek": _date_time.iso_week,
	"iso_week_day": _date_time.iso_week_day,
	"isoweekday": _date_time.iso_week_day,
	"iso_year": _date_time.iso_year,
	"isoyear": _date_time.iso_year,
	"now": _date_time.now,
	"quarter": _date_time.quarter,
	"today": _date_time.today,
	"week": _date_time.week,
	"year": _date_time.year,
	"date_add": _date_time.date_add,
	"date add": _date_time.date_add,
	"dateadd": _date_time.date_add,
	"date_sub": _date_time.date_sub,
	"date_diff": _date_time.date_diff,
	"date diff": _date_time.date_diff,
	"datediff": _date_time.date_diff,
	"date_name": _date_time.date_name,
	"date name": _date_time.date_name,
	"datename": _date_time.date_name,
	"month": _date_time.month,
	"extract_date_part": _date_time.extract_date_part,
	"coalesce": _logical.coalesce,
	"ifnull": _logical.coalesce,
	"conditional_map": _logical.conditional_map,
	"and": partial(_logical.logical, operation="and"),
	"case": partial(_logical.logical, operation="case"),
	"if": partial(_logical.logical, operation="if"),
	"elseif": partial(_logical.logical, operation="elseif"),
	"or": partial(_logical.logical, operation="or"),
	"not": partial(_logical.logical, operation="not"),
	"absolute": _numeric.absolute,
	"abs": _numeric.absolute,
	"arithmetic": _numeric.arithmetic,
	"ceiling": _numeric.ceiling,
	"clean_float": _numeric.clean_float,
	"floor": _numeric.floor,
	"max": _numeric.max,
	"min": _numeric.min,
	"power": _numeric.power,
	"round": _numeric.round_column,
	"filter": _row.filter_rows,
	"limit": _row.limit_rows,
	"sample": _row.sample,
	"union": _structural.union,
	"join": _structural.join,
	"inner_join": partial(_structural.join, how="inner"),
	"outer_join": partial(_structural.join, how="outer"),
	"add_column": _structural.add_column,
	"sort": _structural.sort_rows,
	"drop-column": _structural.drop_column,
	"drop_column": _structural.drop_column,
	"rename-column": _structural.rename_column,
	"rename_column": _structural.rename_column,
	"change-data-type": _structural.change_data_type,
	"change_data_type": _structural.change_data_type,
	"aggregate": _structural.aggregate,
	"pivot": _structural.pivot,
	"uppercase": _text.uppercase,
	"upper": _text.uppercase,
	"proper": _text.proper,
	"propper": _text.propper,
	"lowercase": _text.lowercase,
	"lower": _text.lowercase,
	"trim": _text.trim,
	"ltrim": _text.ltrim,
	"rtrim": _text.rtrim,
	"substring": _text.substring,
	"replace": _text.replace,
	"split": _text.split,
	"concat_column": _text.concat_column,
	"concat_text": _text.concat_text,
	"contains": _text.contains,
	"starts_with": _text.starts_with,
	"ends_with": _text.ends_with,
	"transform_left": _text.transform_left,
	"transform_right": _text.transform_right,
	"length": _text.length,
}

_ZERO_INPUT_OPERATIONS = {"input", "read_csv"}
_MULTI_INPUT_OPERATIONS = {"union"}
_TWO_INPUT_OPERATIONS = {"join", "inner_join", "outer_join"}


def _require_inputs(operation: str, inputs: Sequence[pd.DataFrame], count: int) -> None:
	"""Validate the number of dataframes supplied for a pipeline operation."""
	if len(inputs) != count:
		raise ValueError(
			f"{operation} requires {count} input dataframe(s), received {len(inputs)}"
		)


def get_operation(operation: str) -> Operation:
	"""Return the concrete processor method for a pipeline operation name."""
	try:
		return OPERATION_PROCESSORS[operation.lower()]
	except KeyError as error:
		raise ValueError(f"Unsupported operation {operation!r}") from error


def execute_operation(
	operation: str,
	inputs: Sequence[pd.DataFrame],
	parameters: Mapping[str, Any] | None = None,
	**overrides: Any,
) -> pd.DataFrame:
	"""Dispatch inputs to the concrete method registered for an operation."""
	operation = operation.lower()
	function = get_operation(operation)
	arguments = dict(parameters or {})
	arguments.update(overrides)
	if operation in _ZERO_INPUT_OPERATIONS:
		_require_inputs(operation, inputs, 0)
		return function(**arguments)
	if operation in _MULTI_INPUT_OPERATIONS:
		if not inputs:
			raise ValueError(f"{operation} requires at least one input dataframe")
		return function(inputs, **arguments)
	if operation in _TWO_INPUT_OPERATIONS:
		_require_inputs(operation, inputs, 2)
		return function(inputs[0], inputs[1], **arguments)
	_require_inputs(operation, inputs, 1)
	return function(inputs[0], **arguments)
