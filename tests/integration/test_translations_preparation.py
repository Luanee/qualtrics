"""Prepared labels and comments keep base analytic identities."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import pytest

import qualtrics
from qualtrics._common.models.entity_set import validate_entity_set


def _survey(tmp_path: Path):
    response_path = tmp_path / "responses.csv"
    with response_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1", "QID2"],
            ["Response ID", "Language", "Choice", "Comment"],
            ["{}", "{}", json.dumps({"ImportId": "QID1"}), json.dumps({"ImportId": "QID2"})],
            ["R_NO", "NO", "1", "Norsk kommentar"],
            ["R_EN", "EN", "2", "English comment"],
            ["R_UNKNOWN", "", "Maybe", "Unknown comment"],
        ])
    definition = tmp_path / "definition.qsf"
    definition.write_text(
        json.dumps({
            "SurveyID": "SV_NORWAY",
            "SurveyOptions": {"SurveyLanguage": "NO", "AvailableLanguages": {"NO": [], "DE": []}},
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "Velg ett alternativ",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {"1": {"Display": "Ja"}, "2": {"Display": "Nei"}},
                    "Language": {"DE": {"QuestionText": "Wählen Sie", "Choices": {"1": {"Display": "Ja"}}}},
                },
                "QID2": {"QuestionID": "QID2", "QuestionText": "Kommentar", "QuestionType": "TE"},
                "QID3": {"QuestionID": "QID3", "QuestionText": "Nur Definition", "QuestionType": "TE"},
            },
        }),
        encoding="utf-8",
    )
    return qualtrics.parse_survey(response_path, definition)


def _prepare(entities, **kwargs):
    prepare = getattr(qualtrics, "prepare_translations", None)
    assert prepare is not None, "public prepare_translations is missing"
    return prepare(entities, **kwargs)


def test_english_target_outside_qsf_keeps_base_catalogs_and_fact_count(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    original = copy.deepcopy(source)
    requests = []

    def translate(request):
        requests.append(request)
        return f"EN:{request.kind}:{request.text}"

    prepared = _prepare(source, language="EN", translate=translate)

    assert source == original
    assert len(prepared.response_answers) == len(source.response_answers)
    assert len(prepared.comments) == len(source.comments) == 3
    assert prepared.survey_manifests["SV_NORWAY"]["languages"]["prepared_languages"] == ["EN"]
    base_questions = {row["question_external_id"]: row for row in source.questions if not row.get("is_localized")}
    english = [row for row in prepared.questions if row.get("language_code") == "EN"]
    assert len(english) == len(base_questions)
    assert all(row["is_localized"] for row in english)
    assert all(
        row["question_catalog_id"] == base_questions[row["question_external_id"]]["question_catalog_id"]
        for row in english
    )
    assert all(row["question_id"] != base_questions[row["question_external_id"]]["question_id"] for row in english)
    assert any(request.kind == "answer_option" and request.target_language == "EN" for request in requests)


def test_comment_callback_skips_known_target_and_passes_unknown_source(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    requests = []

    def translate(request):
        requests.append(request)
        return f"English: {request.text}"

    prepared = _prepare(source, language="EN", comment=translate)
    comments = {row["answer_text"]: row for row in prepared.comments}

    assert comments["English comment"]["translated_text__EN"] is None
    assert comments["Norsk kommentar"]["translated_text__EN"] == "English: Norsk kommentar"
    assert comments["Unknown comment"]["translated_text__EN"] == "English: Unknown comment"
    assert {(request.text, request.source_language) for request in requests} == {
        ("Norsk kommentar", "NO"),
        ("Unknown comment", None),
    }
    assert all(request.kind == "comment" for request in requests)


def test_qsf_labels_win_and_specific_option_callback_fills_only_missing_choice(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    requests = []

    def option(request):
        requests.append(request)
        return "Nein"

    prepared = _prepare(source, language="DE", answer_option=option)
    question = next(
        row for row in prepared.questions if row.get("language_code") == "DE" and row["question_external_id"] == "QID1"
    )
    options = {
        row["answer_external_id"]: row
        for row in prepared.answer_options
        if row.get("language_code") == "DE" and row["question_external_id"] == "QID1"
    }

    assert question["question_text"] == "Wählen Sie"
    assert options["1"]["answer_text"] == "Ja"
    assert options["2"]["answer_text"] == "Nein"
    assert [request.text for request in requests] == ["Nei"]


def test_failed_callback_leaves_input_unchanged(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    original = copy.deepcopy(source)

    def fail(_request):
        raise RuntimeError("translation service offline")

    with pytest.raises(RuntimeError, match="translation service offline"):
        _prepare(source, language="EN", translate=fail)
    assert source == original


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_prepared_target_validates_and_roundtrips(tmp_path: Path, format: str) -> None:
    source = _survey(tmp_path)
    prepared = _prepare(source, language="EN", translate=lambda request: f"English {request.text}")
    validate_entity_set(prepared, strict=True)

    folder = tmp_path / format
    qualtrics.write_entities(prepared, folder, format=format)
    loaded = qualtrics.load_entities(folder)

    assert loaded.comments == prepared.comments
    assert len(loaded.response_answers) == len(source.response_answers)
    assert loaded.survey_manifests["SV_NORWAY"]["languages"]["prepared_languages"] == ["EN"]
