"""Single entry point for the pandas operation processors."""

from tableau_engine.functions.datetime import DateTimeProcessor
from tableau_engine.functions.io import IOProcessor
from tableau_engine.functions.logical import LogicalProcessor
from tableau_engine.functions.numeric import NumericProcessor
from tableau_engine.functions.row import RowProcessor
from tableau_engine.functions.structural import StructuralProcessor
from tableau_engine.functions.text import TextProcessor


class PandasDataProcessor:
	"""Group pandas operations by category without sharing processor instances."""

	def __init__(self) -> None:
		self.structure = StructuralProcessor()
		self.text = TextProcessor()
		self.number = NumericProcessor()
		self.row = RowProcessor()
		self.io = IOProcessor()
		self.datetime = DateTimeProcessor()
		self.logical = LogicalProcessor()
