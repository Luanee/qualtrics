"""Ordered page registry and accessible report navigation."""

from dataclasses import dataclass

from ..templating import render_template


@dataclass(frozen=True)
class ReportPage:
    view_id: str
    label: str
    icon_path: str


REPORT_PAGES = (
    ReportPage("overview", "Summary", "M3 3h6v6H3z M15 3h6v6h-6z M3 15h6v6H3z M15 15h6v6h-6z"),
    ReportPage("survey-flow", "Flow", "M9 2h6v5H9z M12 7v5 M5 12h14 M5 12v5 M19 12v5 M2 17h6v5H2z M16 17h6v5h-6z"),
    ReportPage("question-analytics", "Questions", "M4 20V10 M12 20V4 M20 20v-7"),
    ReportPage("written-answers", "Written answers", "M4 3h16v18H4z M8 8h8 M8 12h8 M8 16h5"),
    ReportPage("by-responses", "Responses", "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M4 21v-3a8 8 0 0 1 16 0v3"),
    ReportPage("codebook", "Codebook", "M12 5v16 M12 5C8 2 4 2 2 3v16c4-1 7 0 10 2 3-2 6-3 10-2V3c-2-1-6-1-10 2"),
)


def render_navigation() -> str:
    return render_template("components/navigation.html.jinja", pages=REPORT_PAGES)
