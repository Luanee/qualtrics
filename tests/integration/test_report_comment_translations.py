"""Prepared comment text is a display overlay, never a replacement for answers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from qualtrics import build_semantic_model, parse_survey, prepare_comment_translations, render_report


def _entities(tmp_path: Path):
    source = tmp_path / "answers.csv"
    definition = tmp_path / "definition.qsf"
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1"],
            ["Response", "Language", "Comment"],
            [json.dumps({"ImportId": value}) for value in ("responseId", "userLanguage", "QID1")],
            ["R1", "DE", "<source> & text"],
        ])
    definition.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_REPORT_TRANSLATION", "SurveyName": "Report", "SurveyLanguage": "DE"},
            "SurveyElements": [
                {
                    "Element": "SQ",
                    "PrimaryAttribute": "QID1",
                    "Payload": {
                        "QuestionID": "QID1",
                        "QuestionText": "Comment",
                        "QuestionType": "TE",
                        "Selector": "ML",
                    },
                }
            ],
        }),
        encoding="utf-8",
    )
    return parse_survey(source, definition)


def _translation_payload(document: str) -> dict[str, dict[str, dict[str, object]]]:
    return json.loads(
        document.split("<script id='written-translation-data' type='application/json'>", 1)[1].split("</script>", 1)[0]
    )


def test_report_embeds_current_prepared_text_with_original_preserved(tmp_path: Path) -> None:
    entities = _entities(tmp_path)
    prepared = prepare_comment_translations(entities, ["EN"], lambda *_args: "<translated> & text")
    report = tmp_path / "report.html"
    render_report(prepared, report)
    document = report.read_text(encoding="utf-8")
    answer_id = entities.response_answers[0]["response_answer_id"]
    assert "class='written-value'>&lt;source&gt; &amp; text</p>" in document
    assert "class='written-original' hidden" in document
    assert "Translation unavailable" in document
    assert "Display language" in document
    assert "<option value='EN'>EN</option>" in document
    assert _translation_payload(document)[answer_id]["EN"] == {"text": "<translated> & text", "current": True}
    assert "<translated>" not in document
    assert entities.response_answers[0]["answer_text"] == "<source> & text"


def test_report_marks_stale_prepared_text_without_exposing_it_as_display_text(tmp_path: Path) -> None:
    entities = prepare_comment_translations(_entities(tmp_path), ["EN"], lambda *_args: "Old translation")
    entities.response_answers[0]["answer_text"] = "New original"
    report = tmp_path / "stale.html"
    render_report(entities, report)
    document = report.read_text(encoding="utf-8")
    answer_id = entities.response_answers[0]["response_answer_id"]
    assert "class='written-value'>New original</p>" in document
    assert _translation_payload(document)[answer_id]["EN"] == {"text": None, "current": False}
    assert "Old translation" not in document


def test_report_without_prepared_translations_stays_offline_and_shows_original(tmp_path: Path) -> None:
    entities = _entities(tmp_path)
    report = tmp_path / "original.html"
    render_report(entities, report)
    document = report.read_text(encoding="utf-8")
    assert "class='written-value'>&lt;source&gt; &amp; text</p>" in document
    assert _translation_payload(document) == {}


def test_semantic_display_languages_include_prepared_target_without_qsf_labels(tmp_path: Path) -> None:
    prepared = prepare_comment_translations(_entities(tmp_path), ["EN"], lambda *_args: "Translation")
    model = build_semantic_model(prepared)
    target = next(row for row in model.dim_display_languages if row["language_code"] == "EN")
    assert target == {
        "language_code": "EN",
        "is_available": True,
        "available_survey_count": 1,
        "defined_survey_count": 0,
    }
    assert any(row["language_code"] == "EN" for row in model.dim_question_labels)
