from qualtrics.models.entities import EntitySet
from qualtrics.reporting.report import render_report


def test_views_written_answer_types_and_escaped_deep_links(tmp_path):
    entities = EntitySet(
        surveys=[{"survey_id": "s", "survey_name": "Survey"}],
        questions=[
            {"survey_id": "s", "question_id": "q", "question_text": "<Question>", "question_type": "TE"},
            {"survey_id": "s", "question_id": "n", "question_text": "Score", "question_type": "Slider"},
        ],
        question_fields=[
            {"survey_id": "s", "question_id": "q", "field_id": "f"},
            {"survey_id": "s", "question_id": "n", "field_id": "g"},
        ],
        responses=[{"survey_id": "s", "response_id": "r"}],
        response_answers=[
            {
                "survey_id": "s",
                "question_id": "q",
                "field_id": "f",
                "response_id": "r",
                "answer_text": "<script>001</script>",
            },
            {"survey_id": "s", "question_id": "n", "field_id": "g", "response_id": "r", "answer_text": "42"},
        ],
    )
    target = tmp_path / "report.html"
    render_report(entities, target)
    document = target.read_text()
    for view in ("overview", "question-analytics", "written-answers", "by-responses", "codebook", "survey-flow"):
        assert f"data-view='{view}' href='#{view}'" in document
    assert "id='question-detail-1'" in document
    assert "data-label='&lt;Question&gt;'" in document
    assert "id='response-1'" in document
    assert "id='written-1'" in document
    assert "id='written-2'" not in document
    assert "data-response-target='response-1'" in document
    assert "class='written-value'>&lt;script&gt;001&lt;/script&gt;" in document
    assert "class='finding' data-survey='s'" in document
    assert "href='#question-detail-1'" in document
    assert "<script>001</script>" not in document


def test_empty_report_retains_views_and_empty_explanations(tmp_path):
    target = tmp_path / "empty.html"
    render_report(EntitySet(), target)
    document = target.read_text()
    assert "id='findings-empty'>No observed highlights" in document
    assert "id='written-empty'>No written answers" in document
    assert "id='response-list'></div>" in document
    assert document.index("id='overview'") < document.index("id='stat-responses'")


def test_written_and_response_fields_share_escaped_identity(tmp_path):
    from html.parser import HTMLParser

    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.written = []
            self.fields = []
            self.options = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            classes = attrs.get("class", "").split()
            if "written-answer" in classes:
                self.written.append(attrs)
            if "field-answer" in classes:
                self.fields.append(attrs)
            if tag == "option" and attrs.get("data-survey"):
                self.options.append(attrs)

    identities = ["first'&", "last"]
    entities = EntitySet(
        surveys=[{"survey_id": "s", "survey_name": "Survey"}],
        questions=[{"survey_id": "s", "question_id": "q", "question_text": "Name", "question_type": "TE"}],
        question_fields=[
            {"survey_id": "s", "question_id": "q", "field_id": field, "field_text": field} for field in identities
        ],
        responses=[{"survey_id": "s", "response_id": "r"}],
        response_answers=[
            {"survey_id": "s", "question_id": "q", "field_id": field, "response_id": "r", "answer_text": "Lee"}
            for field in identities
        ],
    )
    target = tmp_path / "report.html"
    render_report(entities, target)
    parsed = Elements()
    parsed.feed(target.read_text())
    assert [item.get("data-field-id") for item in parsed.written] == identities
    assert [item.get("data-field-id") for item in parsed.fields] == identities
    assert all(item["data-response-target"] == "response-1" for item in parsed.written)
    assert parsed.options[0]["data-label"] == "Name"


def test_compact_summary_keeps_search_in_header_and_diagnostics_collapsed(tmp_path):
    from html.parser import HTMLParser

    class Layout(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.elements = {}
            self.primary_metrics = 0

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if attrs.get("id"):
                self.elements[attrs["id"]] = (attrs, list(self.stack))
            if "stat" in attrs.get("class", "").split():
                self.primary_metrics += 1
            if tag not in {"meta", "input", "br", "hr", "link"}:
                self.stack.append((tag, attrs.get("id")))

        def handle_endtag(self, tag):
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    del self.stack[index:]
                    break

    output = tmp_path / "report.html"
    render_report(EntitySet(), output)
    layout = Layout()
    layout.feed(output.read_text())
    assert any(tag == "header" for tag, _ in layout.elements["report-search"][1])
    assert "open" not in layout.elements["summary-details"][0]
    assert ("details", "summary-details") in layout.elements["overview-unused-fields"][1]
    assert ("details", "summary-details") in layout.elements["stat-questions"][1]
    assert layout.primary_metrics == 3


def test_summary_distinguishes_not_marked_finished_without_inventing_partial_status(tmp_path):
    entities = EntitySet(
        surveys=[{"survey_id": "s", "survey_name": "Survey"}],
        responses=[
            {"survey_id": "s", "response_id": "one", "is_finished": "True"},
            {"survey_id": "s", "response_id": "two", "is_finished": "False"},
            {"survey_id": "s", "response_id": "three", "is_finished": None},
        ],
    )
    output = tmp_path / "report.html"
    render_report(entities, output)
    document = output.read_text()
    assert "id='overview-other'>2</strong>" in document
    assert "Not marked finished" in document
    assert "href='#overview' aria-current='page'" in document
