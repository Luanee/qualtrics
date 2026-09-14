from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from qualtrics import parse_survey
from qualtrics._common.analytics import analyze_entities
from qualtrics.ui.codebook import build_codebook


def test_qsf_only_answerable_fields_are_catalogued_without_becoming_response_metrics(tmp_path: Path) -> None:
    responses = tmp_path / "responses.csv"
    with responses.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1"],
            ["Response ID", "Exported text"],
            ["{}", json.dumps({"ImportId": "QID1"})],
            ["R_1", "hello"],
        ])
    definition = tmp_path / "definition.qsf"
    definition.write_text(
        json.dumps({
            "SurveyID": "SV_DEFINITION",
            "Questions": {
                "QID1": {"QuestionID": "QID1", "QuestionText": "Exported text", "QuestionType": "TE"},
                "QID2": {
                    "QuestionID": "QID2",
                    "QuestionText": "Single choice",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                },
                "QID3": {
                    "QuestionID": "QID3",
                    "QuestionText": "Multiple choice",
                    "QuestionType": "MC",
                    "Selector": "MAVR",
                    "Choices": {"1": {"Display": "A"}, "2": {"Display": "B"}},
                },
                "QID4": {"QuestionID": "QID4", "QuestionText": "Comments", "QuestionType": "TE"},
                "QID5": {"QuestionID": "QID5", "QuestionText": "Introduction", "QuestionType": "DB"},
                "QID6": {
                    "QuestionID": "QID6",
                    "QuestionText": "Matrix",
                    "QuestionType": "Matrix",
                    "Choices": {"1": {"Display": "Row A"}, "2": {"Display": "Row B"}},
                    "Answers": {"1": {"Display": "Poor"}, "2": {"Display": "Good"}},
                },
                "QID7": {"QuestionID": "QID7", "QuestionText": "Slider", "QuestionType": "Slider"},
            },
        }),
        encoding="utf-8",
    )

    entities = parse_survey(responses, definition)
    question_ids = {row["question_id"]: row["question_external_id"] for row in entities.questions}
    fields = Counter(question_ids[row["question_id"]] for row in entities.question_fields)
    options = Counter(question_ids[row["question_id"]] for row in entities.answer_options)

    assert set(question_ids.values()) == {f"QID{number}" for number in range(1, 8)}
    assert fields == {"QID1": 1, "QID2": 1, "QID3": 2, "QID4": 1, "QID6": 2, "QID7": 1}
    assert options == {"QID2": 2, "QID3": 2, "QID6": 4}
    assert all(
        row["source_column_index"] is None and row["import_external_id"] is None
        for row in entities.question_fields
        if row["is_definition_only"]
    )
    assert {row["question_external_id"] for row in entities.questions if row["is_definition_only"]} == {
        f"QID{number}" for number in range(2, 8)
    }
    assert {entry["question_id"] for entry in build_codebook(entities)} >= {"QID2", "QID3", "QID4", "QID6"}
    analysis = analyze_entities(entities)
    assert analysis.survey_question_counts == {"SV_DEFINITION": 1}
    assert analysis.survey_unanswered_counts == {}
    assert len(entities.response_answers) == 1
