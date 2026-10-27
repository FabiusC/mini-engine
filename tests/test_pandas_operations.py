"""Check pandas operation methods and the local reference registry."""

import inspect

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from engine.operations.pandas import (
	ConversionOperations,
	DateTimeOperations,
	IOOperations,
	LogicalOperations,
	NumericOperations,
	RowOperations,
	StructuralOperations,
	TextOperations,
)
from engine.core.operation_registry import OPERATION_FUNCTIONS, get_operation


@pytest.mark.parametrize("operations", [
	NumericOperations, TextOperations, StructuralOperations, RowOperations,
	IOOperations, DateTimeOperations, LogicalOperations, ConversionOperations,
])
def test_pandas_operations_are_instance_methods(operations) -> None:
	module = inspect.getmodule(operations)
	assert module is not None
	assert not [
		function for _, function in inspect.getmembers(module, inspect.isfunction)
		if function.__module__ == module.__name__
	]
	methods = [
		method for name, method in vars(operations).items() if not name.startswith("_")
	]
	assert methods
	assert all(inspect.isfunction(method) for method in methods)
	assert all(method.__code__.co_varnames[0] == "self" for method in methods)


def test_operation_registry_routes_names_to_pandas_operations() -> None:
	for operation, implementation, method_name in [
		("absolute", NumericOperations, "absolute"),
		("lowercase", TextOperations, "lowercase"),
		("date", ConversionOperations, "date"),
		("read_csv", IOOperations, "read_csv"),
		("sort", RowOperations, "sort_rows"),
	]:
		function = get_operation(operation)
		assert function.__self__.__class__ is implementation
		assert function.__func__ is getattr(implementation, method_name)
	assert all(callable(operation) for operation in OPERATION_FUNCTIONS.values())


def test_pandas_operations_do_not_mutate_inputs() -> None:
	frame = pd.DataFrame({"v": [-2, 3]})
	expected = pd.DataFrame({"v": [2, 3]})
	assert_frame_equal(NumericOperations().absolute(frame, column="v"), expected)
	assert frame["v"].tolist() == [-2, 3]
