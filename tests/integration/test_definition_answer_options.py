from __future__ import annotations

import csv
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from qualtrics import load_entities, parse_survey, write_entities
from qualtrics._common.analytics import analyze_entities
from qualtrics._common.models.entity_set import validate_entity_set
from qualtrics._common.models.semantic import build_semantic_model
from qualtrics.ui import render_report


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
            "ChoiceDataExportTags": {"1": "ROW_TAG"},
            "AnswerDataExportTags": {"3": "GOOD_TAG"},
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
        assert field_options[0]["answer_export_tag"] == "GOOD_TAG"


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


@pytest.mark.parametrize("recodes", [{"1": "2", "2": "3"}, {"1": "2"}, {"1": 0, "2": 2}])
def test_explicit_recode_wins_over_another_native_choice_id(
    definition_answer_files: tuple[Path, Path], recodes: dict[str, str | int]
) -> None:
    csv_path, qsf_path = definition_answer_files
    qsf = json.loads(qsf_path.read_text())
    question = next(item["Payload"] for item in qsf["SurveyElements"] if item.get("PrimaryAttribute") == "QID1")
    question["RecodeValues"] = recodes
    question["Choices"]["0"] = {"Display": "Other"}
    qsf_path.write_text(json.dumps(qsf))
    with csv_path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    rows[3][1] = str(recodes["1"])
    with csv_path.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)

    entities = parse_survey(csv_path, qsf_path)

    answer = next(row for row in entities.response_answers if row["field_external_id"] == "QID1")
    option = next(row for row in entities.answer_options if row["answer_option_id"] == answer["answer_option_id"])
    assert option["answer_external_id"] == "1"
    assert option["answer_text"] == "Red"
    assert answer["answer_text"] == str(recodes["1"])
    assert not any(key.startswith("_") for option in entities.answer_options for key in option)


def test_matrix_recode_wins_within_each_row_domain(definition_answer_files: tuple[Path, Path]) -> None:
    csv_path, qsf_path = definition_answer_files
    with csv_path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    rows[3][5:7] = ["1", "1"]
    with csv_path.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)

    entities = parse_survey(csv_path, qsf_path)
    options = {row["answer_option_id"]: row for row in entities.answer_options}
    answers = [row for row in entities.response_answers if row["question_external_id"] == "QID3"]
    assert len(answers) == 2
    assert len({row["answer_option_id"] for row in answers}) == 2
    for answer in answers:
        option = options[answer["answer_option_id"]]
        assert option["answer_external_id"] == "3"
        assert option["answer_text"] == "Good"
        assert option["question_field_id"] == answer["question_field_id"]


def test_duplicate_explicit_recodes_remain_unresolved(definition_answer_files: tuple[Path, Path]) -> None:
    csv_path, qsf_path = definition_answer_files
    qsf = json.loads(qsf_path.read_text())
    question = next(item["Payload"] for item in qsf["SurveyElements"] if item.get("PrimaryAttribute") == "QID1")
    question["RecodeValues"] = {"1": "2", "2": "2"}
    qsf_path.write_text(json.dumps(qsf))
    with csv_path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    rows[3][1] = "2"
    with csv_path.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)

    answer = next(
        row for row in parse_survey(csv_path, qsf_path).response_answers if row["field_external_id"] == "QID1"
    )
    assert answer["answer_option_id"] is None
    assert answer["answer_text"] == "2"


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


@pytest.mark.parametrize("selector", ["TE", "CS"])
def test_continuous_matrix_variants_have_no_options(definition_answer_files: tuple[Path, Path], selector: str) -> None:
    csv_path, qsf_path = definition_answer_files
    qsf = json.loads(qsf_path.read_text(encoding="utf-8"))
    question = next(item["Payload"] for item in qsf["SurveyElements"] if item.get("PrimaryAttribute") == "QID3")
    question["Selector"] = selector
    qsf_path.write_text(json.dumps(qsf), encoding="utf-8")

    entities = parse_survey(csv_path, qsf_path)
    assert not [row for row in entities.answer_options if row["question_external_id"] == "QID3"]


