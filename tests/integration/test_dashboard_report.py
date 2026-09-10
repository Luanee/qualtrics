import json
from html.parser import HTMLParser

from qualtrics._common.models import EntitySet
from qualtrics.ui import render_report


class ReportDocument(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.dashboard = None
        self.in_dashboard = False
        self.controls = {}
        self.options = {}
        self.current_select = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.ids.add(attrs.get("id"))
        if tag in {"input", "select"}:
            self.controls[attrs.get("id")] = attrs
        if tag == "select":
            self.current_select = attrs.get("id")
            self.options[self.current_select] = []
        if tag == "option" and self.current_select:
            self.options[self.current_select].append(attrs.get("value"))
        if tag == "script":
            self.in_dashboard = attrs.get("id") == "dashboard-data"

    def handle_data(self, data):
        if self.in_dashboard:
            self.dashboard = json.loads(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_dashboard = False
        if tag == "select":
            self.current_select = None


def test_generated_dashboard_embeds_safe_aggregates_with_working_question_targets(tmp_path):
    label = '</script><script id="injected">alert(1)</script>'
    entities = EntitySet(
        surveys=[{"survey_id": "s", "survey_name": label}],
        responses=[{"survey_id": "s", "response_id": "r", "is_finished": "true", "recorded_at": "2025-01-01"}],
        questions=[{"survey_id": "s", "question_id": "q", "question_text": label, "question_type": "Slider"}],
        question_fields=[{"survey_id": "s", "question_id": "q", "field_id": "f", "answer_value_type": "numeric"}],
        response_answers=[
            {"survey_id": "s", "question_id": "q", "field_id": "f", "response_id": "r", "answer_text": "8"}
        ],
    )
    output = tmp_path / "report.html"
    render_report(entities, output)
    parsed = ReportDocument()
    parsed.feed(output.read_text())
    assert parsed.dashboard is not None
    assert parsed.dashboard["surveys"][0]["label"] == label
    assert parsed.dashboard["spotlights"][0]["target"] in parsed.ids
    assert parsed.dashboard["coverage"][0]["target"] in parsed.ids
    assert "injected" not in parsed.ids
    for control in ("period", "cumulative", "question-1", "question-2", "timeline-table"):
        assert "dashboard-" + control in parsed.ids
    assert parsed.options["dashboard-period"] == ["week", "month", "year"]
    assert parsed.controls["dashboard-cumulative"]["type"] == "checkbox"
    assert "checked" not in parsed.controls["dashboard-cumulative"]


def test_empty_generated_report_has_an_empty_dashboard_dataset(tmp_path):
    output = tmp_path / "empty.html"
    render_report(EntitySet(), output)
    parsed = ReportDocument()
    parsed.feed(output.read_text())
    assert parsed.dashboard == {"surveys": [], "coverage": [], "spotlights": []}
