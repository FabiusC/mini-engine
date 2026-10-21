"""Check the public processor API and facade bindings."""

import inspect

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from tableau_engine.functions.datetime import DateTimeProcessor
from tableau_engine.functions.io import IOProcessor
from tableau_engine.functions.logical import LogicalProcessor
from tableau_engine.functions.numeric import NumericProcessor
from tableau_engine.functions.row import RowProcessor
from tableau_engine.functions.structural import StructuralProcessor
from tableau_engine.functions.text import TextProcessor
from tableau_engine.interfaces.datetime import DateTimeInterface
from tableau_engine.interfaces.logical import LogicalInterface
from tableau_engine.interfaces.numeric import NumericInterface
from tableau_engine.interfaces.row import RowInterface
from tableau_engine.interfaces.structural import StructuralInterface
from tableau_engine.interfaces.text import TextInterface


@pytest.mark.parametrize("processor", [
	NumericProcessor, TextProcessor, StructuralProcessor, RowProcessor,
	IOProcessor, DateTimeProcessor, LogicalProcessor,
])
def test_operations_are_contained_in_processor_as_static_methods(processor) -> None:
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
	assert all(isinstance(method, staticmethod) for method in methods)


@pytest.mark.parametrize("interface, processor, mapping_name", [
	(NumericInterface, NumericProcessor, "_operations"),
	(TextInterface, TextProcessor, "_operations"),
	(RowInterface, RowProcessor, "_operations"),
	(StructuralInterface, StructuralProcessor, "_transformations"),
	(DateTimeInterface, DateTimeProcessor, "_operations"),
	(LogicalInterface, LogicalProcessor, "_operations"),
])
def test_facades_bind_processor_methods(interface, processor, mapping_name) -> None:
	for function in getattr(interface, mapping_name).values():
		assert function is getattr(processor, function.__name__)


def test_processor_calls_support_classes_and_instances_without_shared_state() -> None:
	frame = pd.DataFrame({"v": [-2, 3]})
	expected = pd.DataFrame({"v": [2, 3]})
	assert_frame_equal(NumericProcessor.absolute(frame, column="v"), expected)
	assert_frame_equal(NumericProcessor().absolute(frame, column="v"), expected)
	assert frame["v"].tolist() == [-2, 3]
