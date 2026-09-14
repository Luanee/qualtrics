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


def test_entities_combine_does_not_replace_existing_manifest(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    source = tmp_path / "source"
    output = tmp_path / "combined"
    write_entities(parse_survey(*survey_files), source, "json")
    output.mkdir()
    manifest = output / "manifest.json"
    manifest.write_text("original", encoding="utf-8")

    result = CliRunner().invoke(app, ["entities", "combine", str(source), "--output", str(output)])

    assert result.exit_code == 2
    assert "already contains entity files" in result.output
    assert manifest.read_text(encoding="utf-8") == "original"
    assert list(output.iterdir()) == [manifest]


def test_entities_combine_rejects_incomplete_entity_collection(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "surveys.json").write_text("[]", encoding="utf-8")

    result = CliRunner().invoke(app, ["entities", "combine", str(source), "--output", str(tmp_path / "output")])

    assert result.exit_code == 2
    assert "missing entity files" in result.output


def test_entities_combine_equivalent_catalog_labels_survive_serialization(
    tmp_path: Path, catalog_survey_factory
) -> None:
    from qualtrics._common.models.entity_set import validate_entity_set

    first = catalog_survey_factory("SV_1", "How was your visit?")
    second = catalog_survey_factory("SV_2", "HOW WAS YOUR VISIT?")
    source_a, source_b, output = (tmp_path / name for name in ("first", "second", "combined"))
    write_entities(first, source_a, "json")
    write_entities(second, source_b, "csv")

    result = CliRunner().invoke(
        app,
        [
            "entities",
            "combine",
            str(source_a),
            str(source_b),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    combined = load_entities(output)
    validate_entity_set(combined, strict=True)
    assert combined.question_catalog == first.question_catalog
    assert combined.question_field_catalog == first.question_field_catalog
    assert [row["question_text"] for row in combined.questions] == ["How was your visit?", "HOW WAS YOUR VISIT?"]
    assert [row["field_text"] for row in combined.question_fields] == ["How was your visit?", "HOW WAS YOUR VISIT?"]
    assert (
        len(combined.surveys)
        == len(combined.responses)
        == len(combined.response_answers)
        == len(combined.comments)
        == 2
    )
    assert {row["response_answer_id"] for row in combined.comments} == {
        row["response_answer_id"] for item in (first, second) for row in item.comments
    }
