from engine.operations.polars.date import PolarsDateOperations
from engine.operations.polars.conversion import PolarsConversionOperations
from engine.operations.polars.date import PolarsDateOperations
from engine.operations.polars.io import PolarsIOOperations
from engine.operations.polars.logical import PolarsLogicalOperations
from engine.operations.polars.numeric import PolarsNumericOperations
from engine.operations.polars.row import PolarsRowOperations
from engine.operations.polars.structural import PolarsStructuralOperations
from engine.operations.polars.text import PolarsTextOperations


class PolarsOperations(
	PolarsIOOperations,
	PolarsStructuralOperations,
	PolarsRowOperations,
	PolarsDateOperations,
	PolarsConversionOperations,
	PolarsLogicalOperations,
	PolarsNumericOperations,
	PolarsTextOperations,
):
	"""Full Polars operation set composed by responsibility."""


__all__ = ["PolarsOperations"]