def test_multiple_answer_matrix_has_one_option_per_cell(
    definition_answer_files: tuple[Path, Path], tmp_path: Path
) -> None:
    csv_path, qsf_path = definition_answer_files
    rows = list(csv.reader(csv_path.open(encoding="utf-8")))
    rows[2][5] = json.dumps({"ImportId": "1_QID3_3"})
    rows[2][6] = json.dumps({"ImportId": "2_QID3_1"})
    rows[3][5:7] = ["Selected", "Selected"]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qsf = json.loads(qsf_path.read_text(encoding="utf-8"))
    question = next(item["Payload"] for item in qsf["SurveyElements"] if item.get("PrimaryAttribute") == "QID3")
    question["SubSelector"] = "MultipleAnswer"
    qsf_path.write_text(json.dumps(qsf), encoding="utf-8")

    entities = parse_survey(csv_path, qsf_path)
    options = [row for row in entities.answer_options if row["question_external_id"] == "QID3"]
    assert [(row["source_import_id"], row["answer_id"]) for row in options] == [
        ("1_QID3_3", "3"),
        ("2_QID3_1", "1"),
    ]
    answers = [row for row in entities.response_answers if row["question_external_id"] == "QID3"]
    assert all(answer["answer_option_id"] for answer in answers)
    output = tmp_path / "matrix-multiple.html"
    render_report(entities, output)
    section = output.read_text(encoding="utf-8").split("data-question='QID3'", 1)[1].split("</details>", 1)[0]
    assert ">Good</span>" in section
    assert ">Bad</span>" in section
    assert ">Selected</span>" not in section


def test_single_answer_matrix_report_includes_unobserved_definition_options(
    definition_answer_files: tuple[Path, Path], tmp_path: Path
) -> None:
    entities = parse_survey(*definition_answer_files)
    output = tmp_path / "matrix-single.html"
    render_report(entities, output)
    section = output.read_text(encoding="utf-8").split("data-question='QID3'", 1)[1].split("</details>", 1)[0]
    assert ">OK</span>" in section
    assert "option-zero" in section


def test_analytics_counts_linked_option_even_when_raw_value_is_selected(
    definition_answer_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*definition_answer_files)
    selected = next(
        row for row in entities.answer_options if row["question_external_id"] == "QID2" and row["answer_id"] == "1"
    )
    assert selected not in analyze_entities(entities).unused_options


def test_validation_rejects_cross_field_option_links(definition_answer_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*definition_answer_files)
    answer = next(row for row in entities.response_answers if row.get("answer_option_id"))
    foreign_option = next(
        row for row in entities.answer_options if row["question_field_id"] != answer["question_field_id"]
    )
    answer["answer_option_id"] = foreign_option["answer_option_id"]

    with pytest.raises(ValueError, match="option must belong"):
        validate_entity_set(entities, strict=True)


def test_validation_rejects_response_answer_lineage_mismatch(definition_answer_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*definition_answer_files)
    answer = entities.response_answers[0]
    answer["question_id"] = next(
        row["question_id"] for row in entities.questions if row["question_id"] != answer["question_id"]
    )

    with pytest.raises(ValueError, match="lineage must match"):
        validate_entity_set(entities, strict=True)


def test_validation_reports_missing_response_answer_field_id_as_contract_error(
    definition_answer_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*definition_answer_files)
    entities.response_answers[0].pop("field_id")

    with pytest.raises(ValueError, match="response_answers row is missing required columns: field_id"):
        validate_entity_set(entities, strict=True)


def test_empty_csv_table_must_expose_current_answer_option_schema(
    definition_answer_files: tuple[Path, Path], tmp_path: Path
) -> None:
    output = tmp_path / "entities"
    write_entities(parse_survey(*definition_answer_files), output, "csv")
    (output / "answer_options.csv").write_text("answer_option_id,question_id,survey_id\n", encoding="utf-8")

    with pytest.raises(ValueError, match="answer_options schema is missing required columns"):
        load_entities(output)


