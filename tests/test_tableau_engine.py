import json

import pandas as pd
import pytest

from tableau_engine.core.dag_runner import DAGRunner
from tableau_engine.interfaces.text import TextInterface


def test_runner_orders_dependencies_and_exports_generic_ast() -> None:
	left = pd.DataFrame({"Segment": ["consumer"]})
	right = pd.DataFrame({"Segment": ["corporate"]})
	plan = [
		{
			"id": "normalized",
			"category": "text",
			"operation": "UPPER",
			"inputs": ["combined"],
			"params": {"column": "Segment"},
		},
		{
			"id": "combined",
			"category": "structural",
			"operation": "UNION",
			"inputs": ["left", "right"],
			"params": {},
		},
	]

	runner = DAGRunner({"left": left, "right": right}, plan, outputs=["normalized"])
	context = runner.run()
	ast = runner.to_ast_dict()

	assert context["normalized"]["Segment"].tolist() == ["CONSUMER", "CORPORATE"]
	assert [node["id"] for node in ast["nodes"]] == ["combined", "normalized"]
	assert ast["nodes"][0]["inputs"] == [{"ref": "left"}, {"ref": "right"}]
	assert ast["outputs"] == [{"ref": "normalized"}]
	json.dumps(ast)


def test_runner_rejects_cycles() -> None:
	plan = [
		{"id": "first", "category": "text", "operation": "UPPER", "inputs": ["second"]},
		{"id": "second", "category": "text", "operation": "LOWER", "inputs": ["first"]},
	]

	with pytest.raises(ValueError, match="Cycle detected"):
		DAGRunner({}, plan)


def test_text_interface_and_numeric_operation_do_not_mutate_input() -> None:
	frame = pd.DataFrame({"text": [" mixed "], "amount": [1.2]})
	upper = TextInterface.execute("UPPER", frame, column="text")

	assert upper["text"].iloc[0] == " MIXED "
	assert frame["text"].iloc[0] == " mixed "
	assert frame["amount"].iloc[0] == 1.2