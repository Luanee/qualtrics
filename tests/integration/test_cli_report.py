from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from typer.testing import CliRunner

from qualtrics import parse_survey, write_entities
from qualtrics.cli import app


def _write_survey_folders(root: Path, survey_files: tuple[Path, Path]) -> tuple[Path, Path]:
    first = parse_survey(*survey_files)
    second = deepcopy(first)
    for rows in vars(second).values():
        for row in rows:
            if "survey_id" in row:
                row["survey_id"] = "SV_SECOND"
    second.surveys[0]["survey_name"] = "Second survey"

    first_folder = root / "SV_SAMPLE"
    second_folder = root / "SV_SECOND"
    write_entities(first, first_folder / "entities", "json")
    write_entities(second, second_folder / "entities", "json")
    return first_folder, second_folder


def _assert_combined_report(path: Path) -> None:
    report = path.read_text(encoding="utf-8")
    assert "id='survey-toggle'" in report
    assert "id='survey-menu'" in report
    assert report.count("class='survey-choice'") == 2
    assert ">Sample</span>" in report
    assert "Second survey" in report
    assert "data-survey='SV_SAMPLE'" in report
    assert "data-survey='SV_SECOND'" in report


def test_report_cli_combines_repeated_survey_folders(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    first_folder, second_folder = _write_survey_folders(tmp_path / "data", survey_files)
    output = tmp_path / "repeated-folders.html"

    result = CliRunner().invoke(
        app,
        [
            "report",
            "--folder",
            str(first_folder),
            "--folder",
            str(second_folder),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    _assert_combined_report(output)


def test_report_cli_discovers_survey_folders_under_batch_root(
    tmp_path: Path,
    survey_files: tuple[Path, Path],
) -> None:
    data_folder = tmp_path / "data"
    _write_survey_folders(data_folder, survey_files)
    output = tmp_path / "batch-root.html"

    result = CliRunner().invoke(
        app,
        ["report", "--folder", str(data_folder), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    _assert_combined_report(output)


def test_report_cli_still_accepts_one_entity_folder(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    first_folder, _ = _write_survey_folders(tmp_path / "data", survey_files)
    output = tmp_path / "single.html"

    result = CliRunner().invoke(
        app,
        ["report", "--folder", str(first_folder / "entities"), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    report = output.read_text(encoding="utf-8")
    assert "<title>Sample · Response report</title>" in report
    assert "Second survey" not in report
