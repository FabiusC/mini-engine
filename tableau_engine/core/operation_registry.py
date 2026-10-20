"""Map pipeline operation names to the facade that executes them."""

from tableau_engine.interfaces.column import ColumnInterface
from tableau_engine.interfaces.io import IOInterface
from tableau_engine.interfaces.row import RowInterface
from tableau_engine.interfaces.structural import StructuralInterface
from tableau_engine.interfaces.text import TextInterface

OPERATION_INTERFACES = {
	"read_csv": IOInterface,
	"write_csv": IOInterface,
	"inner_join": StructuralInterface,
	"outer_join": StructuralInterface,
	"limit": RowInterface,
	"filter": RowInterface,
	"uppercase": TextInterface,
	"lowercase": TextInterface,
	"add_column": ColumnInterface,
}


def get_interface(operation: str) -> type:
	"""Return the facade registered for an operation name."""
	try:
		return OPERATION_INTERFACES[operation]
	except KeyError as error:
		raise ValueError(f"Unsupported operation {operation!r}") from error
