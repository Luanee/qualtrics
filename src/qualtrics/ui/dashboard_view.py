"""Prepare aggregate data for the offline Summary dashboard template."""

from __future__ import annotations

import json

from ..analytics.report import ReportAnalytics
from ..models import EntitySet
from .dashboard import build_dashboard
from .templating import render_template, trusted_html


def render_dashboard(entities: EntitySet, analysis: ReportAnalytics) -> str:
    payload = json.dumps(build_dashboard(entities, analysis), ensure_ascii=True, separators=(",", ":"))
    # Script raw text must retain JSON syntax while blocking closing HTML tags.
    payload = payload.replace("<", "\\u003c")
    return render_template("dashboard/page.html.jinja", payload=trusted_html(payload))
