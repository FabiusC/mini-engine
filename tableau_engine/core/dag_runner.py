"""Execute an ordered DAG containing joins and text operations."""

from collections.abc import Mapping
from typing import TypedDict

import pandas as pd

from tableau_engine.interfaces.text import TextInterface
from tableau_engine.structural import join


class TextNode(TypedDict):
	"""A text operation consuming the source or a previously defined node."""

	id: str
	input: str
	operation: str
	column: str


class JoinNode(TypedDict):
	"""Join two datasource or node results."""

	id: str
	inputs: list[str]
	operation: str
	left_on: str | list[str]
	right_on: str | list[str]
	how: str


class DAGRunner:
	"""Execute join and text nodes in JSON order."""

	def __init__(self, nodes: list[TextNode | JoinNode]) -> None:
		self.nodes = nodes

	def run(
		self,
		datasources: pd.DataFrame | Mapping[str, pd.DataFrame],
		output: str,
	) -> pd.DataFrame:
		"""Apply each operation and return the selected output dataframe."""
		results = {"source": datasources} if isinstance(datasources, pd.DataFrame) else dict(datasources)
		for node in self.nodes:
			if node["id"] in results:
				raise ValueError(f"Duplicate node id: {node['id']!r}")

			if node["operation"] == "JOIN":
				inputs = node["inputs"]
				if len(inputs) != 2 or any(input_id not in results for input_id in inputs):
					raise ValueError(f"JOIN node {node['id']!r} needs two existing inputs")
				results[node["id"]] = join(
					results[inputs[0]],
					results[inputs[1]],
					left_on=node["left_on"],
					right_on=node["right_on"],
					how=node.get("how", "inner"),
				)
				continue

			input_id = node["input"]
			if input_id not in results:
				raise ValueError(f"Input must precede node {node['id']!r}: {input_id!r}")
			results[node["id"]] = TextInterface.execute(
				node["operation"], results[input_id], column=node["column"]
			)

		if output not in results:
			raise ValueError(f"Unknown DAG output: {output!r}")
		return results[output].copy()
