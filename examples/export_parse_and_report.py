"""Export Qualtrics surveys, extract their CSVs, parse them, and render reports."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Annotated
from zipfile import BadZipFile, ZipFile

import typer

from qualtrics import QualtricsClient, parse_survey, render_report, write_entities
from qualtrics.api import ResponseExportRequest


def _extract_single_csv(archive_path: Path, csv_path: Path) -> None:
    try:
        with ZipFile(archive_path) as archive:
            csv_members = [
                member
                for member in archive.infolist()
                if not member.is_dir()
                and Path(member.filename).suffix.casefold() == ".csv"
                and "__MACOSX" not in Path(member.filename).parts
            ]
            if len(csv_members) != 1:
                raise ValueError(
                    f"Qualtrics response ZIP must contain exactly one CSV; found {len(csv_members)} in {archive_path}"
                )
            with archive.open(csv_members[0]) as source, csv_path.open("wb") as target:
                shutil.copyfileobj(source, target)
    except BadZipFile as error:
        raise ValueError(f"Invalid Qualtrics response ZIP: {archive_path}") from error


def main(
    survey_ids: Annotated[
        list[str],
        typer.Argument(help="One or more Qualtrics survey IDs, for example SV_abc123 SV_def456"),
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="Root output directory")] = Path("data"),
    use_labels: Annotated[bool, typer.Option("--labels/--codes")] = True,
    format: Annotated[str, typer.Option("--format", "-f", help="Entity file format")] = "parquet",
    start_date: Annotated[
        str | None,
        typer.Option("--start-date", help="Optional ISO 8601 lower bound for recorded responses"),
    ] = None,
) -> None:
    """Export surveys and create their CSVs, entities, and HTML reports."""
    invalid_ids = [
        survey_id for survey_id in survey_ids if Path(survey_id).name != survey_id or survey_id in {".", ".."}
    ]
    if invalid_ids:
        raise typer.BadParameter(f"survey IDs must not contain path separators: {', '.join(invalid_ids)}")
    if format not in {"parquet", "json", "csv"}:
        raise typer.BadParameter("format must be parquet, json, or csv")

    with QualtricsClient() as client:
        for survey_id in survey_ids:
            survey_folder = output / survey_id
            survey_folder.mkdir(parents=True, exist_ok=True)
            definition_path = survey_folder / "definition.qsf"
            archive_path = survey_folder / "export.zip"
            csv_path = survey_folder / "responses.csv"
            report_path = survey_folder / "report.html"
            entities_path = survey_folder / "entities"

            definition = client.survey_definitions.get(survey_id)
            definition_path.write_text(
                json.dumps(definition.payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            client.response_exports.export(
                survey_id,
                archive_path,
                options=ResponseExportRequest(
                    format="csv",
                    compress=True,
                    useLabels=use_labels,
                    newlineReplacement="//",
                    startDate=start_date,
                ),
            )

            _extract_single_csv(archive_path, csv_path)
            entities = parse_survey(csv_path, definition_path)
            write_entities(entities, entities_path, format)
            render_report(entities, report_path)

            typer.echo(f"Parsed {len(entities.responses):,} responses for {survey_id}")
            typer.echo(f"Definition: {definition_path}")
            typer.echo(f"ZIP export: {archive_path}")
            typer.echo(f"CSV export: {csv_path}")
            typer.echo(f"{format.title()} entities: {entities_path}")
            typer.echo(f"HTML report: {report_path}")


if __name__ == "__main__":
    typer.run(main)
