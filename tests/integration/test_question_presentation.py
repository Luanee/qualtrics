from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from qualtrics import load_entities, parse_survey, write_entities
from qualtrics.models import EntitySet
from qualtrics.reporting import render_report


def _entities(question_type: str, selector: str = "") -> EntitySet:
    return EntitySet(
        surveys=[{"survey_id": "SV_TEST", "survey_name": "Survey"}],
        questions=[
            {
                "survey_id": "SV_TEST",
                "question_id": "Q1",
                "question_external_id": "QID1",
                "question_text": "A question",
                "question_type": question_type,
                "selector": selector,
                "question_role": "response",
            }
        ],
        responses=[{"survey_id": "SV_TEST", "response_id": f"R{i}"} for i in range(1, 5)],
    )


def _field(entities: EntitySet, field_id: str, label: str, value_type: str) -> None:
    entities.question_fields.append({
        "survey_id": "SV_TEST",
        "question_id": "Q1",
        "field_id": field_id,
        "field_text": label,
        "answer_value_type": value_type,
    })


def _answer(entities: EntitySet, response: int, field: str, value: str, option: str | None = None) -> None:
    entities.response_answers.append({
        "survey_id": "SV_TEST",
        "question_id": "Q1",
        "response_id": f"R{response}",
        "field_id": field,
        "answer_text": value,
        "answer_option_id": option,
    })


def _option(entities: EntitySet, field: str, code: str, label: str, order: int) -> None:
    entities.answer_options.append({
        "survey_id": "SV_TEST",
        "question_id": "Q1",
        "field_id": field,
        "answer_option_id": f"{field}:{code}",
        "answer_id": code,
        "answer_code": code,
        "answer_text": label,
        "answer_order": order,
    })


def _section(entities: EntitySet, tmp_path: Path) -> str:
    output = tmp_path / "report.html"
    render_report(entities, output)
    return output.read_text().split("data-question='QID1'>", 1)[1].split("</details>", 1)[0]


def test_matrix_compares_ordered_options_with_each_rows_answered_denominator(tmp_path: Path) -> None:
    entities = _entities("Matrix", "Likert")
    entities.questions[0]["answer_value_type"] = "categorical"
    for field, label in (("delivery", "Delivery"), ("support", "Support"), ("unused", "Unused")):
        _field(entities, field, label, "categorical")
        for code, text, order in (("1", "Bad", 2), ("2", "Neutral", 3), ("3", "Good", 1)):
            _option(entities, field, code, text, order)
    _answer(entities, 1, "delivery", "3")
    _answer(entities, 2, "delivery", "1")
    _answer(entities, 1, "support", "Good")

    section = _section(entities, tmp_path)

    assert "class='matrix-summary'" in section
    assert section.index(">Good</span>") < section.index(">Bad</span>") < section.index(">Neutral</span>")
    delivery = section.split("<th scope='row'>Delivery</th>")[1].split("</tr>")[0]
    support = section.split("<th scope='row'>Support</th>")[1].split("</tr>")[0]
    unused = section.split("<th scope='row'>Unused</th>")[1].split("</tr>")[0]
    assert delivery.count("<b>1</b><small>50%</small>") == 2
    assert "<b>1</b><small>100%</small>" in support
    assert unused.count("<b>0</b><small>—</small>") == 3
    assert "option-zero" in delivery
    assert "respondents who answered that row" in section
    assert "does not tell us whether the question was shown" in section


def test_multiple_choice_deduplicates_selections_and_explains_percentages(tmp_path: Path) -> None:
    entities = _entities("MC", "MAVR")
    _field(entities, "choice", "Choice", "categorical")
    for code, text, order in (("1", "First", 1), ("3", "Unused", 3), ("2", "Second", 2)):
        _option(entities, "choice", code, text, order)
    _answer(entities, 1, "choice", "First", "choice:1")
    _answer(entities, 1, "choice", "1")
    _answer(entities, 1, "choice", "2")
    _answer(entities, 2, "choice", "2")

    section = _section(entities, tmp_path)

    assert "<b>3</b> selections" in section
    assert "<b>1</b><small>50%</small>" in section
    assert "<b>2</b><small>100%</small>" in section
    assert "<b>0</b><small>0%</small>" in section
    assert section.index(">Second</span>") < section.index(">Unused</span>")
    assert "2 respondents who answered this question" in section
    assert "Percentages can add up to more than 100%" in section


