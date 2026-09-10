from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from qualtrics import load_entities, parse_survey, write_entities
from qualtrics._common.models.entity_set import merge_entity_sets
from qualtrics._common.models.semantic import build_semantic_model
from qualtrics._common.serialization.semantic import write_semantic_model


def _survey_files(tmp_path: Path, *, include_flow: bool = True) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "flow.csv"
    qsf_path = tmp_path / "flow.qsf"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1"],
            ["Response ID", "Exported question"],
            ["{}", json.dumps({"ImportId": "QID1"})],
            ["R_1", "Sales"],
        ])
    elements: list[dict[str, object]] = [
        {
            "Element": "SQ",
            "PrimaryAttribute": "QID1",
            "Payload": {
                "QuestionID": "QID1",
                "QuestionText": "Department",
                "QuestionType": "MC",
                "Selector": "SAVR",
                "Choices": {"1": {"Display": "Sales"}},
            },
        },
        {
            "Element": "SQ",
            "PrimaryAttribute": "QID2",
            "Payload": {"QuestionID": "QID2", "QuestionText": "Definition only", "QuestionType": "TE"},
        },
        {
            "Element": "BL",
            "Payload": {
                "BL_1": {
                    "ID": "BL_1",
                    "Description": "Questions",
                    "Type": "Standard",
                    "BlockElements": [
                        {"Type": "Question", "QuestionID": "QID1"},
                        {"Type": "Question", "QuestionID": "QID2"},
                    ],
                }
            },
        },
    ]
    if include_flow:
        elements.append({
            "Element": "FL",
            "Payload": {"Type": "Root", "FlowID": "FL_1", "Flow": [{"Type": "Block", "ID": "BL_1"}]},
        })
    qsf_path.write_text(
        json.dumps({"SurveyEntry": {"SurveyID": "SV_FLOW", "SurveyName": "Flow"}, "SurveyElements": elements}),
        encoding="utf-8",
    )
    return csv_path, qsf_path


def test_parse_stores_optional_flow_as_json_scalar_and_keeps_definition_only_question(tmp_path: Path) -> None:
    entities = parse_survey(*_survey_files(tmp_path))
    scalar = entities.surveys[0]["flow_definition_json"]
    definition = json.loads(scalar)

    assert isinstance(scalar, str)
    assert definition["questions"]["QID2"]["text"] == "Definition only"
    assert {question["question_external_id"] for question in entities.questions} == {"QID1"}


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_flow_scalar_round_trips_entity_formats(tmp_path: Path, format: str) -> None:
    entities = parse_survey(*_survey_files(tmp_path / "input"))
    destination = tmp_path / format
    write_entities(entities, destination, format)

    loaded = load_entities(destination)
    assert loaded.surveys[0]["flow_definition_json"] == entities.surveys[0]["flow_definition_json"]


def test_flow_scalar_reaches_semantic_sqlite(tmp_path: Path) -> None:
    entities = parse_survey(*_survey_files(tmp_path / "input"))
    destination = tmp_path / "semantic"
    destination.mkdir()
    write_semantic_model(build_semantic_model(entities), destination, "sqlite")

    with sqlite3.connect(destination / "semantic_model.sqlite") as connection:
        value = connection.execute("SELECT flow_definition_json FROM dim_surveys").fetchone()[0]
    assert value == entities.surveys[0]["flow_definition_json"]


def test_legacy_absent_flow_remains_absent_when_combined_with_flow_survey(tmp_path: Path) -> None:
    with_flow = parse_survey(*_survey_files(tmp_path / "new"))
    legacy_csv, legacy_qsf = _survey_files(tmp_path / "legacy", include_flow=False)
    legacy = parse_survey(legacy_csv, legacy_qsf, survey_id="SV_LEGACY")

    combined = merge_entity_sets([with_flow, legacy])
    surveys = {row["survey_id"]: row for row in combined.surveys}
    assert "flow_definition_json" in surveys["SV_FLOW"]
    assert "flow_definition_json" not in surveys["SV_LEGACY"]


def test_explicit_flow_file_is_used_with_definition_metadata(tmp_path: Path) -> None:
    csv_path, qsf_path = _survey_files(tmp_path / "input", include_flow=False)
    flow_path = tmp_path / "flow.json"
    flow_path.write_text(json.dumps({"result": {"Flow": [{"Type": "Block", "ID": "BL_1"}]}}), encoding="utf-8")

    entities = parse_survey(csv_path, qsf_path, flow_path=flow_path)
    definition = json.loads(entities.surveys[0]["flow_definition_json"])
    assert definition["root"]["children"][0]["config"]["ID"] == "BL_1"
    assert definition["blocks"]["BL_1"]["name"] == "Questions"
    assert definition["questions"]["QID2"]["text"] == "Definition only"


def test_standalone_flow_definition_keeps_its_own_metadata(tmp_path: Path) -> None:
    csv_path, _ = _survey_files(tmp_path / "definition", include_flow=False)
    standalone_csv = tmp_path / "responses.csv"
    standalone_csv.write_bytes(csv_path.read_bytes())
    flow_path = tmp_path / "standalone.json"
    flow_path.write_text(
        json.dumps({
            "Flow": [{"Type": "Block", "ID": "BL_API"}],
            "Blocks": [
                {
                    "ID": "BL_API",
                    "Description": "API questions",
                    "Type": "Standard",
                    "BlockElements": [{"Type": "Question", "QuestionID": "QID_API"}],
                }
            ],
            "Questions": {"QID_API": {"QuestionID": "QID_API", "QuestionText": "API label", "QuestionType": "TE"}},
        }),
        encoding="utf-8",
    )

    entities = parse_survey(standalone_csv, flow_path=flow_path)
    definition = json.loads(entities.surveys[0]["flow_definition_json"])
    assert definition["blocks"]["BL_API"]["name"] == "API questions"
    assert definition["questions"]["QID_API"]["text"] == "API label"


@pytest.mark.parametrize(
    "wrap",
    [
        lambda definition: {"SurveyDefinition": definition},
        lambda definition: {"result": {"SurveyDefinition": definition}},
    ],
)
def test_separate_wrapped_definition_supplies_metadata_for_raw_flow(
    tmp_path: Path, wrap: Callable[[dict[str, object]], dict[str, object]]
) -> None:
    csv_path, qsf_path = _survey_files(tmp_path / "input", include_flow=False)
    definition = json.loads(qsf_path.read_text(encoding="utf-8"))
    elements = definition.pop("SurveyElements")
    questions = {
        str(element["PrimaryAttribute"]): element["Payload"] for element in elements if element["Element"] == "SQ"
    }
    blocks = next(element["Payload"] for element in elements if element["Element"] == "BL")
    wrapped = wrap({"SurveyEntry": definition["SurveyEntry"], "Blocks": blocks, "Questions": questions})
    qsf_path.write_text(json.dumps(wrapped), encoding="utf-8")
    flow_path = tmp_path / "raw-flow.json"
    flow_path.write_text(json.dumps({"Flow": [{"Type": "Block", "ID": "BL_1"}]}), encoding="utf-8")

    entities = parse_survey(csv_path, qsf_path, flow_path=flow_path)
    flow = json.loads(entities.surveys[0]["flow_definition_json"])
    assert flow["blocks"]["BL_1"]["name"] == "Questions"
    assert flow["questions"]["QID2"]["text"] == "Definition only"
