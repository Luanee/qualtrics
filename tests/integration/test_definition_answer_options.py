from __future__ import annotations

import csv
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from qualtrics import load_entities, parse_survey, write_entities
from qualtrics.models.entity_set import validate_entity_set
from qualtrics.models.semantic import build_semantic_model


@pytest.fixture
def definition_answer_files(tmp_path: Path) -> tuple[Path, Path]:
    csv_path = tmp_path / "answers.csv"
    qsf_path = tmp_path / "answers.qsf"
    columns = [
        "ResponseId",
        "QID1",
        "one",
        "two",
        "two_TEXT",
        "matrix_one",
        "matrix_two",
        "QID4",
        "QID5",
        "QID6_1",
    ]
    headers = [
        "Response ID",
        "Preferred color",
        "Features - Fast",
        "Features - Safe",
        "Features - Safe - Text",
        "Service - Delivery",
        "Service - Support",
        "Comment",
        "Score",
        "Contact - Name",
    ]
    metadata = [
        {},
        {"ImportId": "QID1"},
        {"ImportId": "1_QID2"},
        {"ImportId": "unexpected", "questionId": "QID2", "choiceId": "2"},
        {"ImportId": "2_QID2_TEXT"},
        {"ImportId": "1_QID3"},
        {"ImportId": "QID3_2"},
        {"ImportId": "QID4"},
        {"ImportId": "QID5"},
        {"ImportId": "QID6_1"},
    ]
    response = ["R1", "Red", "Selected", "", "because", "Good", "Bad", "free text", "73", "Ada"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([columns, headers, [json.dumps(item) for item in metadata], response])

    questions = {
        "QID1": {
            "QuestionID": "QID1",
            "QuestionText": "Preferred color",
            "QuestionType": "MC",
            "Selector": "SAVR",
            "Choices": {"1": {"Display": "Red"}, "2": {"Display": "Blue"}, "10": {"Display": "Green"}},
            "ChoiceOrder": ["2", "1"],
            "RecodeValues": {"1": "R", "2": "B"},
        },
        "QID2": {
            "QuestionID": "QID2",
            "QuestionText": "Features",
            "QuestionType": "MC",
            "Selector": "MAVR",
            "Choices": {"1": {"Display": "Fast"}, "2": {"Display": "Safe"}},
            "ChoiceOrder": ["2", "1"],
        },
        "QID3": {
            "QuestionID": "QID3",
            "QuestionText": "Service",
            "QuestionType": "Matrix",
            "Selector": "Likert",
            "Choices": {"1": {"Display": "Delivery"}, "2": {"Display": "Support"}},
            "Answers": {"1": {"Display": "Bad"}, "2": {"Display": "OK"}, "3": {"Display": "Good"}},
            "AnswerOrder": ["3", "1"],
            "RecodeValues": {"1": "-1", "2": "0", "3": "1"},
        },
        "QID4": {"QuestionID": "QID4", "QuestionText": "Comment", "QuestionType": "TE", "Selector": "SL"},
        "QID5": {"QuestionID": "QID5", "QuestionText": "Score", "QuestionType": "Slider"},
        "QID6": {
            "QuestionID": "QID6",
            "QuestionText": "Contact",
            "QuestionType": "TE",
            "Selector": "FORM",
            "Choices": {"1": {"Display": "Name"}},
        },
    }
    qsf_path.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_OPTIONS", "SurveyName": "Options"},
            "SurveyElements": [
                *({"Element": "SQ", "PrimaryAttribute": qid, "Payload": payload} for qid, payload in questions.items()),
                {
                    "Element": "BL",
                    "Payload": {
                        "BL1": {
                            "ID": "BL1",
                            "Description": "Questions",
                            "Type": "Standard",
                            "BlockElements": [{"Type": "Question", "QuestionID": qid} for qid in questions],
                        }
                    },
                },
            ],
        }),
        encoding="utf-8",
    )
    return csv_path, qsf_path


def _fields_by_external_id(csv_path: Path, qsf_path: Path) -> dict[str, dict[str, object]]:
    return {str(row["field_external_id"]): row for row in parse_survey(csv_path, qsf_path).question_fields}


def test_export_fields_map_to_definition_choices(definition_answer_files: tuple[Path, Path]) -> None:
    fields = _fields_by_external_id(*definition_answer_files)
    assert fields["one"]["choice_external_id"] == "1"
    assert fields["two"]["choice_external_id"] == "2"
    assert fields["two_TEXT"]["choice_external_id"] == "2"
    assert fields["matrix_one"]["choice_external_id"] == "1"
    assert fields["matrix_two"]["choice_external_id"] == "2"
    assert fields["QID1"]["choice_external_id"] is None


def test_single_choice_domain_includes_unobserved_choices_order_and_recodes(
    definition_answer_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*definition_answer_files)
    question = next(row for row in entities.questions if row["question_external_id"] == "QID1")
    field = next(row for row in entities.question_fields if row["question_external_id"] == "QID1")
    options = [row for row in entities.answer_options if row["question_id"] == question["question_id"]]
    assert [(row["answer_id"], row["answer_code"], row["answer_text"], row["answer_order"]) for row in options] == [
        ("2", "B", "Blue", 1),
        ("1", "R", "Red", 2),
        ("10", "10", "Green", 3),
    ]
    assert {row["question_field_id"] for row in options} == {field["question_field_id"]}
    assert {row["field_id"] for row in options} == {field["question_field_id"]}