@pytest.fixture
def looped_answer_files(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "looped.csv"
    definition = tmp_path / "looped.qsf"
    imports = ["2_QID1_1", "1_QID1_2", "1_QID1_1"]
    with source.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", *imports],
            ["Response ID", "Features - Fast", "Features - Safe", "Features - Fast"],
            ["{}", *(json.dumps({"ImportId": value}) for value in imports)],
            ["R1", "Selected", "Selected", "Selected"],
        ])
    definition.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_LOOP", "SurveyName": "Looped options"},
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "Features",
                    "QuestionType": "MC",
                    "Selector": "MAVR",
                    "Choices": {"1": {"Display": "Fast"}, "2": {"Display": "Safe"}},
                }
            },
        }),
        encoding="utf-8",
    )
    return source, definition


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_looped_selections_keep_native_choice_links_through_storage_and_reporting(
    looped_answer_files, tmp_path, format
):
    entities = parse_survey(*looped_answer_files)
    assert [field["choice_external_id"] for field in entities.question_fields] == ["1", "2", "1"]
    assert len({field["question_field_id"] for field in entities.question_fields}) == 3
    assert len({answer["response_answer_id"] for answer in entities.response_answers}) == 3
    write_entities(entities, tmp_path / "entities", format)
    loaded = load_entities(tmp_path / "entities")
    model = build_semantic_model(loaded)
    options = {option["answer_option_id"]: option for option in model.dim_answer_options}
    assert [answer["raw_value"] for answer in model.fact_response_answers] == ["Selected"] * 3
    assert [answer["answer_text"] for answer in model.fact_response_answers] == ["Selected"] * 3
    linked = [options[answer["answer_option_id"]] for answer in model.fact_response_answers]
    assert [(option["source_choice_id"], option["choice_value"]) for option in linked] == [
        ("1", "Fast"),
        ("2", "Safe"),
        ("1", "Fast"),
    ]
    assert [option["question_field_id"] for option in linked] == [
        answer["question_field_id"] for answer in model.fact_response_answers
    ]
    output = tmp_path / "report.html"
    render_report(loaded, output)
    document = output.read_text(encoding="utf-8").split("data-question='QID1'", 1)[1].split("</details>", 1)[0]
    assert ">Fast</span>" in document
    assert ">Safe</span>" in document
    assert ">Selected</span>" not in document


@pytest.mark.parametrize("key", ["choiceId", "ChoiceId", "choiceID"])
@pytest.mark.parametrize(("explicit", "expected"), [("2", "2"), ("invalid", "1")])
def test_looped_choice_metadata_precedes_suffix_but_invalid_metadata_does_not(
    looped_answer_files, key, explicit, expected
):
    source, definition = looped_answer_files
    with source.open(newline="") as handle:
        rows = list(csv.reader(handle))
    rows[2][1] = json.dumps({"ImportId": "2_QID1_1", key: explicit})
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    entities = parse_survey(source, definition)
    field = entities.question_fields[0]
    answer = entities.response_answers[0]
    option = next(
        option for option in entities.answer_options if option["answer_option_id"] == answer["answer_option_id"]
    )
    assert field["choice_external_id"] == option["source_choice_id"] == expected


