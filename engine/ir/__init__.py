"""Backend-independent compilation; schema validation can be imported on its own."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from engine.ir.plan import ExecutionPlan, build_plan

__all__ = ["ExecutionPlan", "build_plan"]


def __getattr__(name: str) -> object:
	if name in __all__:
		from engine.ir import plan

		return getattr(plan, name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
