"""Response properties remain visible without becoming survey answers."""

import json
from html.parser import HTMLParser

from qualtrics._common.models import EntitySet
from qualtrics.ui.codebook import build_codebook, render_codebook
from qualtrics.ui.context import ReportContext
from qualtrics.ui.pages.responses import render_responses


def _entities() -> EntitySet:
    descriptors = [
        ("Region", "region", "Area <north>", "embedded", "Declared in survey flow", "responses"),
        ("Email_permission", "permission", "Email permission", "embedded", "Declared in survey flow", "responses"),
        ("CampaignCode", "campaign", "Campaign code", "unclassified", "No definition evidence", "responses"),
        ("Count", "count", "Count", "embedded", "Declared in survey flow", "responses"),
        ("Missing", "missing", "Missing field", "embedded", "Declared in survey flow", "responses"),
        ("Rating", "Rating", "Rating", "question", "Question ImportId QID1", "response_answers"),
        ("Rating_NPS_GROUP", "Rating_NPS_GROUP", "NPS category", "derived", "Derived from QID1", "response_answers"),
        ("I3_Browser", "browser", "Browser", "metadata", "Question type Meta/Browser", "responses"),
    ]
    source_columns = [
        {
            "source_column": source,
            "source_column_index": index,
            "source_import_id": "QID1" if kind == "question" else "QID1_NPS_GROUP" if kind == "derived" else source,
            "label": label,
            "kind": kind,
            "reason": reason,
            "storage_table": table,
            "storage_column": storage,
        }
        for index, (source, storage, label, kind, reason, table) in enumerate(descriptors)
    ]
    return EntitySet(
        surveys=[
            {"survey_id": "s", "survey_name": "Fictional survey", "source_columns_json": json.dumps(source_columns)}
        ],
        questions=[
            {
                "survey_id": "s",
                "question_id": "q",
                "question_external_id": "QID1",
                "question_text": "Rating",
                "question_type": "MC",
            },
        ],
        question_fields=[
            {
                "survey_id": "s",
                "question_id": "q",
                "field_id": "f",
                "field_external_id": "Rating",
                "source_column_index": 5,
            },
            {
                "survey_id": "s",
                "question_id": "q",
                "field_id": "g",
                "field_external_id": "Rating_NPS_GROUP",
                "source_column_index": 6,
            },
        ],
        responses=[
            {
                "survey_id": "s",
                "response_id": "r",
                "response_external_id": "R1",
                "region": "<script>North</script>",
                "permission": False,
                "campaign": "001",
                "count": 0,
                "missing": None,
                "browser": "ExampleBrowser",
            }
        ],
        response_answers=[
            {"survey_id": "s", "response_id": "r", "question_id": "q", "field_id": "f", "answer_text": "9"}
        ],
    )


class _Markup(HTMLParser):
    def __init__(self, markup: str) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.text: list[str] = []
        self.feed(markup)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def test_response_properties_are_expandable_escaped_and_preserve_false_and_zero() -> None:
    rendered = render_responses(ReportContext.build(_entities()))
    parsed = _Markup(rendered)
    properties = [
        attrs for tag, attrs in parsed.tags if tag == "details" and attrs.get("class") == "response-properties"
    ]
    assert len(properties) == 1
    assert "open" not in properties[0]
    assert "Area &lt;north&gt;" in rendered
    assert "&lt;script&gt;North&lt;/script&gt;" in rendered
    assert not any(tag == "script" for tag, _ in parsed.tags)
    assert "False" in parsed.text and "0" in parsed.text and "001" in parsed.text
    assert "None" not in parsed.text
    assert parsed.text.count("ExampleBrowser") == 1
    card = next(attrs for _, attrs in parsed.tags if attrs.get("class") == "respondent")
    assert "Email permission" in parsed.text
    assert card["data-total-answers"] == "1"


def test_codebook_includes_property_evidence_and_storage_without_response_values() -> None:
    entities = _entities()
    rows = build_codebook(entities)
    assert len(rows) == 8
    by_column = {row["export_column"]: row for row in rows}
    assert by_column["Region"]["kind"] == "embedded"
    assert by_column["Region"]["reason"] == "Declared in survey flow"
    assert by_column["Region"]["storage_table"] == "responses"
    assert by_column["Region"]["storage_column"] == "region"
    assert by_column["Region"]["source_column_index"] == "0"
    assert by_column["CampaignCode"]["kind"] == "unclassified"
    assert by_column["Rating_NPS_GROUP"]["kind"] == "derived"
    assert by_column["Rating_NPS_GROUP"]["question_id"] == "QID1"
    assert by_column["Rating_NPS_GROUP"]["storage_table"] == "response_answers"
    assert by_column["I3_Browser"]["kind"] == "metadata"
    rendered = render_codebook(entities)
    assert "responses.region" in rendered
    assert "response_answers.answer_text" in rendered
    assert "Answer field: Rating_NPS_GROUP" in rendered
    assert "response_answers.Rating" not in rendered
    assert "Declared in survey flow" in rendered
    assert "Area &lt;north&gt;" in rendered
    assert "&lt;script&gt;North&lt;/script&gt;" not in rendered
    assert "ExampleBrowser" not in rendered


def test_legacy_response_browser_metadata_still_renders_without_source_dictionary() -> None:
    entities = _entities()
    del entities.surveys[0]["source_columns_json"]
    rendered = render_responses(ReportContext.build(entities))
    assert "<b>Browser</b> ExampleBrowser" in rendered
    assert len(build_codebook(entities)) == 2


def test_codebook_source_dictionary_supersedes_a_legacy_browser_question_field() -> None:
    entities = _entities()
    entities.questions.append({
        "survey_id": "s",
        "question_id": "browser-q",
        "question_external_id": "QID3",
        "question_type": "Meta",
    })
    entities.question_fields.append({
        "survey_id": "s",
        "question_id": "browser-q",
        "field_id": "browser-f",
        "field_external_id": "I3_Browser",
        "source_column_index": 7,
    })
    rows = build_codebook(entities)
    browser = [row for row in rows if row["export_column"] == "I3_Browser"]
    assert len(browser) == 1
    assert browser[0]["storage_table"] == "responses"
    assert browser[0]["storage_column"] == "browser"
