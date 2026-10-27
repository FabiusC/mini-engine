"""Deterministic nbformat 4.5 notebooks, without a builder dependency on Jupyter."""

import json
from typing import Any


def emit_notebook(script: str, framework: str) -> str:
	def cell(cell_id: str, code: str) -> dict[str, Any]:
		return {
			"cell_type": "code", "id": cell_id, "metadata": {},
			"execution_count": None, "outputs": [], "source": code.splitlines(keepends=True),
		}

	definitions = script.rsplit('if __name__ == "__main__":', 1)[0].rstrip() + "\n"
	notebook = {
		"nbformat": 4,
		"nbformat_minor": 5,
		"metadata": {
			"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
			"language_info": {"name": "python"},
			"pipeline": {"framework": framework},
		},
		"cells": [
			cell("pipeline-definitions", definitions),
			cell("runtime-inputs", "parameters = {}\ndatasources = {}\nbase_dir = None\n"),
			cell("execute-pipeline", "results = run(datasources=datasources, parameters=parameters, base_dir=base_dir)\nresults\n"),
		],
	}
	return json.dumps(notebook, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