@pytest.mark.parametrize("question_type,selector", [("Slider", ""), ("Matrix", "CS"), ("MC", "NPS"), ("TE", "SL")])
def test_declared_numeric_fields_include_median_and_sample_standard_deviation(
    tmp_path: Path, question_type: str, selector: str
) -> None:
    entities = _entities(question_type, selector)
    _field(entities, "score", "Score", "numeric")
    for response, value in enumerate(("1", "2", "3", "7"), 1):
        _answer(entities, response, "score", value)

    section = _section(entities, tmp_path)

    assert "<b>1</b> Minimum" in section
    assert "<b>3.25</b> Average" in section
    assert "<b>2.5</b> Median" in section
    assert "<b>7</b> Maximum" in section
    assert "<b>2.63</b> Standard deviation" in section
    assert "Sample standard deviation" in section


def test_numeric_looking_text_identifiers_are_not_averaged(tmp_path: Path) -> None:
    entities = _entities("TE", "SL")
    _field(entities, "employee", "Employee number", "text")
    _answer(entities, 1, "employee", "000123")
    _answer(entities, 2, "employee", "000456")

    section = _section(entities, tmp_path)

    assert "numeric-summary" not in section
    assert ">000123</span>" in section
    assert ">000456</span>" in section


def test_numeric_summary_excludes_nonfinite_values_and_handles_an_empty_field(tmp_path: Path) -> None:
    entities = _entities("Slider")
    _field(entities, "score", "Score", "numeric")
    _field(entities, "empty", "Empty score", "numeric")
    for response, value in enumerate(("NaN", "inf", "-inf", "5"), 1):
        _answer(entities, response, "score", value)

    section = _section(entities, tmp_path)

    assert "<b>5</b> Median" in section
    assert "<b>—</b> Standard deviation" in section
    assert "3 non-numeric or non-finite values excluded" in section
    assert "<h4>Empty score</h4><p class='meta'>No numeric values observed.</p>" in section


def test_matrix_content_is_escaped(tmp_path: Path) -> None:
    entities = _entities("Matrix", "Likert")
    entities.questions[0]["answer_value_type"] = "categorical"
    _field(entities, "row", "<img src=x onerror=alert(1)>", "categorical")
    _option(entities, "row", "1", "<script>alert(1)</script>", 1)
    _answer(entities, 1, "row", "1")

    section = _section(entities, tmp_path)

    assert "<th scope='row'>&lt;img src=x onerror=alert(1)&gt;</th>" in section
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in section
    assert "<script>" not in section


def test_choice_aliases_do_not_match_another_fields_domain(tmp_path: Path) -> None:
    entities = _entities("MC", "MAVR")
    _field(entities, "first", "First", "categorical")
    _field(entities, "second", "Second", "categorical")
    _option(entities, "first", "1", "First option", 1)
    _option(entities, "second", "2", "Other field option", 2)
    _answer(entities, 1, "first", "2")

    section = _section(entities, tmp_path)

    other = section.split("title='Other field option'>")[1].split("</div><b>")[1]
    assert other.startswith("0</b><small>0%</small>")
    assert ">2</span>" in section


def test_ambiguous_choice_aliases_remain_raw(tmp_path: Path) -> None:
    entities = _entities("MC", "SAVR")
    _field(entities, "choice", "Choice", "categorical")
    _option(entities, "choice", "1", "One", 1)
    _option(entities, "choice", "2", "Two", 2)
    entities.answer_options[1]["answer_code"] = "1"
    _answer(entities, 1, "choice", "1")

    section = _section(entities, tmp_path)

    assert section.count("<b>0</b><small>0%</small>") == 2
    assert ">1</span>" in section


