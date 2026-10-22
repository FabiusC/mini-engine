"""Single entry point for the pandas operation processors."""

from engine.processors.conversion_processor import ConversionProcessor
from engine.processors.date_processor import DateTimeProcessor
from engine.processors.io_processor import IOProcessor
from engine.processors.logical_processor import LogicalProcessor
from engine.processors.numeric_processor import NumericProcessor
from engine.processors.row_processor import RowProcessor
from engine.processors.structural_processor import StructuralProcessor
from engine.processors.text_processor import TextProcessor


class PandasDataProcessor:
	"""Group pandas operations by category without sharing processor instances."""

	def __init__(self) -> None:
		self.structure = StructuralProcessor()
		self.text = TextProcessor()
		self.number = NumericProcessor()
		self.row = RowProcessor()
		self.io = IOProcessor()
		self.datetime = DateTimeProcessor()
		self.conversion = ConversionProcessor()
		self.logical = LogicalProcessor()
