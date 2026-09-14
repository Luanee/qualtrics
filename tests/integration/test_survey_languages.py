from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from qualtrics import parse_survey
from qualtrics._common.models.entities import EntitySet
from qualtrics._common.serialization.io import write_entities


def test_direct_qsf_registers_available_and_extra_question_languages(tmp_path: Path) -> None:
    responses = tmp_path / "responses.csv"
    with responses.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1"],
            ["Response ID", "How are you?"],
            ["{}", json.dumps({"ImportId": "QID1"})],
            ["R_1", "Good"],
        ])
    definition = tmp_path / "definition.qsf"
    definition.write_text(
        json.dumps({
            "SurveyID": "SV_LANG",
            "SurveyName": "Languages",
            "SurveyOptions": {
                "SurveyLanguage": "EN",
                "AvailableLanguages": {"EN": [], "DE": []},
            },
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "How are you?",
                    "QuestionType": "TE",
                    "Language": {
                        "DE": {"QuestionText": "Wie geht es Ihnen?"},
                        "FR": {"QuestionText": "Comment ça va ?"},
                    },
                }
            },
        }),
        encoding="utf-8",
    )

    entities = parse_survey(responses, definition)

    assert entities.surveys[0]["default_language"] == "EN"
    assert entities.survey_manifests["SV_LANG"]["languages"] == {
        "base_language": "EN",
        "available_languages": ["EN", "DE"],
        "all_languages": ["EN", "DE", "FR"],
    }


@pytest.mark.parametrize(
    ("languages", "message"),
    [
        ("EN", "must be an object"),
        ({"base_language": " ", "available_languages": [], "all_languages": []}, "base_language"),
        ({"base_language": 1, "available_languages": [], "all_languages": []}, "base_language"),
        ({"base_language": "EN", "available_languages": "DE", "all_languages": ["EN"]}, "available_languages"),
        ({"base_language": "EN", "available_languages": [""], "all_languages": ["EN"]}, "available_languages"),
        ({"base_language": "EN", "available_languages": [], "all_languages": ["EN", "EN"]}, "duplicate codes"),
        ({"base_language": "EN", "available_languages": [], "all_languages": ["DE"]}, "codes missing"),
        ({"base_language": "EN", "available_languages": ["FR"], "all_languages": ["EN"]}, "codes missing"),
    ],
)
def test_manifest_rejects_invalid_language_registry(tmp_path: Path, languages: object, message: str) -> None:
    entities = EntitySet(
        surveys=[{"survey_id": "SV_LANG", "survey_name": "Languages"}],
        survey_manifests={
            "SV_LANG": {
                "flow_definition_json": None,
                "source_columns_json": [],
                "languages": languages,
            }
        },
    )

    with pytest.raises(ValueError, match=message):
        write_entities(entities, tmp_path / "entities", "json")


def test_manifest_accepts_unknown_base_language_with_no_translations(tmp_path: Path) -> None:
    entities = EntitySet(
        surveys=[{"survey_id": "SV_LANG", "survey_name": "Languages"}],
        survey_manifests={
            "SV_LANG": {
                "flow_definition_json": None,
                "source_columns_json": [],
                "languages": {"base_language": None, "available_languages": [], "all_languages": []},
            }
        },
    )

    write_entities(entities, tmp_path / "entities", "json")
    assert (tmp_path / "entities" / "manifest.json").exists()
