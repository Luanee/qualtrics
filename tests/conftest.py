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
        "StartDate",
        "EndDate",
        "Status",
        "IPAddress",
        "Progress",
        "Finished",
        "RecordedDate",
        "RecipientLastName",
        "RecipientFirstName",
        "RecipientEmail",
        "ExternalReference",
        "DistributionChannel",
        "UserLanguage",
        "Duration (in seconds)",
        *(f"{index}_cat" for index in range(1, 11)),
        *(f"{index}_cat_train" for index in range(1, 7)),
        "browser_Browser",
        "browser_Version",
        "browser_Operating System",
        "browser_Resolution",
        "browser_User Agent",
    ]
    headers = [
        "Response ID",
        "Start Date",
        "End Date",
        "Response Type",
        "IP Address",
        "Progress",
        "Finished",
        "Recorded Date",
        "Recipient Last Name",
        "Recipient First Name",
        "Recipient Email",
        "External Data Reference",
        "Distribution Channel",
        "User Language",
        "Duration (in seconds)",
        *(f"https://example.test/cat-{index} - {index}_cat" for index in range(1, 11)),
        *(f"https://example.test/train-{index} - PRACTICE QUESTION" for index in range(1, 7)),
        "Browser Meta Info - Browser",
        "Browser Meta Info - Version",
        "Browser Meta Info - Operating System",
        "Browser Meta Info - Resolution",
        "Browser Meta Info - User Agent",
    ]
    import_ids = [
        *({} for _ in range(15)),
        *({"ImportId": f"{index}_QID18"} for index in range(1, 11)),
        *({"ImportId": f"{index}_QID30"} for index in range(1, 7)),
        {"ImportId": "QID37_BROWSER"},
        {"ImportId": "QID37_VERSION"},
        {"ImportId": "QID37_OS"},
        {"ImportId": "QID37_RESOLUTION"},
        {"ImportId": "QID37_USERAGENT"},
    ]
    answers = [
        [
            "R_1",
            "2026-01-01 10:00:00",
            "2026-01-01 10:00:42",
            "0",
            "192.0.2.1",
            "100",
            "True",
            "2026-01-01 10:00:43",
            "Lovelace",
            "Ada",
            "ada@example.test",
            "EXT_1",
            "anonymous",
            "EN",
            "42",
            *(["Robot"] * 10),
            *(["Robot"] * 6),
            "Chrome",
            "120",
            "TestOS",
            "1920x1080",
            "ExampleAgent/1.0",
        ],
        [
            "R_2",
            "2026-01-02 10:00:00",
            "2026-01-02 10:00:38",
            "0",
            "192.0.2.2",
            "100",
            "True",
            "2026-01-02 10:00:39",
            "Hopper",
            "Grace",
            "grace@example.test",
            "EXT_2",
            "anonymous",
            "EN",
            "38",
            *(["Human"] * 10),
            *(["Human"] * 6),
            "Firefox",
            "121",
            "TestOS",
            "1440x900",
            "ExampleAgent/2.0",
        ],
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
