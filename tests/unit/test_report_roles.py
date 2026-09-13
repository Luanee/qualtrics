"""Report role inference for legacy entities without optional role metadata."""

from copy import deepcopy

import pytest

from qualtrics._common.analytics import analyze_entities
from qualtrics._common.models.entities import EntitySet


def _entities(question: dict, field: dict | None = None) -> EntitySet:
    return EntitySet(
        surveys=[{"survey_id": "s", "survey_name": "Fictional survey"}],
        questions=[{"survey_id": "s", "question_id": "q", "question_text": "Test question", **question}],
        question_fields=[{"survey_id": "s", "question_id": "q", "field_id": "f", **(field or {})}],
        responses=[{"survey_id": "s", "response_id": "r"}],
    )


@pytest.mark.parametrize(
    ("question", "field", "role"),
    [
        ({"question_type": "Timing", "selector": "PageTimer"}, {}, "timing"),
        ({"question_type": "Meta", "selector": "Browser"}, {}, "metadata"),
        ({"question_type": "TE", "selector": "Browser"}, {}, "metadata"),
        ({"selector": "Timing"}, {}, "timing"),
        ({}, {"import_external_id": "QID2_PAGE_SUBMIT"}, "timing"),
        ({}, {"source_import_id": "QID2_FIRST_CLICK"}, "timing"),
        ({}, {"import_external_id": "QID3_BROWSER"}, "metadata"),
        ({}, {"source_import_id": "QID3_USERAGENT"}, "metadata"),
        ({"question_type": "MC", "selector": "SAVR"}, {}, "response"),
        ({}, {}, "response"),
    ],
)
def test_missing_role_infers_technical_evidence_without_inventing_respondent_diagnostics(question, field, role):
    entities = _entities(question, field)
    before = deepcopy(entities)

    result = analyze_entities(entities)

    assert result.question_roles[("s", "q")] == role
    assert len(result.response_questions) == (1 if role == "response" else 0)
    assert len(result.unanswered_questions) == (1 if role == "response" else 0)
    assert len(result.unused_fields) == (1 if role == "response" else 0)
    assert result.survey_question_counts["s"] == (1 if role == "response" else 0)
    assert entities == before


@pytest.mark.parametrize(
    ("explicit", "question_type", "role"),
    [("response", "Timing", "response"), ("metadata", "TE", "metadata"), ("timing", "MC", "timing")],
)
def test_persisted_role_takes_precedence_over_question_type(explicit, question_type, role):
    entities = _entities({"question_type": question_type, "question_role": explicit})
    assert analyze_entities(entities).question_roles[("s", "q")] == role


def test_import_evidence_is_scoped_to_both_survey_and_question_and_canonical_id_wins():
    entities = _entities({}, {"import_external_id": "Name", "source_import_id": "QID2_PAGE_SUBMIT"})
    entities.questions += [
        {"survey_id": "s", "question_id": "technical"},
        {"survey_id": "another", "question_id": "q"},
    ]
    entities.question_fields += [
        {
            "survey_id": "s",
            "question_id": "technical",
            "field_id": "technical-f",
            "import_external_id": "QID2_PAGE_SUBMIT",
        },
        {"survey_id": "another", "question_id": "q", "field_id": "another-f", "import_external_id": "QID3_BROWSER"},
    ]
    result = analyze_entities(entities)
    assert result.question_roles == {("s", "q"): "response", ("s", "technical"): "timing", ("another", "q"): "metadata"}
    assert set(result.response_questions) == {("s", "q")}


def test_mixed_import_ids_do_not_infer_metadata_from_one_browser_field():
    entities = _entities({}, {"import_external_id": "QID3_BROWSER"})
    entities.question_fields.append({
        "survey_id": "s",
        "question_id": "q",
        "field_id": "other",
        "import_external_id": "QID3_OTHER",
    })
    assert analyze_entities(entities).question_roles[("s", "q")] == "response"
