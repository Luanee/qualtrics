"""Ordered, locally bundled report assets; dependencies precede controllers."""

from importlib.resources import files

STYLE_ASSETS = (
    "report.css",
    "layouts/shell.css",
    "components/controls.css",
    "components/content.css",
    "pages/questions.css",
    "pages/written.css",
    "pages/search.css",
    "components/pagination.css",
    "pages/responses.css",
    "pages/quality.css",
    "components/charts.css",
    "components/filters.css",
    "components/tables.css",
    "layouts/responsive.css",
    "layouts/print.css",
    "codebook.css",
    "question-charts.css",
    "dashboard.css",
    "flow.css",
)
SCRIPT_ASSETS = (
    "report-search.js",
    "components/dom.js",
    "components/pagination.js",
    "components/menus.js",
    "codebook.js",
    "dashboard.js",
    "flow-engine.js",
    "flow-graph.js",
    "flow-canvas.js",
    "flow.js",
    "pages/responses.js",
    "pages/written.js",
    "pages/questions.js",
    "pages/summary.js",
    "pages/search.js",
    "layouts/navigation.js",
    "report.js",
)


def load_asset(name: str) -> str:
    """Load a report asset bundled inside the installed distribution."""
    return files("qualtrics.reporting").joinpath("static", name).read_text(encoding="utf-8")


def load_styles() -> str:
    return "\n".join(load_asset(name) for name in STYLE_ASSETS)


def load_scripts() -> str:
    return "\n".join(load_asset(name) for name in SCRIPT_ASSETS)
