"""Execute an ordered text DAG without compilation or dependency sorting."""

from typing import TypedDict

import pandas as pd

from tableau_engine.interfaces.text import TextInterface


class TextNode(TypedDict):
	"""A text operation consuming the source or a previously defined node."""

	id: str
	input: str
	operation: str
	column: str


class DAGRunner:
	"""Execute text nodes in JSON order; each input must already exist."""

	def __init__(self, nodes: list[TextNode]) -> None:
		self.nodes = nodes

	def run(self, df: pd.DataFrame, output: str) -> pd.DataFrame:
		"""Apply each operation and return the selected output dataframe."""
		results = {"source": df}
		for node in self.nodes:
			if node["id"] in results:
				raise ValueError(f"Duplicate node id: {node['id']!r}")
			if node["input"] not in results:
				raise ValueError(f"Input must precede node {node['id']!r}: {node['input']!r}")
			results[node["id"]] = TextInterface.execute(
				node["operation"], results[node["input"]], column=node["column"]
			)
		return results[output].copy()
