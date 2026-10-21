"""Map pipeline operation names to the facade that executes them."""

from tableau_engine.interfaces.io import IOInterface
from tableau_engine.interfaces.datetime import DateTimeInterface
from tableau_engine.interfaces.conversion import ConversionInterface
from tableau_engine.interfaces.logical import LogicalInterface
from tableau_engine.interfaces.numeric import NumericInterface
from tableau_engine.interfaces.row import RowInterface
from tableau_engine.interfaces.structural import StructuralInterface
from tableau_engine.interfaces.text import TextInterface

INTERFACES = (
	IOInterface,
	ConversionInterface,
	DateTimeInterface,
	LogicalInterface,
	NumericInterface,
	RowInterface,
	StructuralInterface,
	TextInterface,
)
OPERATION_INTERFACES = {
	operation: interface
	for interface in INTERFACES
	for operation in interface._operations
}


def get_interface(operation: str) -> type:
	"""Return the facade registered for an operation name."""
	try:
		return OPERATION_INTERFACES[operation]
	except KeyError as error:
		raise ValueError(f"Unsupported operation {operation!r}") from error
