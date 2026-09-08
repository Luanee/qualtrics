"""Export Qualtrics surveys, extract their CSVs, parse them, and render reports."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated
from zipfile import BadZipFile, ZipFile

import typer

from qualtrics import QualtricsClient, parse_survey, render_report, write_entities
from qualtrics.api import ExportCallback, ExportEvent, ResponseExportRequest
from qualtrics.cli.api import _export_date
from qualtrics.cli.export_progress import run_surveys, validate_survey_ids


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
    end_date: Annotated[str | None, typer.Option(help="Optional ISO 8601 upper bound for recorded responses")] = None,
    batch_size: Annotated[int, typer.Option(min=1, help="Maximum concurrent surveys")] = 1,
    retries: Annotated[int, typer.Option(min=0, help="Retries per safe API request")] = 3,
    no_progress: Annotated[bool, typer.Option("--no-progress")] = False,
) -> None:
    """Export surveys and create their CSVs, entities, and HTML reports."""
    validate_survey_ids(survey_ids)
    if format not in {"parquet", "json", "csv"}:
        raise typer.BadParameter("format must be parquet, json, or csv")

    start_date, end_date = _export_date(start_date), _export_date(end_date)
    if start_date and end_date and datetime.fromisoformat(start_date) > datetime.fromisoformat(end_date):
        raise typer.BadParameter("start-date must not be later than end-date")

    with QualtricsClient(max_retries=retries) as client:

        def export_one(survey_id: str, on_progress: ExportCallback) -> str:
            on_progress(ExportEvent(survey_id, "starting"))
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
                    endDate=end_date,
                ),
                on_progress=on_progress,
            )

            _extract_single_csv(archive_path, csv_path)
            entities = parse_survey(csv_path, definition_path)
            write_entities(entities, entities_path, format)
            render_report(entities, report_path)

            return (
                f"Parsed {len(entities.responses):,} responses for {survey_id}\n"
                f"Definition: {definition_path}\n"
                f"ZIP export: {archive_path}\n"
                f"CSV export: {csv_path}\n"
                f"{format.title()} entities: {entities_path}\n"
                f"HTML report: {report_path}"
            )

        results, failures = run_surveys(
            survey_ids,
            export_one,
            batch_size=batch_size,
            show_progress=not no_progress,
            description="Completed surveys",
        )
    for summary in results.values():
        typer.echo(summary)
    for survey_id, error in failures.items():
        typer.echo(f"{survey_id}: {error}", err=True)
    if failures:
        raise typer.Exit(1)


if __name__ == "__main__":
    typer.run(main)
