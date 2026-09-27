"""The offline report keeps respondent and definition language independent."""

from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from qualtrics import build_semantic_model, parse_survey
from qualtrics._common.models.entity_set import merge_entity_sets, validate_entity_set
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


def test_localized_labels_follow_occurrences_not_shared_catalogs(tmp_path: Path) -> None:
    collections = []
    for survey_id in ("SV_FIRST", "SV_SECOND"):
        source = tmp_path / f"{survey_id}.csv"
        columns = [f"QID{question}_{row}" for question in (1, 2) for row in (1, 2)]
        with source.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows([
                ["ResponseId", "UserLanguage", *columns],
                ["Response ID", "Language", *["Choice - Item"] * 4],
                ["{}", "{}", *[json.dumps({"ImportId": column}) for column in columns]],
                ["R_1", "DE", "1", "2", "1", "2"],
            ])
        definition = tmp_path / f"{survey_id}.qsf"
        definition.write_text(
            json.dumps({
                "SurveyID": survey_id,
                "SurveyOptions": {"SurveyLanguage": "EN", "AvailableLanguages": {"DE": []}},
                "Questions": {
                    f"QID{question}": {
                        "QuestionID": f"QID{question}",
                        "QuestionText": "Choice",
                        "QuestionType": "Matrix",
                        "Selector": "Likert",
                        "SubSelector": "SingleAnswer",
                        "Choices": {"1": {"Display": "Item"}, "2": {"Display": "Item"}},
                        "Answers": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                        "Language": {
                            "DE": {
                                "QuestionText": f"Auswahl {survey_id} QID{question}",
                                "Choices": {
                                    str(row): {"Display": f"Zeile {survey_id} QID{question}_{row}"} for row in (1, 2)
                                },
                                "Answers": {
                                    "1": {"Display": f"Ja {survey_id} QID{question}"},
                                    "2": {"Display": f"Nein {survey_id} QID{question}"},
                                },
                            }
                        },
                    }
                    for question in (1, 2)
                },
            }),
            encoding="utf-8",
        )
        collections.append(parse_survey(source, definition))
    entities = merge_entity_sets(collections)
    before = deepcopy(entities)
    assert len(entities.question_catalog) == 1
    assert len(entities.question_field_catalog) == 1

    report = build_report_languages(entities)
    semantic = build_semantic_model(entities)
    labels = report["labels"]["DE"]
    fields = {row["question_field_id"]: row for row in entities.question_fields if not row["is_localized"]}
    assert len(fields) == 8
    for field_id, row in fields.items():
        expected = f"Zeile {row['survey_id']} {row['field_external_id']}"
        assert labels["fields"][field_id] == expected
    for row in entities.answer_options:
        if row["is_localized"]:
            continue
        prefix = "Ja" if row["answer_external_id"] == "1" else "Nein"
        assert (
            labels["options"][row["answer_option_id"]] == f"{prefix} {row['survey_id']} {row['question_external_id']}"
        )
    for row in semantic.dim_question_labels:
        if row["language_code"] == "DE":
            assert labels["fields"][row["question_field_id"]] == row["field_text"]
            assert labels["questions"][row["question_id"]] == row["question_text"]
    for row in semantic.dim_answer_option_labels:
        if row["language_code"] == "DE":
            assert labels["options"][row["answer_option_id"]] == row["answer_text"]
    assert len(semantic.fact_response_answers) == 8
    assert entities == before


@pytest.mark.parametrize("include_german", [False, True])
def test_missing_native_field_lineage_preserves_unambiguous_labels(tmp_path: Path, include_german: bool) -> None:
    entities = _survey(tmp_path, include_german=include_german)
    for row in entities.question_fields:
        row["field_external_id"] = None
        if not include_german:
            row["question_external_id"] = None
    validate_entity_set(entities, strict=True)

    report = build_report_languages(entities)

    for row in entities.question_fields:
        if row.get("is_localized"):
            continue
        assert report["labels"]["EN"]["fields"][row["question_field_id"]] == row["field_text"]
        if include_german:
            expected = {"QID1": "Auswahl", "QID2": "Kommentar", "QID3": "Definition only"}
            assert report["labels"]["DE"]["fields"][row["question_field_id"]] == expected[row["question_external_id"]]
    for row in entities.answer_options:
        if row.get("is_localized"):
            continue
        assert report["labels"]["EN"]["options"][row["answer_option_id"]] == row["answer_text"]
        if include_german:
            assert report["labels"]["DE"]["options"][row["answer_option_id"]] == (
                "Ja" if row["answer_external_id"] == "1" else "No"
            )


def test_ambiguous_legacy_field_catalog_keeps_original_labels(tmp_path: Path) -> None:
    entities = _survey(tmp_path)
    for row in entities.question_fields:
        row["field_external_id"] = None
    original = next(row for row in entities.question_fields if not row["is_localized"])
    duplicate = {
        **original,
        "question_field_id": "second-occurrence",
        "field_id": "second-occurrence",
        "field_text": "CHOICE",
    }
    entities.question_fields.append(duplicate)
    validate_entity_set(entities, strict=True)

    report = build_report_languages(entities)

    for row in (original, duplicate):
        assert report["labels"]["DE"]["fields"][row["question_field_id"]] == row["field_text"]
        assert report["label_fallbacks"]["DE"]["fields"][row["question_field_id"]]["reason"] == "missing"
    for row in entities.answer_options:
        if not row["is_localized"]:
            assert report["labels"]["DE"]["options"][row["answer_option_id"]] == row["answer_text"]
