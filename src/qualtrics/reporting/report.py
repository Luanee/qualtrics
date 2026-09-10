"""Compatibility entry point for the optional report UI."""

from pathlib import Path

from ..models.entities import EntitySet


def render_report(entities: EntitySet, output: str | Path) -> None:
    """Render an offline report; requires the ``ui`` installation extra."""
    from ..ui.report import render_report as render_ui_report

    render_ui_report(entities, output)
