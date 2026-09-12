import csv
import json
import sqlite3
from pathlib import Path

import pytest
from typer import BadParameter
from typer.testing import CliRunner

from qualtrics import parse_survey, write_entities
from qualtrics.cli.app import app
from qualtrics.cli.entity_folders import validate_entity_collection


@pytest.fixture
def comment_source(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "comments.csv"
    definition = tmp_path / "comments.qsf"
    columns = ["ResponseId", "UserLanguage", "QID1", "QID2"]
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            columns,
            ["Response ID", "Language", "Your feedback", "Satisfied?"],
            [json.dumps({"ImportId": column}) for column in columns],
            ["R_DE", "DE", "  Grüße, bitte schneller.  ", "Yes"],
            ["R_UNKNOWN", "", "00123", "No"],
        ])
    definition.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_COMMENTS", "SurveyName": "Comments", "SurveyLanguage": "EN"},
            "SurveyElements": [
                {
                    "Element": "SQ",
                    "PrimaryAttribute": "QID1",
                    "Payload": {"QuestionID": "QID1", "QuestionText": "Your feedback", "QuestionType": "TE"},
                },
                {
                    "Element": "SQ",
                    "PrimaryAttribute": "QID2",
                    "Payload": {
                        "QuestionID": "QID2",
                        "QuestionText": "Satisfied?",
                        "QuestionType": "MC",
                        "Selector": "SAVR",
                        "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                    },
                },
            ],
        }),
        encoding="utf-8",
    )
    return source, definition


def test_build_and_sqlite_cli_export_comments_with_response_language(
    tmp_path: Path, comment_source: tuple[Path, Path]
) -> None:
    source, definition = comment_source
    entities = tmp_path / "entities"
    built = CliRunner().invoke(app, ["build", str(source), "--qsf", str(definition), "-o", str(entities)])
    assert built.exit_code == 0, built.output
    assert (entities / "comments.json").is_file()
    comments = json.loads((entities / "comments.json").read_text())
    assert [(row["answer_text"], row["raw_value"], row["user_language"]) for row in comments] == [
        ("  Grüße, bitte schneller.  ", "  Grüße, bitte schneller.  ", "DE"),
        ("00123", "00123", None),
    ]
    assert len(list(entities.glob("*.json"))) == 10
    answers = json.loads((entities / "response_answers.json").read_text())
    assert len(answers) == 4
    output = tmp_path / "power-bi"
    result = CliRunner().invoke(
        app, ["semantic-model", "build", str(entities), "-o", str(output), "--format", "sqlite"]
    )
    assert result.exit_code == 0, result.output
    with sqlite3.connect(output / "semantic_model.sqlite") as connection:
        assert connection.execute("SELECT count(*) FROM fact_response_answers").fetchone() == (4,)
        assert connection.execute(
            "SELECT answer_text, user_language FROM fact_comments ORDER BY answer_text"
        ).fetchall() == [
            ("  Grüße, bitte schneller.  ", "DE"),
            ("00123", None),
        ]


def test_legacy_nine_table_folder_combines_and_exports_comments(
    tmp_path: Path, comment_source: tuple[Path, Path]
) -> None:
    source = tmp_path / "legacy"
    write_entities(parse_survey(*comment_source), source)
    (source / "comments.json").unlink(missing_ok=True)
    output = tmp_path / "combined"
    result = CliRunner().invoke(app, ["entities", "combine", str(source), "-o", str(output), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert (output / "comments.json").is_file()
    assert len(json.loads((output / "comments.json").read_text())) == 2
    semantic = CliRunner().invoke(
        app, ["semantic-model", "build", str(source), "-o", str(tmp_path / "model"), "--format", "json"]
    )
    assert semantic.exit_code == 0, semantic.output
    assert (tmp_path / "model" / "fact_comments.json").is_file()


def test_optional_comment_files_still_reject_ambiguous_formats(
    tmp_path: Path, comment_source: tuple[Path, Path]
) -> None:
    source = tmp_path / "entities"
    write_entities(parse_survey(*comment_source), source)
    (source / "comments.json").write_text("[]")
    (source / "comments.csv").write_text("response_answer_id\n")
    with pytest.raises(BadParameter, match="multiple formats"):
        validate_entity_collection(source)