def test_multiple_choice_has_one_option_per_selection_field_and_none_for_text(
    definition_answer_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*definition_answer_files)
    fields = {str(row["field_external_id"]): row for row in entities.question_fields}
    options = [row for row in entities.answer_options if row["question_external_id"] == "QID2"]
    assert {(row["source_import_id"], row["answer_id"], row["answer_text"]) for row in options} == {
        ("1_QID2", "1", "Fast"),
        ("unexpected", "2", "Safe"),
    }
    assert {row["question_field_id"] for row in options} == {
        fields["one"]["question_field_id"],
        fields["two"]["question_field_id"],
    }
    assert fields["two_TEXT"]["question_field_id"] not in {row["question_field_id"] for row in options}


def test_matrix_answers_are_materialized_for_each_row_in_answer_order(
    definition_answer_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*definition_answer_files)
    fields = {str(row["field_external_id"]): row for row in entities.question_fields}
    options = [row for row in entities.answer_options if row["question_external_id"] == "QID3"]
    assert len(options) == 6
    for field_name in ("matrix_one", "matrix_two"):
        field_options = [row for row in options if row["question_field_id"] == fields[field_name]["question_field_id"]]
        assert [(row["answer_id"], row["answer_code"], row["answer_order"]) for row in field_options] == [
            ("3", "1", 1),
            ("1", "-1", 2),
            ("2", "0", 3),
        ]


def test_text_form_and_slider_fields_have_no_answer_options(definition_answer_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*definition_answer_files)
    assert not [row for row in entities.answer_options if row["question_external_id"] in {"QID4", "QID5", "QID6"}]


def test_responses_resolve_only_against_their_field_domain(
    definition_answer_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*definition_answer_files)
    fields = {str(row["field_external_id"]): row for row in entities.question_fields}
    options = {str(row["answer_option_id"]): row for row in entities.answer_options}
    answers = {str(row["field_external_id"]): row for row in entities.response_answers}

    assert options[str(answers["QID1"]["answer_option_id"])]["answer_id"] == "1"
    assert options[str(answers["one"]["answer_option_id"])]["answer_id"] == "1"
    assert options[str(answers["matrix_one"]["answer_option_id"])]["answer_id"] == "3"
    assert options[str(answers["matrix_two"]["answer_option_id"])]["answer_id"] == "1"
    assert answers["two_TEXT"]["answer_option_id"] is None
    assert answers["QID4"]["answer_option_id"] is None
    assert answers["QID5"]["answer_option_id"] is None
    assert answers["one"]["question_field_id"] == fields["one"]["question_field_id"]


def test_unknown_and_ambiguous_values_remain_raw(
    definition_answer_files: tuple[Path, Path],
) -> None:
    csv_path, qsf_path = definition_answer_files
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    rows[3][1] = "Same"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qsf = json.loads(qsf_path.read_text(encoding="utf-8"))
    question = next(item["Payload"] for item in qsf["SurveyElements"] if item.get("PrimaryAttribute") == "QID1")
    question["Choices"]["1"]["Display"] = "Same"
    question["Choices"]["2"]["Display"] = "Same"
    qsf_path.write_text(json.dumps(qsf), encoding="utf-8")

    answer = next(
        row for row in parse_survey(csv_path, qsf_path).response_answers if row["field_external_id"] == "QID1"
    )
    assert answer["answer_text"] == "Same"
    assert answer["answer_option_id"] is None


def test_csv_and_zip_produce_identical_entities(definition_answer_files: tuple[Path, Path], tmp_path: Path) -> None:
    csv_path, qsf_path = definition_answer_files
    zip_path = tmp_path / "answers.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        archive.write(csv_path, csv_path.name)

    csv_entities = parse_survey(csv_path, qsf_path)
    zip_entities = parse_survey(zip_path, qsf_path)
    assert zip_entities == csv_entities


def test_option_identity_is_scoped_to_survey_and_field(definition_answer_files: tuple[Path, Path]) -> None:
    first = parse_survey(*definition_answer_files, survey_id="SV_FIRST")
    second = parse_survey(*definition_answer_files, survey_id="SV_SECOND")
    assert {row["answer_option_id"] for row in first.answer_options}.isdisjoint({
        row["answer_option_id"] for row in second.answer_options
    })


@pytest.mark.parametrize("format", ["csv", "json", "parquet"])
def test_answer_option_roundtrip_preserves_field_grain(
    definition_answer_files: tuple[Path, Path], tmp_path: Path, format: str
) -> None:
    entities = parse_survey(*definition_answer_files)
    output = tmp_path / format
    write_entities(entities, output, format)

    loaded = load_entities(output)
    assert loaded.answer_options == entities.answer_options
    assert all(isinstance(row["answer_order"], int) for row in loaded.answer_options)
    assert all(row["question_field_id"] == row["field_id"] for row in loaded.answer_options)


def test_answer_option_requires_a_valid_question_field(definition_answer_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*definition_answer_files)
    entities.answer_options[0]["question_field_id"] = "missing"
    entities.answer_options[0]["field_id"] = "missing"

    with pytest.raises(ValueError, match="has no parent in question_fields"):
        validate_entity_set(entities, strict=True)


def test_semantic_answer_options_have_field_scoped_grain(definition_answer_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*definition_answer_files)
    model = build_semantic_model(entities)

    assert model.dim_answer_options == entities.answer_options
    assert len({row["answer_option_id"] for row in model.dim_answer_options}) == len(model.dim_answer_options)
    question_fields = {row["question_field_id"] for row in model.dim_questions}
    assert {row["question_field_id"] for row in model.dim_answer_options} <= question_fields
