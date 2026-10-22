"""Check the public processor API and facade bindings."""

import inspect

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from tableau_engine import PandasDataProcessor
from tableau_engine.functions.conversion import ConversionProcessor
from tableau_engine.functions.datetime import DateTimeProcessor
from tableau_engine.functions.io import IOProcessor
from tableau_engine.functions.logical import LogicalProcessor
from tableau_engine.functions.numeric import NumericProcessor
from tableau_engine.functions.row import RowProcessor
from tableau_engine.functions.structural import StructuralProcessor
from tableau_engine.functions.text import TextProcessor
from tableau_engine.interfaces.datetime import DateTimeInterface
from tableau_engine.interfaces.conversion import ConversionInterface
from tableau_engine.interfaces.io import IOInterface
from tableau_engine.interfaces.logical import LogicalInterface
from tableau_engine.interfaces.numeric import NumericInterface
from tableau_engine.interfaces.row import RowInterface
from tableau_engine.interfaces.structural import StructuralInterface
from tableau_engine.interfaces.text import TextInterface


@pytest.mark.parametrize("processor", [
	NumericProcessor, TextProcessor, StructuralProcessor, RowProcessor,
	IOProcessor, DateTimeProcessor, LogicalProcessor,
	ConversionProcessor,
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


@pytest.mark.parametrize("interface, processor", [
	(NumericInterface, NumericProcessor),
	(TextInterface, TextProcessor),
	(RowInterface, RowProcessor),
	(StructuralInterface, StructuralProcessor),
	(IOInterface, IOProcessor),
	(ConversionInterface, ConversionProcessor),
	(DateTimeInterface, DateTimeProcessor),
	(LogicalInterface, LogicalProcessor),
])
def test_processors_implement_abstract_interface_contracts(interface, processor) -> None:
	assert inspect.isabstract(interface)
	assert not inspect.isabstract(processor)
	assert issubclass(processor, interface)
	assert set(interface.__abstractmethods__).issubset(vars(processor))


def test_processor_calls_support_classes_and_instances_without_shared_state() -> None:
	frame = pd.DataFrame({"v": [-2, 3]})
	expected = pd.DataFrame({"v": [2, 3]})
	assert_frame_equal(NumericProcessor.absolute(frame, column="v"), expected)
	assert_frame_equal(NumericProcessor().absolute(frame, column="v"), expected)
	assert frame["v"].tolist() == [-2, 3]


@pytest.mark.parametrize("category, processor", [
	("structure", StructuralProcessor),
	("text", TextProcessor),
	("number", NumericProcessor),
	("row", RowProcessor),
	("io", IOProcessor),
	("datetime", DateTimeProcessor),
	("logical", LogicalProcessor),
	("conversion", ConversionProcessor),
])
def test_pandas_processor_composes_independent_category_instances(category, processor) -> None:
	first = PandasDataProcessor()
	second = PandasDataProcessor()

	assert isinstance(getattr(first, category), processor)
	assert getattr(first, category) is not getattr(second, category)


def test_pandas_processor_transforms_and_persists_without_mutating_input(tmp_path) -> None:
	processor = PandasDataProcessor()
	frame = pd.DataFrame({
		"name": [" Ana ", " Luis "],
		"amount": [-2, 3],
		"date": ["2024-02-29", "2025-01-01"],
		"note": [None, "ok"],
	})
	before = frame.copy(deep=True)

	result = processor.text.trim(frame, column="name")
	result = processor.number.absolute(result, column="amount")
	result = processor.datetime.extract_date_part(result, column="date", part="year")
	result = processor.logical.coalesce(result, column="note", default_value="missing")
	result = processor.structure.rename_column(result, column="date", new_name="year")
	result = processor.row.filter_rows(result, column="amount", operator=">", value=2)
	path = tmp_path / "result.csv"
	processor.io.write_csv(result, filepath=path)
	persisted = processor.io.read_csv(filepath=path)

	assert persisted.to_dict("records") == [
		{"name": "Luis", "amount": 3, "year": 2025, "note": "ok"},
	]
	assert_frame_equal(frame, before)
