"""Structural operations that combine or reshape datasets."""

from tableau_engine.functions.structural.change_data_type import change_data_type
from tableau_engine.functions.structural.add_column import add_column
from tableau_engine.functions.structural.drop_column import drop_column
from tableau_engine.functions.structural.join import join
from tableau_engine.functions.structural.rename_column import rename_column
from tableau_engine.functions.structural.sort_rows import sort_rows

__all__ = [
	"add_column",
	"change_data_type",
	"drop_column",
	"join",
	"rename_column",
	"sort_rows",
]
