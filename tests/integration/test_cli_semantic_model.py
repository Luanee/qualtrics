import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qualtrics import parse_survey, write_entities
from qualtrics._common.models.semantic import SEMANTIC_TABLE_NAMES
from qualtrics.cli.app import app


def test_semantic_model_cli_writes_five_json_tables(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    source = tmp_path / "entities"
    output = tmp_path / "semantic"
    write_entities(parse_survey(*survey_files), source, "json")
    result = CliRunner().invoke(
        app,
        ["semantic-model", "build", str(source), "--output", str(output), "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    assert {path.name for path in output.glob("*.json")} == {
        "fact_responses.json",
        "fact_response_answers.json",
        "dim_surveys.json",
        "dim_questions.json",
        "dim_answer_options.json",
    }


def test_semantic_model_cli_rejects_tables_in_another_format(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    source = tmp_path / "entities"
    output = tmp_path / "semantic"
    write_entities(parse_survey(*survey_files), source, "json")
    output.mkdir()
    (output / "fact_responses.json").write_text("[]", encoding="utf-8")
    result = CliRunner().invoke(app, ["semantic-model", "build", str(source), "--output", str(output)])
    assert result.exit_code != 0
    assert "already contains semantic tables" in result.output


def test_semantic_parquet_has_columns_for_empty_tables(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    import pyarrow.parquet as pq

    source = tmp_path / "entities"
    output = tmp_path / "semantic"
    write_entities(parse_survey(*survey_files), source, "json")
    result = CliRunner().invoke(app, ["semantic-model", "build", str(source), "--output", str(output)])
    assert result.exit_code == 0, result.output
    for name in SEMANTIC_TABLE_NAMES:
        assert pq.read_schema(output / f"{name}.parquet").names


def test_semantic_model_cli_writes_one_sqlite_database(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    source = tmp_path / "entities"
    output = tmp_path / "semantic"
    write_entities(parse_survey(*survey_files), source, "json")

    result = CliRunner().invoke(
        app, ["semantic-model", "build", str(source), "--output", str(output), "--format", "sqlite"]
    )

    assert result.exit_code == 0, result.output
    assert [path.name for path in output.iterdir()] == ["semantic_model.sqlite"]
    assert str(output / "semantic_model.sqlite") in result.output
    with sqlite3.connect(output / "semantic_model.sqlite") as connection:
        assert connection.execute("SELECT count(*) FROM fact_responses").fetchone() == (2,)
        # Two responses each answer ten main questions and six practice questions;
        # browser columns are response metadata, not answer rows.
        assert connection.execute("SELECT count(*) FROM fact_response_answers").fetchone() == (32,)
        assert connection.execute("SELECT count(*) FROM dim_surveys").fetchone() == (1,)


@pytest.mark.parametrize("format", ["sqlite", "json", "csv", "parquet"])
def test_semantic_model_cli_rejects_existing_sqlite_database(
    tmp_path: Path, survey_files: tuple[Path, Path], format: str
) -> None:
    source = tmp_path / "entities"
    output = tmp_path / "semantic"
    write_entities(parse_survey(*survey_files), source, "json")
    output.mkdir()
    database = output / "semantic_model.sqlite"
    database.write_bytes(b"existing export")

    result = CliRunner().invoke(
        app, ["semantic-model", "build", str(source), "--output", str(output), "--format", format]
    )

    assert result.exit_code != 0
    assert "already contains semantic tables" in result.output
    assert database.read_bytes() == b"existing export"
    assert list(output.iterdir()) == [database]
