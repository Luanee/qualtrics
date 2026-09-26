"""Each repeated single-choice field owns its complete definition domain."""

import csv
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from qualtrics import build_semantic_model, load_entities, parse_survey, write_entities
from qualtrics._common.models.entity_set import validate_entity_set


def _survey_files(folder: Path) -> tuple[Path, Path]:
    source, definition = folder / "responses.csv", folder / "definition.qsf"
    columns = ["1_QID1", "2_QID1", "3_QID1", "4_QID1", "1_QID1_10_TEXT"]
    with source.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", *columns],
            ["Response ID", "Color", "Color", "Color", "Color", "Color - Other - Text"],
            ["{}", *[json.dumps({"ImportId": column}) for column in columns]],
            ["R1", "02", "00", "", "", "  because  "],
            ["R2", "unknown", "Blue", "10", "", ""],
        ])
    definition.write_text(
        json.dumps({
            "SurveyID": "SV_LOOP_SINGLE",
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "Color",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {"1": {"Display": "Red"}, "2": {"Display": "Blue"}, "10": {"Display": "Blue"}},
                    "ChoiceOrder": ["2", "1"],
                    "RecodeValues": {"1": "02", "2": "00", "10": "other"},
                }
            },
        }),
        encoding="utf-8",
    )
    return source, definition


@pytest.mark.parametrize("file_format", ["csv", "json", "parquet"])
def test_looped_single_choice_domains_survive_storage_and_semantic_export(tmp_path: Path, file_format: str) -> None:
    source, definition = _survey_files(tmp_path)
    entities = parse_survey(source, definition)
    fields = {row["field_external_id"]: row for row in entities.question_fields}
    # Captured from main before correcting the missing domains: occurrence
    # identities and existing option IDs do not depend on the added domains.
    assert entities.questions[0]["question_id"] == "69b9e276d487b9c374bac6bd3dd3afd76b3ff42e0817bd94b2f8139ec116e88e"
    assert fields["2_QID1"]["question_field_id"] == "5b95eaf7f2c00f008ee06c50138151b11b4c0a58cd1a12716e06e7885f97b5df"
    assert (
        entities.response_answers[1]["response_answer_id"]
        == "853fcd1d102cfb0a247504c1495d5bc33f22767c09f6f8c342ef5b1af224e807"
    )
    assert (
        entities.answer_options[0]["answer_option_id"]
        == "a94607295a2cb046d26955f9b1a46b07c81538a214d9d45c329a3d33be31494d"
    )

    for name in ("1_QID1", "2_QID1", "3_QID1", "4_QID1"):
        domain = [
            row for row in entities.answer_options if row["question_field_id"] == fields[name]["question_field_id"]
        ]
        assert [(row["answer_id"], row["answer_code"], row["answer_order"]) for row in domain] == [
            ("2", "00", 1),
            ("1", "02", 2),
            ("10", "other", 3),
        ]
        assert all(row["source_import_id"] == name for row in domain)
    assert len({row["answer_option_id"] for row in entities.answer_options}) == 12
    assert not any(row["field_external_id"] == "4_QID1" for row in entities.response_answers)
    assert len(entities.response_answers) == 6
    options = {row["answer_option_id"]: row for row in entities.answer_options}
    for row in entities.response_answers:
        assert row["answer_text"] == row["raw_value"]
        if row["raw_value"] in {"unknown", "Blue", "  because  "}:
            assert row["answer_option_id"] is None
        else:
            option = options[row["answer_option_id"]]
            assert option["question_field_id"] == row["question_field_id"]
            assert option["answer_id"] == {"02": "1", "00": "2", "10": "10"}[row["raw_value"]]
    assert [row["answer_text"] for row in entities.comments] == ["  because  "]
    validate_entity_set(entities, strict=True)

    archive = tmp_path / "responses.zip"
    with ZipFile(archive, "w") as handle:
        handle.write(source, "responses.csv")
    assert parse_survey(archive, definition) == entities
    output = tmp_path / "entities"
    write_entities(entities, output, file_format)
    loaded = load_entities(output)
    assert loaded.answer_options == entities.answer_options
    assert loaded.response_answers == entities.response_answers
    semantic = build_semantic_model(loaded)
    assert len(semantic.dim_answer_options) == 12
    assert len(semantic.fact_response_answers) == 6
