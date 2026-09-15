from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from qualtrics import parse_survey
from qualtrics._common.models.entity_set import merge_entity_sets
from qualtrics._common.models.semantic import build_semantic_model
from qualtrics._common.serialization.semantic import write_semantic_model


def _localized_survey(tmp_path: Path, survey_id: str = "SV_LABELS", *, include_french: bool = True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    responses = tmp_path / "responses.csv"
    with responses.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1"],
            ["Response ID", "User language", "Choice field"],
            ["{}", "{}", json.dumps({"ImportId": "QID1"})],
            ["R_1", "DE", "Ja"],
            ["R_2", "FR", "Yes"],
        ])
    definition = tmp_path / "definition.qsf"
    translations = {"DE": {"QuestionText": "Auswahl", "Choices": {"1": {"Display": "Ja"}}}}
    if include_french:
        translations["FR"] = {"QuestionText": "Choix"}
    definition.write_text(
        json.dumps({
            "SurveyID": survey_id,
            "SurveyOptions": {"SurveyLanguage": "EN", "AvailableLanguages": {"EN": [], "DE": []}},
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "Choice",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                    "Language": translations,
                },
                "QID2": {"QuestionID": "QID2", "QuestionText": "Not exported", "QuestionType": "TE"},
            },
        }),
        encoding="utf-8",
    )
    return parse_survey(responses, definition)


def test_semantic_label_tables_keep_base_join_grain_and_fallback_provenance(tmp_path: Path) -> None:
    entities = _localized_survey(tmp_path)
    model = build_semantic_model(entities)

    assert len(model.fact_response_answers) == 2
    assert len(model.dim_questions) == 1
    assert len(model.dim_answer_options) == 2
    base_field_id = model.dim_questions[0]["question_field_id"]
    base_option_ids = {row["answer_option_id"] for row in model.dim_answer_options}
    assert len(model.dim_question_labels) == 3
    assert len(model.dim_answer_option_labels) == 6
    assert {row["question_field_id"] for row in model.dim_question_labels} == {base_field_id}
    assert {row["answer_option_id"] for row in model.dim_answer_option_labels} == base_option_ids
    assert len({row["question_field_label_id"] for row in model.dim_question_labels}) == 3
    assert len({row["answer_option_label_id"] for row in model.dim_answer_option_labels}) == 6
    assert {
        (row["language_code"], row["is_available"], row["defined_survey_count"]) for row in model.dim_display_languages
    } == {
        ("EN", True, 1),
        ("DE", True, 1),
        ("FR", False, 1),
    }
    question_labels = {row["language_code"]: row for row in model.dim_question_labels}
    assert question_labels["DE"]["question_text"] == "Auswahl"
    assert question_labels["DE"]["question_label_source_language"] == "DE"
    assert question_labels["FR"]["question_text"] == "Choix"
    assert question_labels["FR"]["field_label_source_language"] == "EN"
    option_labels = {(row["language_code"], row["answer_external_id"]): row for row in model.dim_answer_option_labels}
    assert option_labels["DE", "1"]["answer_text"] == "Ja"
    assert option_labels["DE", "1"]["label_source_language"] == "DE"
    assert option_labels["DE", "2"]["answer_text"] == "No"
    assert option_labels["DE", "2"]["label_source_language"] == "EN"
    assert all(row["question_external_id"] != "QID2" for row in model.dim_question_labels)


def test_global_display_language_has_base_fallback_for_every_combined_survey(tmp_path: Path) -> None:
    first = _localized_survey(tmp_path / "first", "SV_FIRST")
    second = _localized_survey(tmp_path / "second", "SV_SECOND", include_french=False)
    model = build_semantic_model(merge_entity_sets([first, second]))

    assert len(model.fact_response_answers) == 4
    assert len(model.dim_questions) == 2
    assert len(model.dim_question_labels) == 6
    assert len(model.dim_answer_option_labels) == 12
    french = next(row for row in model.dim_display_languages if row["language_code"] == "FR")
    assert french["defined_survey_count"] == 1
    assert french["is_available"] is False
    fallback = next(
        row for row in model.dim_question_labels if row["survey_id"] == "SV_SECOND" and row["language_code"] == "FR"
    )
    assert fallback["question_text"] == "Choice"
    assert fallback["question_label_source_language"] == "EN"


@pytest.mark.parametrize("format", ["json", "csv", "parquet", "sqlite"])
def test_semantic_language_tables_export_stable_columns_and_ids(tmp_path: Path, format: str) -> None:
    model = build_semantic_model(_localized_survey(tmp_path))
    output = tmp_path / format
    write_semantic_model(model, output, format)
    for name, id_key in (
        ("dim_display_languages", "language_code"),
        ("dim_question_labels", "question_field_label_id"),
        ("dim_answer_option_labels", "answer_option_label_id"),
    ):
        if format == "sqlite":
            with sqlite3.connect(output / "semantic_model.sqlite") as connection:
                rows = connection.execute(f"SELECT {id_key} FROM {name}").fetchall()
            assert len(rows) == len(getattr(model, name))
        elif format == "json":
            rows = json.loads((output / f"{name}.json").read_text(encoding="utf-8"))
            assert {row[id_key] for row in rows} == {row[id_key] for row in getattr(model, name)}
        elif format == "csv":
            with (output / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            assert {row[id_key] for row in rows} == {row[id_key] for row in getattr(model, name)}
        else:
            import pyarrow.parquet as pq

            rows = pq.read_table(output / f"{name}.parquet").to_pylist()
            assert {row[id_key] for row in rows} == {row[id_key] for row in getattr(model, name)}
