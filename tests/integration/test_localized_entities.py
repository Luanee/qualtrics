from __future__ import annotations

import csv
import json
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile

import pytest

from qualtrics import parse_survey, parse_surveys
from qualtrics._common.analytics import analyze_entities
from qualtrics._common.models.entity_set import validate_entity_set
from qualtrics._common.models.semantic import build_semantic_model
from qualtrics._common.serialization.io import load_entities, write_entities
from qualtrics.ui.codebook import build_codebook


def _survey_files(folder: Path, survey_id: str = "SV_LANG") -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    responses = folder / "responses.csv"
    with responses.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1"],
            ["Response ID", "User language", "Which option?"],
            ["{}", "{}", json.dumps({"ImportId": "QID1"})],
            ["R_1", "DE", "1"],
            ["R_2", "FR", "2"],
        ])
    definition = folder / "definition.qsf"
    definition.write_text(
        json.dumps({
            "SurveyID": survey_id,
            "SurveyName": "Languages",
            "SurveyOptions": {"SurveyLanguage": "EN", "AvailableLanguages": {"EN": [], "DE": [], "FR": []}},
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "Which option?",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                    "ChoiceOrder": ["1", "2"],
                    "Language": {
                        "DE": {
                            "QuestionText": "Welche Option?",
                            "Choices": {"1": {"Display": "Ja"}},
                        },
                        "IT": {"Choices": {"2": {"Display": "No (IT)"}}},
                    },
                },
                "QID2": {
                    "QuestionID": "QID2",
                    "QuestionText": "Rate service",
                    "QuestionType": "Matrix",
                    "Selector": "Likert",
                    "Choices": {"1": {"Display": "Service"}},
                    "Answers": {"1": {"Display": "Good"}, "2": {"Display": "Bad"}},
                    "Language": {
                        "DE": {
                            "QuestionText": "Service bewerten",
                            "Choices": {"1": {"Display": "Dienstleistung"}},
                            "Answers": {"1": {"Display": "Gut"}},
                        }
                    },
                },
            },
        }),
        encoding="utf-8",
    )
    return responses, definition


