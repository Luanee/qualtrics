"""Generate a fictional team survey and response report with explainable routing."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from qualtrics import parse_survey, render_report

SURVEY_ID = "SV_SYNTHETIC_FLOW"


def _choice(question_id: str, text: str, choices: list[str]) -> dict[str, Any]:
    return {
        "QuestionID": question_id,
        "QuestionText": text,
        "QuestionDescription": text,
        "QuestionType": "MC",
        "Selector": "SAVR",
        "SubSelector": "TX",
        "Choices": {str(index): {"Display": choice} for index, choice in enumerate(choices, 1)},
        "ChoiceOrder": list(range(1, len(choices) + 1)),
        "DataExportTag": question_id,
    }


def _branch(question_id: str, choice_id: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "Type": "Branch",
        "BranchLogic": {
            "Type": "BooleanExpression",
            "0": {
                "Type": "If",
                "0": {
                    "Type": "Expression",
                    "LogicType": "Question",
                    "QuestionID": question_id,
                    "ChoiceLocator": f"q://{question_id}/SelectableChoice/{choice_id}",
                    "Operator": "Selected",
                },
            },
        },
        "Flow": children,
    }


def survey_definition() -> dict[str, Any]:
    """Return a deterministic QSF fixture; this is not a live survey export."""
    questions = [
        {
            "QuestionID": "QID_INTRO",
            "QuestionText": "Welcome to our fictional team survey",
            "QuestionType": "DB",
            "Selector": "TB",
        },
        _choice("QID1", "Which department do you work in?", ["Sales", "Engineering", "Prefer not to say"]),
        _choice("QID2", "Which sales task needs more support?", ["Finding leads", "Preparing proposals", "Follow-up"]),
        _choice("QID3", "Which engineering task needs more support?", ["Planning", "Code review", "Testing"]),
        _choice("QID4", "How useful is concept A?", ["Very useful", "Somewhat useful", "Not useful"]),
        _choice("QID5", "How useful is concept B?", ["Very useful", "Somewhat useful", "Not useful"]),
        _choice("QID6", "Would you like a follow-up conversation?", ["Yes", "No"]),
    ]
    block_specs = [
        ("BL_WELCOME", "Welcome and department", ["QID_INTRO", "QID1"]),
        ("BL_SALES", "Sales follow-up", ["QID2"]),
        ("BL_ENGINEERING", "Engineering follow-up", ["QID3"]),
        ("BL_CONCEPT_A", "Concept A", ["QID4"]),
        ("BL_CONCEPT_B", "Concept B", ["QID5"]),
        ("BL_CLOSE", "Keep in touch", ["QID6"]),
    ]
    blocks = {
        block_id: {
            "ID": block_id,
            "Type": "Standard",
            "Description": name,
            "BlockElements": [{"Type": "Question", "QuestionID": qid} for qid in qids],
        }
        for block_id, name, qids in block_specs
    }
    flow = {
        "Type": "Root",
        "Flow": [
            {"Type": "Block", "ID": "BL_WELCOME"},
            _branch("QID1", "3", [{"Type": "EndSurvey", "EndingType": "Default"}]),
            _branch(
                "QID1",
                "1",
                [
                    {"Type": "EmbeddedData", "EmbeddedData": [{"Field": "Team", "Value": "Sales", "Type": "Custom"}]},
                    {"Type": "Block", "ID": "BL_SALES"},
                ],
            ),
            _branch(
                "QID1",
                "2",
                [
                    {
                        "Type": "EmbeddedData",
                        "EmbeddedData": [{"Field": "Team", "Value": "Engineering", "Type": "Custom"}],
                    },
                    {"Type": "Block", "ID": "BL_ENGINEERING"},
                ],
            ),
            {
                "Type": "BlockRandomizer",
                "SubSet": 1,
                "EvenPresentation": True,
                "Flow": [
                    {
                        "Type": "Group",
                        "Description": "Try concept A",
                        "Flow": [
                            {"Type": "Block", "ID": "BL_CONCEPT_A"},
                        ],
                    },
                    {
                        "Type": "Group",
                        "Description": "Try concept B",
                        "Flow": [
                            {"Type": "Block", "ID": "BL_CONCEPT_B"},
                        ],
                    },
                ],
            },
            {"Type": "Block", "ID": "BL_CLOSE"},
            _branch("QID6", "1", [{"Type": "WebService", "Description": "Request a follow-up conversation"}]),
            {"Type": "EndSurvey", "EndingType": "Default"},
        ],
    }
    next_id = 0

    def assign_ids(node: dict[str, Any]) -> None:
        nonlocal next_id
        next_id += 1
        node["FlowID"] = f"FL_{next_id}"
        for child in node.get("Flow", []):
            assign_ids(child)

    assign_ids(flow)
    return {
        "SurveyEntry": {
            "SurveyID": SURVEY_ID,
            "SurveyName": "Team journey · fictional flow example",
            "SurveyLanguage": "EN",
            "SurveyStatus": "Inactive",
            "SurveyDescription": "Synthetic routing illustration, not import-tested in Qualtrics.",
        },
        "SurveyElements": [
            *(
                {"Element": "SQ", "PrimaryAttribute": question["QuestionID"], "Payload": question}
                for question in questions
            ),
            {"Element": "BL", "Payload": blocks},
            {"Element": "FL", "Payload": flow},
        ],
    }


def build_showcase(output_dir: Path) -> dict[str, Path]:
    """Render through the public toolkit with 24 internally consistent fake responses."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        key: output_dir / filename
        for key, filename in {
            "survey": "survey.qsf",
            "flow": "flow.json",
            "responses": "responses.csv",
            "report": "report.html",
        }.items()
    }
    definition = survey_definition()
    paths["survey"].write_text(json.dumps(definition, ensure_ascii=False, indent=2), encoding="utf-8")
    flow = next(element["Payload"] for element in definition["SurveyElements"] if element["Element"] == "FL")
    paths["flow"].write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")
    questions = [
        element["Payload"]
        for element in definition["SurveyElements"]
        if element["Element"] == "SQ" and element["Payload"]["QuestionType"] != "DB"
    ]
    metadata = ["ResponseId", "RecordedDate", "Finished", "Progress"]
    with paths["responses"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        columns = metadata + [question["QuestionID"] for question in questions]
        writer.writerow(columns)
        writer.writerow(metadata + [question["QuestionText"] for question in questions])
        writer.writerow([json.dumps({"ImportId": column}) for column in columns])
        for index in range(24):
            department = index % 3
            early_end = department == 2
            recorded = datetime(2026, 1, 10, 9) + timedelta(days=index * 10)
            writer.writerow([
                f"R_FLOW_FAKE_{index + 1:02d}",
                recorded.isoformat(sep=" "),
                "True",
                "100",
                ("Sales", "Engineering", "Prefer not to say")[department],
                "Preparing proposals" if department == 0 else "",
                "Code review" if department == 1 else "",
                "Very useful" if not early_end and index % 2 == 0 else "",
                "Somewhat useful" if not early_end and index % 2 == 1 else "",
                ("Yes" if index % 4 == 0 else "No") if not early_end else "",
            ])
    entities = parse_survey(paths["responses"], paths["survey"])
    render_report(entities, paths["report"])
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/survey-flow-showcase"))
    for path in build_showcase(parser.parse_args().output).values():
        print(path)


if __name__ == "__main__":
    main()
