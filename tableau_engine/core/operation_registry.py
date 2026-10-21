"""Map pipeline operation names to the facade that executes them."""

from tableau_engine.interfaces.io import IOInterface
from tableau_engine.interfaces.datetime import DateTimeInterface
from tableau_engine.interfaces.logical import LogicalInterface
from tableau_engine.interfaces.numeric import NumericInterface
from tableau_engine.interfaces.row import RowInterface
from tableau_engine.interfaces.structural import StructuralInterface
from tableau_engine.interfaces.text import TextInterface

OPERATION_INTERFACES = {
	"input": IOInterface,
	"output": IOInterface,
	"join": StructuralInterface,
	"union": StructuralInterface,
	"aggregate": StructuralInterface,
	"pivot": StructuralInterface,
	"drop_column": StructuralInterface,
	"rename_column": StructuralInterface,
	"change_data_type": StructuralInterface,
	"sample": RowInterface,
	**dict.fromkeys(TextInterface._operations, TextInterface),
	**dict.fromkeys(NumericInterface._operations, NumericInterface),
	**dict.fromkeys(DateTimeInterface._operations, DateTimeInterface),
	**dict.fromkeys(LogicalInterface._operations, LogicalInterface),
	"read_csv": IOInterface,
	"write_csv": IOInterface,
	"inner_join": StructuralInterface,
	"outer_join": StructuralInterface,
	"sort": StructuralInterface,
	"drop-column": StructuralInterface,
	"rename-column": StructuralInterface,
	"change-data-type": StructuralInterface,
	"limit": RowInterface,
	"filter": RowInterface,
	"add_column": StructuralInterface,
}


def get_interface(operation: str) -> type:
	"""Return the facade registered for an operation name."""
	try:
		return OPERATION_INTERFACES[operation]
	except KeyError as error:
		raise ValueError(f"Unsupported operation {operation!r}") from error
