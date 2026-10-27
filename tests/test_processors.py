"""Check processor methods and operation registry contracts."""

import inspect

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from engine.processors.conversion_processor import ConversionProcessor
from engine.processors.date_processor import DateTimeProcessor
from engine.processors.io_processor import IOProcessor
from engine.processors.logical_processor import LogicalProcessor
from engine.processors.numeric_processor import NumericProcessor
from engine.processors.row_processor import RowProcessor
from engine.processors.structural_processor import StructuralProcessor
from engine.processors.text_processor import TextProcessor
from engine.core.operation_registry import OPERATION_PROCESSORS, get_operation


@pytest.mark.parametrize("processor", [
	NumericProcessor, TextProcessor, StructuralProcessor, RowProcessor,
	IOProcessor, DateTimeProcessor, LogicalProcessor,
	ConversionProcessor,
])
def test_operations_are_instance_methods_on_processor(processor) -> None:
	module = inspect.getmodule(processor)
	assert module is not None
	assert not [
		function for _, function in inspect.getmembers(module, inspect.isfunction)
		if function.__module__ == module.__name__
	]
	methods = [
		method for name, method in vars(processor).items() if not name.startswith("_")
	]
	assert methods
	assert all(inspect.isfunction(method) for method in methods)
	assert all(method.__code__.co_varnames[0] == "self" for method in methods)


def test_operation_registry_routes_names_to_processor_functions() -> None:
	for operation, processor, method_name in [
		("absolute", NumericProcessor, "absolute"),
		("lowercase", TextProcessor, "lowercase"),
		("date", ConversionProcessor, "date"),
		("read_csv", IOProcessor, "read_csv"),
		("sort", RowProcessor, "sort_rows"),
	]:
		function = get_operation(operation)
		assert function.__self__.__class__ is processor
		assert function.__func__ is getattr(processor, method_name)
	assert all(callable(operation) for operation in OPERATION_PROCESSORS.values())


def test_processor_instances_do_not_mutate_inputs() -> None:
	frame = pd.DataFrame({"v": [-2, 3]})
	expected = pd.DataFrame({"v": [2, 3]})
	assert_frame_equal(NumericProcessor().absolute(frame, column="v"), expected)
	assert frame["v"].tolist() == [-2, 3]
