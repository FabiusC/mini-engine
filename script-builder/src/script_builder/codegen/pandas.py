"""Emit explicit calls and only the trusted pandas helpers used by a plan."""

import ast
import inspect
import textwrap
from collections.abc import Callable
from typing import Any

from script_builder.codegen import runtime
from script_builder.ir.catalog import OPERATIONS
from script_builder.ir.plan import ExecutionPlan
from script_builder.ir.validate import parameter_reference, validate_constraints, validate_value
from script_builder.ir.targets import validate_target_parameters
from script_builder.ir.expressions import render_expression
from script_builder.operations.pandas import (
	ConversionOperations,
	DateTimeOperations,
	IOOperations,
	LogicalOperations,
	NumericOperations,
	RowOperations,
	StructuralOperations,
	TextOperations,
)


# Operation name -> (class, method) whose source is copied into the generated script.
# Groups sharing a class and method name are registered in bulk with dict comprehensions.
_IMPLEMENTATIONS: dict[str, tuple[type, str]] = {
	"input": (IOOperations, "input_data"),
	"output": (IOOperations, "output_data"),
	"read_csv": (IOOperations, "read_csv"),
	"write_csv": (IOOperations, "write_csv"),
	"filter": (RowOperations, "filter_rows"),
	"limit": (RowOperations, "limit_rows"),
	"sort": (RowOperations, "sort_rows"),
	"sample": (RowOperations, "sample"),
	**{
		name: (ConversionOperations, name)
		for name in ("date", "datetime", "float", "int", "str", "make_date", "make_time", "make_date_time")
	},
	**{
		name: (NumericOperations, name)
		for name in ("absolute", "clean_float", "ceiling", "floor", "max", "min", "power", "arithmetic")
	},
	"round": (NumericOperations, "round_column"),
	**{
		name: (TextOperations, name)
		for name in (
			"lowercase", "uppercase", "proper", "propper", "trim", "ltrim", "rtrim",
			"substring", "replace", "split", "concat_column", "concat_text", "contains",
			"starts_with", "ends_with", "transform_left", "transform_right", "length",
		)
	},
	**{
		name: (StructuralOperations, name)
		for name in (
			"join", "union", "add_column", "drop_column", "rename_column",
			"change_data_type", "aggregate", "pivot",
		)
	},
}
# Date and logical operations are registered in loops to avoid repeating the tuple for each name.
for _name in (
	"date_parser", "date_parse", "date_trunc", "day", "month", "year", "week", "quarter",
	"iso_quarter", "iso_week", "iso_week_day", "iso_year", "now", "today", "date_add",
	"date_sub", "date_diff", "date_name", "extract_date_part",
):
	_IMPLEMENTATIONS[_name] = (DateTimeOperations, _name)
for _name in ("logical", "coalesce", "conditional_map"):
	_IMPLEMENTATIONS[_name] = (LogicalOperations, _name)
# Class name -> class, used to resolve calls like `TextOperations().method` found inside method bodies.
_OWNERS = {
	owner.__name__: owner
	for owner in (
		ConversionOperations, DateTimeOperations, IOOperations, LogicalOperations,
		NumericOperations, RowOperations, StructuralOperations, TextOperations,
	)
}


def _function_name(owner: type, method: str) -> str:
	# Unique module-level name for a lowered method, e.g. _TextOperations_trim.
	return f"_{owner.__name__}_{method}"


class _MethodToFunction(ast.NodeTransformer):
	"""Rewrite a method's AST so it can live as a plain function: `self.x` becomes a module-level name."""

	def __init__(self, owner: type) -> None:
		self.owner = owner
		# Methods this one calls; they must be emitted too.
		self.dependencies: set[tuple[type, str]] = set()

	def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
		# Case 1: `self.<attr>`. Methods become calls to the lowered function and are recorded as dependencies;
		# class constants are inlined as literals (compiled regexes are rebuilt with re.compile(pattern, flags)).
		if isinstance(node.value, ast.Name) and node.value.id == "self":
			value = getattr(self.owner, node.attr)
			if not callable(value):
				if hasattr(value, "pattern"):
					return ast.parse(f"re.compile({value.pattern!r}, {int(value.flags)})", mode="eval").body
				return ast.parse(repr(value), mode="eval").body
			self.dependencies.add((self.owner, node.attr))
			return ast.copy_location(ast.Name(id=_function_name(self.owner, node.attr), ctx=ast.Load()), node)
		# Case 2: `OtherOperations().method` (no-arg constructor) is treated like a method of that other owner.
		if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
			owner = _OWNERS.get(node.value.func.id)
			if owner is not None and not node.value.args and not node.value.keywords:
				self.dependencies.add((owner, node.attr))
				return ast.copy_location(ast.Name(id=_function_name(owner, node.attr), ctx=ast.Load()), node)
		return self.generic_visit(node)


def _helper_sources(methods: set[tuple[type, str]]) -> list[str]:
	"""Lower trusted pandas operation methods to functions and include their dependencies."""
	# Worklist algorithm: lowering a method may discover more methods, which are added to `pending` until none remain.
	# min(...) picks the smallest (class, method) so the processing order is deterministic.
	pending = set(methods)
	sources: dict[str, str] = {}
	while pending:
		owner, method = min(pending, key=lambda item: (item[0].__name__, item[1]))
		pending.remove((owner, method))
		name = _function_name(owner, method)
		if name in sources:
			continue
		# Read the method's source, dedent it (it was indented inside a class) and parse it into an AST.
		tree = ast.parse(textwrap.dedent(inspect.getsource(getattr(owner, method))))
		function = tree.body[0]
		if not isinstance(function, ast.FunctionDef) or function.args.args[0].arg != "self":
			raise ValueError(f"Cannot emit pandas operation {owner.__name__}.{method}")
		function.name = name
		function.args.args.pop(0)  # drop `self`: the result is a free function
		transformer = _MethodToFunction(owner)
		transformer.visit(function)
		ast.fix_missing_locations(tree)
		sources[name] = ast.unparse(tree)  # back to source text
		pending.update(transformer.dependencies)
	return [sources[name] for name in sorted(sources)]


