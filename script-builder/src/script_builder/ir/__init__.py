"""Backend-independent compilation; schema validation can be imported on its own."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from script_builder.ir.plan import ExecutionPlan, build_plan

__all__ = ["ExecutionPlan", "build_plan"]


# Lazy export (PEP 562): plan is imported on first access, so importing ir.validate alone stays lightweight
# and avoids circular imports.
def __getattr__(name: str) -> object:
	if name in __all__:
		from script_builder.ir import plan

		return getattr(plan, name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
