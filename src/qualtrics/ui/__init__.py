"""Optional report UI; importing this namespace does not load its dependencies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .report import render_report as render_report

__all__ = ["render_report"]


def __getattr__(name: str) -> Any:
    if name == "render_report":
        from .report import render_report

        return render_report
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
