"""Compose the document using the packaged layout and rendered page boundaries."""

from __future__ import annotations

from ..assets import load_scripts, load_styles
from ..components.controls import render_survey_choices
from ..components.navigation import REPORT_PAGES
from ..context import ReportContext
from ..templating import render_template, trusted_html


def render_document(context: ReportContext, pages: tuple[str, ...]) -> str:
    return render_template(
        "layouts/report.html.jinja",
        survey_name=context.analysis.survey_name,
        survey_options=trusted_html(render_survey_choices(context)),
        navigation_pages=REPORT_PAGES,
        pages=tuple(trusted_html(page) for page in pages),
        styles=trusted_html(load_styles()),
        scripts=trusted_html(load_scripts()),
    )