@pytest.mark.parametrize("multiple", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("looped", [False, True])
def test_looped_matrix_rows_and_cells_use_suffix_positions(definition_answer_files, multiple, explicit, looped):
    source, definition = definition_answer_files
    with source.open(newline="") as handle:
        rows = list(csv.reader(handle))
    first = "2_QID3_1_3" if multiple else "2_QID3_1"
    second = "1_QID3_2_1" if multiple else "1_QID3_2"
    if not looped:
        first, second = first[2:], second[2:]
    rows[2][5] = json.dumps({"ImportId": first, **({"choiceId": "2", "answerId": "2"} if explicit else {})})
    rows[2][6] = json.dumps({"ImportId": second, "choiceId": "invalid", "answerId": "invalid"})
    rows[3][5:7] = ["Selected", "Selected"] if multiple else ["1", "-1"]
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qsf = json.loads(definition.read_text())
    matrix = next(item["Payload"] for item in qsf["SurveyElements"] if item.get("PrimaryAttribute") == "QID3")
    if multiple:
        matrix["SubSelector"] = "MultipleAnswer"
    definition.write_text(json.dumps(qsf))
    entities = parse_survey(source, definition)
    fields = [field for field in entities.question_fields if field["question_external_id"] == "QID3"]
    assert [field["choice_external_id"] for field in fields] == (["2", "2"] if explicit else ["1", "2"])
    assert [field["statement_text"] for field in fields] == (
        ["Support", "Support"] if explicit else ["Delivery", "Support"]
    )
    options = {option["answer_option_id"]: option for option in entities.answer_options}
    answers = [answer for answer in entities.response_answers if answer["question_external_id"] == "QID3"]
    assert [options[answer["answer_option_id"]]["source_choice_id"] for answer in answers] == [
        "2" if multiple and explicit else "3",
        "1",
    ]


def test_looped_parser_preserves_baseline_occurrence_and_unchanged_catalog_ids(looped_answer_files):
    entities = parse_survey(*looped_answer_files)
    # Captured from the same fictional source on e59c5b4, before fixing option lookup.
    assert entities.surveys[0]["survey_id"] == "SV_LOOP"
    assert entities.questions[0]["question_id"] == "2444a60997a47ba0052fcada76afe30f94dca98724a0016d287fe1d5c79d71ef"
    assert entities.responses[0]["response_id"] == "d8f5dde8abbeb6013717efdd743c33d8bf78b4af833a3e947c0e060306571117"
    assert [field["question_field_id"] for field in entities.question_fields] == [
        "717e352ea5fc796fb7b41a8d58f544016ab7094d009adc076d0fc775dd9e7e2d",
        "8ffe8932005158c64a475489ae360086c14bc6c59df61c55169ef632f0bb154b",
        "e7c763233182b75c7293110ea28fe986a9740ed169319990dad432ad12b4641f",
    ]
    assert [answer["response_answer_id"] for answer in entities.response_answers] == [
        "36b59d2a3eecf18fb2330cc21f2cad720568e70f59b11822fe1438d8e1bee174",
        "201154f6ad188e686bf0c77d180eb2df19cb518a19d0d4260e6f5ea02d8a674c",
        "b39855be2ab049420b473173b0e81d31dff651987f0d833c5f38989638e8ea81",
    ]
    assert [field["source_field_suffix"] for field in entities.question_fields] == ["2__1", "1__2", "1__1"]
    assert [field["field_text"] for field in entities.question_fields] == ["Fast", "Safe", "Fast"]
    assert (
        entities.question_catalog[0]["question_catalog_id"]
        == "dcadf33bd354d1b25b7cae7fd885aa64a9622fd1a00c1d1e15106235b0b396e4"
    )
    assert [field["question_field_catalog_id"] for field in entities.question_fields] == [
        "ae59cfd99bb40fdcde7f533451664739004d06d166b47cd5d9bdac66251a3bd0",
        "bfd3af22dcc8e9aa558b86cff39ed2a8fc2895948e2dd8d6e35a0e55963b9989",
        "ae59cfd99bb40fdcde7f533451664739004d06d166b47cd5d9bdac66251a3bd0",
    ]
    # Corrected ordering has the same normalized option content in this fixture.
    content = json.loads(entities.question_catalog[0]["normalized_question_content"])
    assert content["answers"] == ["fast", "fast", "safe"]


def test_corrected_loop_option_changes_catalog_content_when_selected_domain_changes(looped_answer_files):
    source, definition = looped_answer_files
    with source.open(newline="") as handle:
        rows = list(csv.reader(handle))
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows([row[:2] for row in rows])
    entities = parse_survey(source, definition)
    assert (
        entities.question_fields[0]["question_field_id"]
        == "717e352ea5fc796fb7b41a8d58f544016ab7094d009adc076d0fc775dd9e7e2d"
    )
    assert (
        entities.response_answers[0]["response_answer_id"]
        == "36b59d2a3eecf18fb2330cc21f2cad720568e70f59b11822fe1438d8e1bee174"
    )
    assert entities.response_answers[0]["raw_value"] == "Selected"
    # The old domain contained only Safe. Correcting it to Fast changes content,
    # hence these catalog IDs, while both identity algorithms remain unchanged.
    assert (
        entities.question_catalog[0]["question_catalog_id"]
        == "67efe1e0a6d441fa3ff9a928ca2322feb37d04d528e40f912b32183cc34aaee8"
    )
    assert json.loads(entities.question_catalog[0]["normalized_question_content"]) == {
        "answers": ["fast"],
        "role": "response",
        "text": "features",
        "type": "multiple_choice_multiple",
        "structure": {
            "definition": {"Choices": [["fast"], ["safe"]]},
            "fields": [{"role": "answer", "text": "fast", "value_type": "categorical"}],
        },
    }
    assert (
        entities.question_field_catalog[0]["question_field_catalog_id"]
        == "5722f167a3b4b8a358ddf85f5302d1118eadcbad58e62968c37ff1e7701bd867"
    )
    assert json.loads(entities.question_field_catalog[0]["normalized_field_content"]) == {
        "role": "answer",
        "text": "fast",
        "value_type": "categorical",
    }


def test_invalid_native_choice_does_not_fall_back_to_loop_iteration(looped_answer_files):
    source, definition = looped_answer_files
    with source.open(newline="") as handle:
        rows = list(csv.reader(handle))
    rows[0][1] = "2_QID1_9"
    rows[2][1] = json.dumps({"ImportId": "2_QID1_9"})
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    entities = parse_survey(source, definition)
    assert entities.question_fields[0]["choice_external_id"] is None
    assert entities.response_answers[0]["answer_option_id"] is None
    assert entities.response_answers[0]["raw_value"] == "Selected"


def test_metadata_associated_legacy_columns_keep_choice_and_matrix_answer_mapping(definition_answer_files):
    source, definition = definition_answer_files
    with source.open(newline="") as handle:
        rows = list(csv.reader(handle))
    rows[2][2] = json.dumps({"ImportId": "legacy_1", "questionId": "QID2"})
    rows[2][5] = json.dumps({"ImportId": "legacy_1_3", "questionId": "QID3"})
    rows[3][5] = "Selected"
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qsf = json.loads(definition.read_text())
    matrix = next(item["Payload"] for item in qsf["SurveyElements"] if item.get("PrimaryAttribute") == "QID3")
    matrix["SubSelector"] = "MultipleAnswer"
    definition.write_text(json.dumps(qsf))
    entities = parse_survey(source, definition)
    fields = {field["field_external_id"]: field for field in entities.question_fields}
    assert fields["one"]["choice_external_id"] == fields["matrix_one"]["choice_external_id"] == "1"
    answers = {answer["field_external_id"]: answer for answer in entities.response_answers}
    options = {option["answer_option_id"]: option for option in entities.answer_options}
    assert options[answers["one"]["answer_option_id"]]["source_choice_id"] == "1"
    assert options[answers["matrix_one"]["answer_option_id"]]["source_choice_id"] == "3"


@pytest.mark.parametrize("key", ["choiceId", "ChoiceId", "choiceID"])
def test_valid_zero_choice_metadata_precedes_loop_suffix(looped_answer_files, key):
    source, definition = looped_answer_files
    with source.open(newline="") as handle:
        rows = list(csv.reader(handle))
    rows[2][1] = json.dumps({"ImportId": "2_QID1_1", key: 0})
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qsf = json.loads(definition.read_text())
    qsf["Questions"]["QID1"]["Choices"]["0"] = {"Display": "Other"}
    definition.write_text(json.dumps(qsf))
    entities = parse_survey(source, definition)
    assert entities.question_fields[0]["choice_external_id"] == "0"
    option = next(
        option
        for option in entities.answer_options
        if option["answer_option_id"] == entities.response_answers[0]["answer_option_id"]
    )
    assert option["source_choice_id"] == "0"


@pytest.mark.parametrize("key", ["answerId", "AnswerId", "answerID"])
def test_valid_zero_matrix_answer_metadata_precedes_loop_suffix(looped_answer_files, key):
    source, definition = looped_answer_files
    with source.open(newline="") as handle:
        rows = list(csv.reader(handle))
    rows[2][1] = json.dumps({"ImportId": "2_QID1_1_1", key: 0})
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows(rows)
    qsf = json.loads(definition.read_text())
    qsf["Questions"]["QID1"].update({
        "QuestionType": "Matrix",
        "Selector": "Likert",
        "SubSelector": "MultipleAnswer",
        "Answers": {"0": {"Display": "No"}, "1": {"Display": "Yes"}},
    })
    definition.write_text(json.dumps(qsf))
    entities = parse_survey(source, definition)
    option = next(
        option
        for option in entities.answer_options
        if option["answer_option_id"] == entities.response_answers[0]["answer_option_id"]
    )
    assert option["source_choice_id"] == "0"
