"""The offline report keeps respondent and definition language independent."""

from __future__ import annotations

import csv
import json

from qualtrics import parse_survey
from qualtrics._common.models.entity_set import merge_entity_sets
from qualtrics.ui.report import render_report
from qualtrics.ui.report_languages import build_report_languages


def _survey(tmp_path, survey_id="SV_LANG_REPORT", *, include_german=True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    responses = tmp_path / "responses.csv"
    with responses.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1", "QID2"],
            ["Response ID", "Language", "Choice", "Comment"],
            ["{}", "{}", json.dumps({"ImportId": "QID1"}), json.dumps({"ImportId": "QID2"})],
            ["R_EN", "EN", "Yes", "Original English"],
            ["R_DE", "DE", "Ja", "Original German"],
            ["R_UNKNOWN", "", "No", "Original unknown"],
        ])
    definition = tmp_path / "definition.qsf"
    definition.write_text(
        json.dumps({
            "SurveyID": survey_id,
            "SurveyOptions": {
                "SurveyLanguage": "EN",
                "AvailableLanguages": {"EN": [], "DE": []} if include_german else {"EN": []},
            },
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "Choice",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                    "Language": {"DE": {"QuestionText": "Auswahl", "Choices": {"1": {"Display": "Ja"}}}}
                    if include_german
                    else {},
                },
                "QID2": {
                    "QuestionID": "QID2",
                    "QuestionText": "Comment",
                    "QuestionType": "TE",
                    "Language": {"DE": {"QuestionText": "Kommentar"}} if include_german else {},
                },
                "QID3": {"QuestionID": "QID3", "QuestionText": "Definition only", "QuestionType": "TE"},
            },
        }),
        encoding="utf-8",
    )
    return parse_survey(responses, definition)


def test_report_language_snapshots_filter_all_metrics_without_changing_facts(tmp_path):
    entities = _survey(tmp_path)
    data = build_report_languages(entities)
    assert data["respondent_languages"] == ["EN", "DE", "__missing__"]
    assert data["snapshots"]["all"]["surveys"]["SV_LANG_REPORT"]["responses"] == 3
    assert data["snapshots"]["DE"]["surveys"]["SV_LANG_REPORT"]["responses"] == 1
    assert data["snapshots"]["DE"]["surveys"]["SV_LANG_REPORT"]["answers"] == 2
    assert data["snapshots"]["__missing__"]["surveys"]["SV_LANG_REPORT"]["responses"] == 1
    assert sum(row["responses"] for row in data["snapshots"]["DE"]["dashboard"]["surveys"]) == 1
    assert data["snapshots"]["DE"]["questions"]["question-detail-1"]["respondents"] == 1
    assert len(data["snapshots"]["DE"]["questions"]) == 2
    assert len(entities.response_answers) == 6


def test_display_language_changes_labels_but_not_counts_or_raw_comment(tmp_path):
    entities = _survey(tmp_path)
    data = build_report_languages(entities)
    assert data["display_languages"] == ["EN", "DE"]
    question = next(
        row for row in entities.questions if row.get("question_external_id") == "QID1" and not row.get("is_localized")
    )
    assert data["labels"]["DE"]["questions"][question["question_id"]] == "Auswahl"
    assert data["labels"]["EN"]["questions"][question["question_id"]] == "Choice"
    assert set(data["snapshots"]) == {"all", "EN", "DE", "__missing__"}
    assert "Original German" in [row["answer_text"] for row in entities.response_answers]


def test_report_exposes_two_single_selects_and_response_language_lineage(tmp_path):
    entities = _survey(tmp_path)
    target = tmp_path / "report.html"
    render_report(entities, target)
    document = target.read_text(encoding="utf-8")
    assert "id='respondent-language'" in document
    assert "id='display-language'" in document
    assert "data-user-language='DE'" in document
    assert "data-user-language='__missing__'" in document
    assert "Original German" in document
    assert "data-language='DE'" in document
    encoded = document.split("<script id='report-language-data' type='application/json'>", 1)[1].split("</script>", 1)[
        0
    ]
    payload = json.loads(encoded)
    assert payload["snapshots"]["DE"]["surveys"]["SV_LANG_REPORT"]["responses"] == 1


def test_combined_report_preserves_nullable_cohorts_and_base_label_fallback(tmp_path):
    first = _survey(tmp_path / "first", "SV_FIRST")
    second = _survey(tmp_path / "second", "SV_SECOND", include_german=False)
    data = build_report_languages(merge_entity_sets([first, second]))
    assert data["snapshots"]["__missing__"]["surveys"]["SV_FIRST"]["responses"] == 1
    assert data["snapshots"]["__missing__"]["surveys"]["SV_SECOND"]["responses"] == 1
    assert data["snapshots"]["DE"]["surveys"]["SV_FIRST"]["answers"] == 2
    assert data["snapshots"]["DE"]["surveys"]["SV_SECOND"]["answers"] == 2
    second_question = next(
        row for row in second.questions if row.get("question_external_id") == "QID1" and not row.get("is_localized")
    )
    assert data["labels"]["DE"]["questions"][second_question["question_id"]] == "Choice"
