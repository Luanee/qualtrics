"""Markup for the offline Summary dashboard, backed by aggregate data only."""

from __future__ import annotations

import json

from ..analytics.report import ReportAnalytics
from ..models import EntitySet
from .dashboard import build_dashboard


def render_dashboard(entities: EntitySet, analysis: ReportAnalytics) -> str:
    payload = json.dumps(build_dashboard(entities, analysis), ensure_ascii=True, separators=(",", ":"))
    # JSON is a script's raw-text content: HTML escaping would corrupt labels,
    # while an unescaped '<' would allow a label to terminate the script element.
    payload = payload.replace("<", "\\u003c")
    spotlights = "".join(
        f"<article class='dashboard-spotlight'><label for='dashboard-question-{index}'>"
        f"Question {index}</label><select id='dashboard-question-{index}'></select>"
        f"<div id='dashboard-spotlight-{index}'></div></article>"
        for index in (1, 2)
    )
    return (
        "<section id='summary-dashboard' class='dashboard-grid' aria-label='Summary charts'>"
        "<section class='dashboard-panel dashboard-timeline' aria-labelledby='dashboard-timeline-title'>"
        "<div class='dashboard-panel-head'><h3 id='dashboard-timeline-title'>Recorded responses over time</h3>"
        "<div class='dashboard-controls'><label for='dashboard-period'>Group by</label>"
        "<select id='dashboard-period'><option value='week'>Week</option><option value='month'>Month</option>"
        "</select></div></div><div id='dashboard-timeline'></div><p id='dashboard-date-note' class='meta'></p>"
        "<details class='dashboard-data-table'><summary>View timeline counts</summary>"
        "<div class='table-scroll'><table id='dashboard-timeline-table'></table></div></details></section>"
        "<section class='dashboard-panel dashboard-surveys' aria-labelledby='dashboard-surveys-title'>"
        "<h3 id='dashboard-surveys-title'>Responses by survey</h3><p class='meta'>"
        "Response volume and finished share of recorded responses.</p>"
        "<div class='dashboard-legend'><span><i class='dashboard-bar-finished' aria-hidden='true'></i>Finished</span>"
        "<span><i class='dashboard-bar-other' aria-hidden='true'></i>Not marked finished</span></div>"
        "<div id='dashboard-surveys'></div></section>"
        "<section class='dashboard-panel dashboard-spotlights' aria-labelledby='dashboard-spotlights-title'>"
        "<h3 id='dashboard-spotlights-title'>Question spotlights</h3>"
        "<p class='meta'>Choose questions to see their answer patterns. "
        "Each chart keeps its own survey and answer counts.</p>"
        f"<div class='dashboard-spotlight-grid'>{spotlights}</div></section>"
        "<section class='dashboard-panel dashboard-coverage' aria-labelledby='dashboard-coverage-title'>"
        "<h3 id='dashboard-coverage-title'>Questions with little recorded data</h3>"
        "<p class='meta'>Answered responses divided by all response records in that survey. "
        "Missing answers do not establish whether a question was shown.</p>"
        "<div id='dashboard-coverage'></div></section>"
        "<noscript>Enable JavaScript to use the dashboard charts. "
        "Detailed report tables are available below.</noscript>"
        f"</section><script id='dashboard-data' type='application/json'>{payload}</script>"
    )
