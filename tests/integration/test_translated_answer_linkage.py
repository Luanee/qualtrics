from __future__ import annotations

import csv
import json
from pathlib import Path
from zipfile import ZipFile

from qualtrics import parse_survey
from qualtrics._common.models.entity_set import validate_entity_set
from qualtrics._common.models.semantic import build_semantic_model


def test_translated_choice_labels_link_to_base_options_without_changing_raw_facts(tmp_path: Path) -> None:
    csv_path = tmp_path / "responses.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1", "QID2_1", "QID3"],
            ["Response ID", "User language", "Choice", "Matrix row", "Free text"],
            [
                "{}",
                "{}",
                json.dumps({"ImportId": "QID1"}),
                json.dumps({"ImportId": "QID2_1"}),
                json.dumps({"ImportId": "QID3"}),
            ],
            ["R_DE", "DE", "Ja", "Gut", "Ja"],
            ["R_FR", "FR", "Oui", "", ""],
            ["R_EMPTY", "", "Oui", "", ""],
            ["R_UNKNOWN", "ZZ", "Ja", "", ""],
            ["R_AMBIGUOUS", "DE", "Gleich", "", ""],
            ["R_NATIVE", "DE", "2", "2", ""],
            ["R_COLLISION", "DE", "Yes", "", ""],
            ["R_RECODE", "DE", "99", "", ""],
        ])
    qsf_path = tmp_path / "definition.qsf"
    qsf_path.write_text(
        json.dumps({
            "SurveyID": "SV_LINK",
            "SurveyOptions": {"SurveyLanguage": "EN", "AvailableLanguages": {"EN": [], "DE": [], "FR": []}},
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "Choice",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {
                        "1": {"Display": "Yes"},
                        "2": {"Display": "No"},
                        "3": {"Display": "Maybe"},
                        "4": {"Display": "Later"},
                        "5": {"Display": "Unclear"},
                        "6": {"Display": "Special"},
                    },
                    "RecodeValues": {"1": "99"},
                    "Language": {
                        "DE": {
                            "Choices": {
                                "1": {"Display": "Ja"},
                                "2": {"Display": "Nein"},
                                "3": {"Display": "Gleich"},
                                "4": {"Display": "Gleich"},
                                "5": {"Display": "Yes"},
                                "6": {"Display": "99"},
                            }
                        },
                        "FR": {"Choices": {"1": {"Display": "Oui"}}},
                    },
                },
                "QID2": {
                    "QuestionID": "QID2",
                    "QuestionText": "Matrix",
                    "QuestionType": "Matrix",
                    "Selector": "Likert",
                    "Choices": {"1": {"Display": "Row"}},
                    "Answers": {"1": {"Display": "Good"}, "2": {"Display": "Bad"}},
                    "Language": {"DE": {"Answers": {"1": {"Display": "Gut"}, "2": {"Display": "Schlecht"}}}},
                },
                "QID3": {"QuestionID": "QID3", "QuestionText": "Free text", "QuestionType": "TE"},
            },
        }),
        encoding="utf-8",
    )

    entities = parse_survey(csv_path, qsf_path)
    validate_entity_set(entities, strict=True)
    answers = {(row["response_external_id"], row["question_external_id"]): row for row in entities.response_answers}
    base_options = {
        (row["question_external_id"], row["answer_external_id"]): row
        for row in entities.answer_options
        if not row["is_localized"]
    }
    assert len(answers) == 11
    assert answers["R_DE", "QID1"]["answer_option_id"] == base_options["QID1", "1"]["answer_option_id"]
    assert answers["R_FR", "QID1"]["answer_option_id"] == base_options["QID1", "1"]["answer_option_id"]
    assert answers["R_DE", "QID2"]["answer_option_id"] == base_options["QID2", "1"]["answer_option_id"]
    assert answers["R_NATIVE", "QID1"]["answer_option_id"] == base_options["QID1", "2"]["answer_option_id"]
    assert answers["R_NATIVE", "QID2"]["answer_option_id"] == base_options["QID2", "2"]["answer_option_id"]
    assert answers["R_COLLISION", "QID1"]["answer_option_id"] == base_options["QID1", "5"]["answer_option_id"]
    assert answers["R_RECODE", "QID1"]["answer_option_id"] == base_options["QID1", "1"]["answer_option_id"]
    for response_id in ("R_EMPTY", "R_UNKNOWN", "R_AMBIGUOUS"):
        assert answers[response_id, "QID1"]["answer_option_id"] is None
    assert answers["R_DE", "QID3"]["answer_option_id"] is None
    assert answers["R_DE", "QID1"]["answer_text"] == answers["R_DE", "QID1"]["raw_value"] == "Ja"
    assert len(build_semantic_model(entities).fact_response_answers) == 11
    archive = tmp_path / "export.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.write(csv_path, arcname="responses.csv")
    assert parse_survey(archive, qsf_path).response_answers == entities.response_answers
