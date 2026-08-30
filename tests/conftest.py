import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def survey_files(tmp_path: Path) -> tuple[Path, Path]:
    """Create a small, non-sensitive three-row Qualtrics export and matching QSF."""
    csv_path = tmp_path / "sample.csv"
    qsf_path = tmp_path / "sample.qsf"
    columns = [
        "ResponseId",
        "UserLanguage",
        *(f"{index}_cat" for index in range(1, 11)),
        *(f"{index}_cat_train" for index in range(1, 7)),
        "browser_Browser",
        "browser_Version",
        "browser_Operating System",
        "browser_Resolution",
    ]
    headers = [
        "Response ID",
        "User Language",
        *(f"https://example.test/cat-{index} - {index}_cat" for index in range(1, 11)),
        *(f"https://example.test/train-{index} - PRACTICE QUESTION" for index in range(1, 7)),
        "Browser Meta Info - Browser",
        "Browser Meta Info - Version",
        "Browser Meta Info - Operating System",
        "Browser Meta Info - Resolution",
    ]
    import_ids = [
        {},
        {},
        *({"ImportId": f"{index}_QID18"} for index in range(1, 11)),
        *({"ImportId": f"{index}_QID30"} for index in range(1, 7)),
        {"ImportId": "QID37_BROWSER"},
        {"ImportId": "QID37_VERSION"},
        {"ImportId": "QID37_OS"},
        {"ImportId": "QID37_RESOLUTION"},
    ]
    answers = [
        ["R_1", "EN", *(["Robot"] * 10), *(["Robot"] * 6), "Chrome", "120", "TestOS", "1920x1080"],
        ["R_2", "EN", *(["Human"] * 10), *(["Human"] * 6), "Firefox", "121", "TestOS", "1440x900"],
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([columns, headers, [json.dumps(item) for item in import_ids], *answers])

    questions = {
        "QID18": {
            "QuestionID": "QID18",
            "QuestionText": "Cat",
            "QuestionType": "MC",
            "Selector": "SAVR",
        },
        "QID30": {
            "QuestionID": "QID30",
            "QuestionText": "PRACTICE QUESTION",
            "QuestionType": "MC",
            "Selector": "SAVR",
        },
        "QID37": {
            "QuestionID": "QID37",
            "QuestionText": "Browser Meta Info",
            "QuestionType": "Meta",
            "Selector": "Browser",
        },
    }
    blocks = {
        "BL_TRAINING": {
            "ID": "BL_TRAINING",
            "Description": "Training",
            "Type": "Standard",
            "BlockElements": [{"Type": "Question", "QuestionID": "QID30"}],
        },
        "BL_FACES": {
            "ID": "BL_FACES",
            "Description": "Categorize faces",
            "Type": "Standard",
            "BlockElements": [{"Type": "Question", "QuestionID": "QID18"}],
        },
        "BL_INSTRUCTIONS": {
            "ID": "BL_INSTRUCTIONS",
            "Description": "Instructions",
            "Type": "Standard",
            "BlockElements": [{"Type": "Question", "QuestionID": "QID37"}],
        },
    }
    qsf_path.write_text(
        json.dumps({
            "SurveyEntry": {
                "SurveyID": "SV_SAMPLE",
                "SurveyName": "Sample",
                "SurveyLanguage": "EN",
            },
            "SurveyElements": [
                *({"Element": "SQ", "PrimaryAttribute": qid, "Payload": payload} for qid, payload in questions.items()),
                {"Element": "BL", "Payload": blocks},
            ],
        }),
        encoding="utf-8",
    )
    return csv_path, qsf_path
