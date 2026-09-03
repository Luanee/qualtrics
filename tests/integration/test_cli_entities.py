from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from qualtrics import load_entities, parse_survey, write_entities
from qualtrics.cli import app


def test_entities_combine_merges_mixed_formats_as_parquet_by_default(
    tmp_path: Path,
    survey_files: tuple[Path, Path],
) -> None:
    first = parse_survey(*survey_files)
    second = parse_survey(*survey_files, survey_id="SV_SECOND")
    third = parse_survey(*survey_files, survey_id="SV_THIRD")
    second.surveys[0]["survey_name"] = "Second survey"
    third.surveys[0]["survey_name"] = "Third survey"

    json_folder = tmp_path / "json-entities"
    csv_folder = tmp_path / "csv-entities"
    parquet_folder = tmp_path / "parquet-entities"
    output = tmp_path / "combined"
    write_entities(first, json_folder, "json")
    write_entities(second, csv_folder, "csv")
    write_entities(third, parquet_folder, "parquet")

    result = CliRunner().invoke(
        app,
        [
            "entities",
            "combine",
            str(json_folder),
            str(csv_folder),
            str(parquet_folder),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert (output / "surveys.parquet").is_file()
    combined = load_entities(output)
    assert [survey["survey_id"] for survey in combined.surveys] == ["SV_SAMPLE", "SV_SECOND", "SV_THIRD"]
    assert {type(field["is_text_field"]) for field in combined.question_fields} == {bool}

    csv_only_output = tmp_path / "csv-only-combined"
    csv_only_result = CliRunner().invoke(
        app,
        ["entities", "combine", str(csv_folder), "--output", str(csv_only_output)],
    )
    assert csv_only_result.exit_code == 0, csv_only_result.output
    assert {type(field["is_text_field"]) for field in load_entities(csv_only_output).question_fields} == {bool}

    json_output = tmp_path / "combined-json"
    json_result = CliRunner().invoke(
        app,
        [
            "entities",
            "combine",
            str(json_folder),
            str(csv_folder),
            "--output",
            str(json_output),
            "--format",
            "json",
        ],
    )
    assert json_result.exit_code == 0, json_result.output
    assert {type(field["is_text_field"]) for field in load_entities(json_output).question_fields} == {bool}


def test_entities_combine_rejects_output_with_existing_entity_files(
    tmp_path: Path,
    survey_files: tuple[Path, Path],
) -> None:
    source = tmp_path / "source"
    output = tmp_path / "combined"
    write_entities(parse_survey(*survey_files), source, "json")
    output.mkdir()
    (output / "surveys.json").write_text("[]", encoding="utf-8")

    result = CliRunner().invoke(app, ["entities", "combine", str(source), "--output", str(output)])

    assert result.exit_code == 2
    assert "already contains entity files" in result.output


def test_entities_combine_rejects_incomplete_entity_collection(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "surveys.json").write_text("[]", encoding="utf-8")

    result = CliRunner().invoke(app, ["entities", "combine", str(source), "--output", str(tmp_path / "output")])

    assert result.exit_code == 2
    assert "missing entity files" in result.output
