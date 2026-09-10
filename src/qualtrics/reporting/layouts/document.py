# ruff: noqa: E501 -- HTML markup
from __future__ import annotations

import html

from ..assets import load_scripts, load_styles
from ..components.controls import render_survey_choices
from ..components.navigation import render_navigation
from ..components.primitives import pagination
from ..context import ReportContext


def render_document(context: ReportContext, pages: tuple[str, ...]) -> str:
    survey_name = context.analysis.survey_name
    survey_options = render_survey_choices(context)
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{html.escape(survey_name)} · Response report</title>",
        f"<style>{load_styles()}</style></head><body><a class='skip-link' href='#report-content'>Skip to report content</a>",
        f"<header class='report-header'><div class='header-inner'><div class='report-title'><small>Response report</small><h1>{html.escape(survey_name)}</h1></div>"
        "<div class='global-search'><label for='report-search'>Search this report</label>"
        "<input id='report-search' type='search' placeholder='Questions, answers, flow, field names…'>"
        "<button id='search-clear' type='button' hidden>Clear</button>"
        "<label for='theme-choice'>Theme</label><select id='theme-choice'>"
        "<option value='system'>System</option><option value='light'>Light</option><option value='dark'>Dark</option>"
        "</select></div></div></header>",
        "<div class='shell report-layout'><aside><div class='survey-switcher'>"
        "<div class='survey-filter filter-wrap'><button id='survey-toggle' type='button' aria-expanded='false'>"
        "Surveys · <span id='survey-selected-count'>All</span></button><div id='survey-menu' "
        "class='survey-menu' hidden><div class='selector-actions'>"
        "<button id='survey-select-all' type='button'>Select all</button>"
        f"<button id='survey-clear' type='button'>Clear</button></div>{survey_options}</div></div></div>"
        f"{render_navigation()}</aside><main id='report-content' class='report-main' tabindex='-1'>",
        "<section id='search-results' hidden aria-label='Search results'><h2>Search results</h2>"
        "<p class='meta'>Search locates content. Statistics use the selected surveys.</p>"
        "<p id='search-result-count' role='status'></p><div id='search-result-list'></div>"
        f"{pagination('search-pagination')}</section>",
        *pages,
        "</main></div><script>",
        load_scripts(),
        "</script></body></html>",
    ]
    return "".join(parts)
