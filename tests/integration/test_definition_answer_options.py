from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from qualtrics import parse_survey


@pytest.fixture
def definition_answer_files(tmp_path: Path) -> tuple[Path, Path]:
    csv_path = tmp_path / "answers.csv"
    qsf_path = tmp_path / "answers.qsf"
    columns = ["ResponseId", "QID1", "one", "two", "two_TEXT", "matrix_one", "matrix_two", "QID4", "QID5"]
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
    ]
    response = ["R1", "Red", "Fast", "", "because", "Good", "Bad", "free text", "73"]
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