def test_localized_entities_share_base_catalogs_without_multiplying_facts(tmp_path: Path) -> None:
    entities = parse_survey(*_survey_files(tmp_path))
    validate_entity_set(entities, strict=True)
    variants = [row for row in entities.questions if row["question_external_id"] == "QID1"]
    assert {row["language_code"] for row in variants} == {"EN", "DE", "FR", "IT"}
    assert len({row["question_id"] for row in variants}) == 4
    assert len({row["question_catalog_id"] for row in variants}) == 1
    by_language = {row["language_code"]: row for row in variants}
    assert by_language["EN"]["is_localized"] is False
    assert by_language["DE"]["question_text"] == "Welche Option?"
    assert by_language["DE"]["label_source_language"] == "DE"
    assert by_language["FR"]["question_text"] == "Which option?"
    assert by_language["FR"]["label_source_language"] == "EN"
    assert by_language["IT"]["label_source_language"] == "EN"

    fields = [row for row in entities.question_fields if row["question_external_id"] == "QID1"]
    assert {row["language_code"] for row in fields} == {"EN", "DE", "FR", "IT"}
    assert len({row["question_field_id"] for row in fields}) == 4
    assert len({row["question_field_catalog_id"] for row in fields}) == 1
    options = [row for row in entities.answer_options if row["question_external_id"] == "QID1"]
    assert len(options) == 8
    assert len({row["answer_option_id"] for row in options}) == 8
    assert len({row["answer_id"] for row in options}) == 2
    option_by_locale = {(row["language_code"], row["answer_id"]): row for row in options}
    assert option_by_locale["DE", "1"]["answer_text"] == "Ja"
    assert option_by_locale["DE", "1"]["label_source_language"] == "DE"
    assert option_by_locale["DE", "2"]["answer_text"] == "No"
    assert option_by_locale["DE", "2"]["label_source_language"] == "EN"
    assert option_by_locale["IT", "2"]["answer_text"] == "No (IT)"

    matrix_fields = [row for row in entities.question_fields if row["question_external_id"] == "QID2"]
    assert next(row for row in matrix_fields if row["language_code"] == "DE")["statement_text"] == "Dienstleistung"
    matrix_options = [row for row in entities.answer_options if row["question_external_id"] == "QID2"]
    assert (
        next(row for row in matrix_options if row["language_code"] == "DE" and row["answer_id"] == "1")["answer_text"]
        == "Gut"
    )
    assert all(row["is_definition_only"] for row in matrix_options)

    assert len(entities.response_answers) == 2
    assert {row["question_id"] for row in entities.response_answers} == {by_language["EN"]["question_id"]}
    assert len(analyze_entities(entities).response_questions) == 1
    semantic = build_semantic_model(entities)
    assert len(semantic.dim_questions) == 1
    assert len(semantic.dim_answer_options) == 2
    assert {row["language_code"] for row in semantic.dim_questions} == {"EN"}
    codebook = build_codebook(entities)
    german = next(row for row in codebook if row["question_id"] == "QID1" and row["language_code"] == "DE")
    assert german["question"] == "Welche Option?"
    assert german["export_column"] == german["storage_column"] == ""
    assert german["kind"] == "translation"
    french = next(row for row in codebook if row["question_id"] == "QID1" and row["language_code"] == "FR")
    assert french["label_source_language"] == "EN"


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_localized_rows_round_trip_with_ids_and_label_provenance(tmp_path: Path, format: str) -> None:
    entities = parse_survey(*_survey_files(tmp_path / "source"))
    folder = tmp_path / format
    write_entities(entities, folder, format)
    restored = load_entities(folder)
    validate_entity_set(restored, strict=True)
    for name in ("questions", "question_fields", "answer_options"):
        id_key = {
            "questions": "question_id",
            "question_fields": "question_field_id",
            "answer_options": "answer_option_id",
        }[name]
        expected = sorted(
            getattr(entities, name),
            key=lambda row: row[id_key],
        )
        actual = sorted(
            getattr(restored, name),
            key=lambda row: row[id_key],
        )
        assert [row[id_key] for row in actual] == [row[id_key] for row in expected]
        assert [(row["language_code"], row["label_source_language"], row["is_localized"]) for row in actual] == [
            (row["language_code"], row["label_source_language"], row["is_localized"]) for row in expected
        ]


def test_localized_ids_do_not_collide_between_surveys_and_zip_matches_csv(tmp_path: Path) -> None:
    first_csv, first_qsf = _survey_files(tmp_path / "first", "SV_FIRST")
    second_csv, second_qsf = _survey_files(tmp_path / "second", "SV_SECOND")
    archive = tmp_path / "first" / "export.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.write(first_csv, arcname="responses.csv")

    from_csv = parse_survey(first_csv, first_qsf)
    from_zip = parse_survey(archive, first_qsf)
    assert from_csv == from_zip
    combined = parse_surveys([first_csv, second_csv], [first_qsf, second_qsf])
    validate_entity_set(combined, strict=True)
    assert set(combined.survey_manifests) == {"SV_FIRST", "SV_SECOND"}
    assert all(
        manifest["languages"]["all_languages"] == ["EN", "DE", "FR", "IT"]
        for manifest in combined.survey_manifests.values()
    )
    assert len(combined.response_answers) == 4
    assert len({row["question_id"] for row in combined.questions}) == len(combined.questions)
    assert len({row["question_field_id"] for row in combined.question_fields}) == len(combined.question_fields)
    assert len({row["answer_option_id"] for row in combined.answer_options}) == len(combined.answer_options)
    assert len(build_semantic_model(combined).fact_response_answers) == 4


@pytest.mark.parametrize("entity_name", ["questions", "question_fields", "answer_options"])
def test_localized_rows_reject_unregistered_language(tmp_path: Path, entity_name: str) -> None:
    entities = deepcopy(parse_survey(*_survey_files(tmp_path)))
    localized = next(row for row in getattr(entities, entity_name) if row["is_localized"])
    localized["language_code"] = "ZZ"
    with pytest.raises(ValueError, match="localized row has invalid language_code"):
        validate_entity_set(entities, strict=True)
