"""Map pipeline operation names directly to concrete processor methods."""

from collections.abc import Mapping, Sequence
from functools import partial
from typing import Any, Callable

import pandas as pd

from tableau_engine.functions.conversion import ConversionProcessor
from tableau_engine.functions.datetime import DateTimeProcessor
from tableau_engine.functions.io import IOProcessor
from tableau_engine.functions.logical import LogicalProcessor
from tableau_engine.functions.numeric import NumericProcessor
from tableau_engine.functions.row import RowProcessor
from tableau_engine.functions.structural import StructuralProcessor
from tableau_engine.functions.text import TextProcessor
from tableau_engine.interfaces.inputs import require_inputs

Operation = Callable[..., pd.DataFrame]

OPERATION_PROCESSORS: dict[str, Operation] = {
	"input": IOProcessor.input_data,
	"output": IOProcessor.output_data,
	"read_csv": IOProcessor.read_csv,
	"write_csv": IOProcessor.write_csv,
	"date": ConversionProcessor.date,
	"datetime": ConversionProcessor.datetime,
	"float": ConversionProcessor.float,
	"int": ConversionProcessor.int,
	"str": ConversionProcessor.str,
	"make_date": ConversionProcessor.make_date,
	"make_time": ConversionProcessor.make_time,
	"make_date_time": ConversionProcessor.make_date_time,
	"date_parser": DateTimeProcessor.date_parser,
	"date_add": DateTimeProcessor.date_add,
	"date_sub": DateTimeProcessor.date_sub,
	"date_diff": DateTimeProcessor.date_diff,
	"extract_date_part": DateTimeProcessor.extract_date_part,
	"coalesce": LogicalProcessor.coalesce,
	"ifnull": LogicalProcessor.coalesce,
	"conditional_map": LogicalProcessor.conditional_map,
	"and": partial(LogicalProcessor.logical, operation="and"),
	"case": partial(LogicalProcessor.logical, operation="case"),
	"if": partial(LogicalProcessor.logical, operation="if"),
	"elseif": partial(LogicalProcessor.logical, operation="elseif"),
	"or": partial(LogicalProcessor.logical, operation="or"),
	"not": partial(LogicalProcessor.logical, operation="not"),
	"absolute": NumericProcessor.absolute,
	"abs": NumericProcessor.absolute,
	"arithmetic": NumericProcessor.arithmetic,
	"ceiling": NumericProcessor.ceiling,
	"clean_float": NumericProcessor.clean_float,
	"floor": NumericProcessor.floor,
	"max": NumericProcessor.max,
	"min": NumericProcessor.min,
	"power": NumericProcessor.power,
	"round": NumericProcessor.round_column,
	"filter": RowProcessor.filter_rows,
	"limit": RowProcessor.limit_rows,
	"sample": RowProcessor.sample,
	"union": StructuralProcessor.union,
	"join": StructuralProcessor.join,
	"inner_join": partial(StructuralProcessor.join, how="inner"),
	"outer_join": partial(StructuralProcessor.join, how="outer"),
	"add_column": StructuralProcessor.add_column,
	"sort": StructuralProcessor.sort_rows,
	"drop-column": StructuralProcessor.drop_column,
	"drop_column": StructuralProcessor.drop_column,
	"rename-column": StructuralProcessor.rename_column,
	"rename_column": StructuralProcessor.rename_column,
	"change-data-type": StructuralProcessor.change_data_type,
	"change_data_type": StructuralProcessor.change_data_type,
	"aggregate": StructuralProcessor.aggregate,
	"pivot": StructuralProcessor.pivot,
	"uppercase": TextProcessor.uppercase,
	"upper": TextProcessor.uppercase,
	"lowercase": TextProcessor.lowercase,
	"lower": TextProcessor.lowercase,
	"trim": TextProcessor.trim,
	"ltrim": TextProcessor.ltrim,
	"rtrim": TextProcessor.rtrim,
	"substring": TextProcessor.substring,
	"replace": TextProcessor.replace,
	"split": TextProcessor.split,
	"concat": TextProcessor.concat,
}

_ZERO_INPUT_OPERATIONS = {"input", "read_csv"}
_MULTI_INPUT_OPERATIONS = {"union"}
_TWO_INPUT_OPERATIONS = {"join", "inner_join", "outer_join"}


def get_operation(operation: str) -> Operation:
	"""Return the concrete processor method for a pipeline operation name."""
	try:
		return OPERATION_PROCESSORS[operation]
	except KeyError as error:
		raise ValueError(f"Unsupported operation {operation!r}") from error


def execute_operation(
	operation: str,
	inputs: Sequence[pd.DataFrame],
	parameters: Mapping[str, Any] | None = None,
	**overrides: Any,
) -> pd.DataFrame:
	"""Dispatch inputs to the concrete method registered for an operation."""
	function = get_operation(operation)
	arguments = dict(parameters or {})
	arguments.update(overrides)
	if operation in _ZERO_INPUT_OPERATIONS:
		require_inputs(operation, inputs, 0)
		return function(**arguments)
	if operation in _MULTI_INPUT_OPERATIONS:
		return function(inputs, **arguments)
	if operation in _TWO_INPUT_OPERATIONS:
		require_inputs(operation, inputs, 2)
		return function(inputs[0], inputs[1], **arguments)
	require_inputs(operation, inputs, 1)
	return function(inputs[0], **arguments)
