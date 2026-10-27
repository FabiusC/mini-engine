from script_builder.operations.polars.date import PolarsDateOperations
from script_builder.operations.polars.conversion import PolarsConversionOperations
from script_builder.operations.polars.date import PolarsDateOperations
from script_builder.operations.polars.io import PolarsIOOperations
from script_builder.operations.polars.logical import PolarsLogicalOperations
from script_builder.operations.polars.numeric import PolarsNumericOperations
from script_builder.operations.polars.row import PolarsRowOperations
from script_builder.operations.polars.structural import PolarsStructuralOperations
from script_builder.operations.polars.text import PolarsTextOperations


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
