from pathlib import Path

from typer.testing import CliRunner

from qualtrics import parse_survey, write_entities
from qualtrics.cli.app import app
from qualtrics.models.semantic import SEMANTIC_TABLE_NAMES


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
        "dim_question_fields.json",
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