def _source(function: Callable[..., Any]) -> str:
	# Source text of an existing function, dedented so it can be pasted at module level.
	return textwrap.dedent(inspect.getsource(function)).strip()


class PandasEmitter:
	"""Generate a standalone Python module with run() and a command-line entrypoint."""

	# The attributes below are the hooks that PolarsEmitter overrides.
	engine = "python"
	framework = "pandas"
	implementations = _IMPLEMENTATIONS
	backend_imports = (
		"import pandas as pd\nimport numpy as np\n"
		"from pandas.api.types import is_bool_dtype\n"
		"from datetime import time\nimport operator\nimport re"
	)
	frame_type = "pd.DataFrame"
	reader = (IOOperations, "read_csv")
	stats: Callable[..., Any] | None = None

	def emit(self, plan: ExecutionPlan) -> str:
		if plan.framework != self.framework:
			raise ValueError(f"Emitter {self.framework} cannot emit plan for {plan.framework}")
		# Collect the (class, method) pairs the plan needs; fx steps are rendered inline instead.
		methods = {self.implementations[step.operation] for step in plan.steps if step.operation != "fx"}
		if plan.datasource_port_ids:
			methods.add(self.reader)
		# The script is assembled from sections: docstring, imports, runtime helpers, lowered operations, run(), launcher.
		sections = [
			f'"""Generated {self.framework} pipeline. Do not edit; regenerate from its DAG."""',
			"from __future__ import annotations\n\n"
			"import argparse\nimport json\nfrom collections.abc import Callable, Mapping, Sequence\n"
			"from pathlib import Path\nfrom typing import Any\n\n" + self.backend_imports,
			*(_source(function) for function in (
				parameter_reference, validate_value, validate_constraints, validate_target_parameters,
				runtime.resolve_parameters, runtime.step_parameters,
				runtime.check_context, runtime.script_main,
			)),
			*([_source(runtime._as_series)] if self.framework == "pandas" else []),
			*([_source(self.stats)] if self.stats else []),
			*_helper_sources(methods),
		]
		# Lines of the generated run() function; `p_i` holds the validated parameters and `n_i` the output of step i.
		lines = [
			"def run(datasources: Mapping[str, Any] | None = None, "
			"parameters: Mapping[str, Any] | None = None, "
			"base_dir: str | Path | None = None) -> dict[str, Any]:",
			"    datasources = {} if datasources is None else datasources",
			"    parameters = {} if parameters is None else parameters",
			f"    check_context(datasources, parameters, {plan.datasource_port_ids!r}, {plan.runtime_parameters!r}, {self.frame_type})",
		]
		# Validate every parameter before any node can perform IO.
		for index, step in enumerate(plan.steps):
			lines.append(
				f"    p_{index} = step_parameters({step.parameters!r}, parameters, "
				f"{OPERATIONS[step.operation].parameters!r}, {step.operation!r}, {step.id!r}, base_dir, {self.framework!r})"
			)
		variables: dict[str, str] = {}  # node id -> name of the variable holding its result
		# Steps are already in topological order, so every input variable exists by the time it is used.
		for index, step in enumerate(plan.steps):
			# An input is the upstream node's variable, or the external dataframe passed in `datasources`.
			inputs = [
				variables[binding.node_id] if binding.node_id is not None
				else f"datasources[{binding.port_id!r}]"
				for binding in step.inputs
			]
			if step.operation == "union":
				# union takes a single list argument instead of positional frames.
				inputs = [f"[{', '.join(inputs)}]"]
			if step.operation == "fx":
				# fx: render the parsed expression tree as native code and assign it to a (new) column of a copy.
				if step.expression is None:
					raise ValueError("fx step requires a compiled expression")
				expression = render_expression(step.expression, self.framework, inputs[0])
				if self.framework == "pandas":
					lines.extend([
						f"    n_{index} = {inputs[0]}.copy()",
						f"    n_{index}[p_{index}['column_name']] = {expression}",
					])
				elif self.framework == "polars":
					lines.append(f"    n_{index} = {inputs[0]}.with_columns(({expression}).alias(p_{index}['column_name']))")
				else:
					lines.append(f"    n_{index} = {inputs[0]}.withColumn(p_{index}['column_name'], {expression})")
				variables[step.id] = f"n_{index}"
				continue
			# Regular step: call the lowered function with the inputs plus the step parameters as keyword arguments.
			function = _function_name(*self.implementations[step.operation])
			arguments = ", ".join([*inputs, f"**p_{index}"])
			variables[step.id] = f"n_{index}"
			lines.append(f"    n_{index} = {function}({arguments})")
		# run() returns every node's result keyed by node id.
		lines.append("    return {" + ", ".join(f"{key!r}: {value}" for key, value in variables.items()) + "}")
		sections.append("\n".join(lines))
		# The launcher gets the datasource reader only when the pipeline has external input ports.
		reader = _function_name(*self.reader) if plan.datasource_port_ids else "None"
		stats = self.stats.__name__ if self.stats else "None"
		sections.append(f'if __name__ == "__main__":\n    script_main(run, {reader}, {stats})')
		source = "\n\n\n".join(sections) + "\n"
		# Compile the result to catch syntax errors at build time instead of at worker time.
		compile(source, f"<generated-{self.framework}-pipeline>", "exec")
		return source
