"""Check pandas operation methods and how the pandas emitter routes catalog names to them."""

import inspect

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from script_builder.operations.pandas import (
	ConversionOperations,
	DateTimeOperations,
	IOOperations,
	LogicalOperations,
	NumericOperations,
	RowOperations,
	StructuralOperations,
	TextOperations,
)
from script_builder.codegen.pandas import PandasEmitter
from script_builder.ir.catalog import OPERATIONS


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


def test_pandas_emitter_routes_catalog_names_to_pandas_operations() -> None:
	for operation, implementation, method_name in [
		("absolute", NumericOperations, "absolute"),
		("lowercase", TextOperations, "lowercase"),
		("date", ConversionOperations, "date"),
		("read_csv", IOOperations, "read_csv"),
		("sort", RowOperations, "sort_rows"),
	]:
		assert PandasEmitter.implementations[operation] == (implementation, method_name)
	# fx is compiled from its expression instead of routed to a method.
	assert set(PandasEmitter.implementations) == set(OPERATIONS) - {"fx"}
	assert all(
		callable(getattr(owner, method)) for owner, method in PandasEmitter.implementations.values()
	)


def test_pandas_operations_do_not_mutate_inputs() -> None:
	frame = pd.DataFrame({"v": [-2, 3]})
	expected = pd.DataFrame({"v": [2, 3]})
	assert_frame_equal(NumericOperations().absolute(frame, column="v"), expected)
	assert frame["v"].tolist() == [-2, 3]
