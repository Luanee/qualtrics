from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile

import typer
from examples import export_parse_and_report
from typer.testing import CliRunner


def test_cli_exports_and_parses_multiple_surveys(
    tmp_path: Path,
    monkeypatch,
    survey_files: tuple[Path, Path],
) -> None:
    source_path, definition_path = survey_files
    definition = json.loads(definition_path.read_text(encoding="utf-8"))

    class FakeDefinitions:
        def get(self, survey_id: str):
            payload = dict(definition)
            payload["SurveyEntry"] = dict(payload["SurveyEntry"], SurveyID=survey_id, SurveyName=f"Survey {survey_id}")
            return SimpleNamespace(payload=payload)

    class FakeExports:
        def export(self, survey_id: str, archive_path: Path, *, options) -> None:
            assert options.format == "csv"
            with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
                archive.write(source_path, f"{survey_id}.csv")

    class FakeClient:
        def __init__(self) -> None:
            self.survey_definitions = FakeDefinitions()
            self.response_exports = FakeExports()

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

    monkeypatch.setattr(export_parse_and_report, "QualtricsClient", FakeClient)
    app = typer.Typer()
    app.command()(export_parse_and_report.main)

    result = CliRunner().invoke(
        app,
        ["--output", str(tmp_path), "--format", "json", "SV_FIRST", "SV_SECOND"],
    )

    assert result.exit_code == 0, result.output
    for survey_id in ("SV_FIRST", "SV_SECOND"):
        survey_folder = tmp_path / survey_id
        assert (survey_folder / "definition.qsf").is_file()
        assert (survey_folder / "export.zip").is_file()
        assert (survey_folder / "responses.csv").is_file()
        assert (survey_folder / "entities" / "responses.json").is_file()
        assert (survey_folder / "report.html").is_file()
        assert f"Parsed 2 responses for {survey_id}" in result.output