def test_multiple_answer_matrix_groups_cells_by_statement_and_counts_respondents(tmp_path: Path) -> None:
    entities = _entities("Matrix", "Likert")
    entities.questions[0]["sub_selector"] = "MultipleAnswer"
    for field, statement, code, label in (
        ("delivery_good", "Delivery", "3", "Good"),
        ("delivery_bad", "Delivery", "1", "Bad"),
        ("support_good", "Support", "3", "Good"),
    ):
        _field(entities, field, statement, "categorical")
        entities.question_fields[-1]["choice_external_id"] = statement
        _option(entities, field, code, label, int(code))
        _answer(entities, 1, field, "Selected", f"{field}:{code}")
    _answer(entities, 1, "delivery_good", "Selected", "delivery_good:3")
    _answer(entities, 2, "support_good", "Selected", "support_good:3")

    section = _section(entities, tmp_path)

    assert section.count("<th scope='row'>Delivery</th>") == 1
    delivery = section.split("<th scope='row'>Delivery</th>")[1].split("</tr>")[0]
    support = section.split("<th scope='row'>Support</th>")[1].split("</tr>")[0]
    assert "class='matrix-n'>1</td>" in delivery
    assert delivery.count("<b>1</b><small>100%</small>") == 2
    assert "class='matrix-n'>2</td>" in support
    assert "<b>2</b><small>100%</small>" in support
    assert "No exported option for this row" in support


def test_side_by_side_uses_field_types_for_mixed_numeric_and_text_answers(tmp_path: Path) -> None:
    entities = _entities("SBS")
    _field(entities, "count", "Count", "numeric")
    _field(entities, "code", "Code", "text")
    _answer(entities, 1, "count", "4")
    _answer(entities, 1, "code", "004")

    section = _section(entities, tmp_path)

    assert "<b>4</b> Median" in section
    assert ">004</span>" in section
    assert section.count("class='numeric-summary'") == 1


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_matrix_statement_label_survives_parse_and_saved_entity_roundtrip(tmp_path: Path, format: str) -> None:
    source = tmp_path / "matrix.csv"
    definition = tmp_path / "matrix.qsf"
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1_1_3", "QID1_1_1"],
            ["Response ID", "Service - Delivery - Good", "Service - Delivery - Bad"],
            ["{}", json.dumps({"ImportId": "1_QID1_3"}), json.dumps({"ImportId": "1_QID1_1"})],
            ["R1", "Selected", "Selected"],
        ])
    definition.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_MATRIX", "SurveyName": "Matrix"},
            "SurveyElements": [
                {
                    "Element": "SQ",
                    "Payload": {
                        "QuestionID": "QID1",
                        "QuestionText": "Service",
                        "QuestionType": "Matrix",
                        "Selector": "Likert",
                        "SubSelector": "MultipleAnswer",
                        "Choices": {"1": {"Display": "<b>Delivery</b>"}},
                        "Answers": {"1": {"Display": "Bad"}, "3": {"Display": "Good"}},
                    },
                }
            ],
        })
    )

    parsed = parse_survey(source, definition)
    write_entities(parsed, tmp_path / "entities", format)
    loaded = load_entities(tmp_path / "entities")
    section = _section(loaded, tmp_path)

    assert {field["field_text"] for field in loaded.question_fields} == {"Delivery - Good", "Delivery - Bad"}
    assert {field.get("statement_text") for field in loaded.question_fields} == {"Delivery"}
    assert section.count("<th scope='row'>Delivery</th>") == 1
    assert "<th scope='row'>Delivery - Good</th>" not in section


def test_older_matrix_entities_infer_shared_statement_from_matching_option_suffixes(tmp_path: Path) -> None:
    entities = _entities("Matrix", "Likert")
    entities.questions[0]["sub_selector"] = "MultipleAnswer"
    for field, code, label in (("good", "3", "Good"), ("bad", "1", "Bad")):
        _field(entities, field, f"Delivery - {label}", "categorical")
        entities.question_fields[-1]["choice_external_id"] = "1"
        _option(entities, field, code, label, int(code))
        _answer(entities, 1, field, "Selected", f"{field}:{code}")

    section = _section(entities, tmp_path)

    assert section.count("<th scope='row'>Delivery</th>") == 1
