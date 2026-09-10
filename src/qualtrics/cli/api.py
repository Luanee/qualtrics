import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

import httpx
import typer

from ..api import (
    ExportCallback,
    ExportResult,
    FilenameStrategy,
    ImportFormat,
    QualtricsAPIError,
    QualtricsClient,
    ResponseExportRequest,
)
from .export_progress import run_surveys, validate_survey_ids

app = typer.Typer(help="Call the Qualtrics API v3.")


def _client(api_token: str | None, data_center: str | None, *, max_retries: int = 3) -> QualtricsClient:
    if api_token or data_center:
        return QualtricsClient(
            api_token or os.environ.get("QUALTRICS_API_TOKEN", ""),
            data_center=data_center or os.environ.get("QUALTRICS_DATA_CENTER"),
            base_url=os.environ.get("QUALTRICS_BASE_URL"),
            max_retries=max_retries,
        )
    return QualtricsClient(max_retries=max_retries)


@app.command("surveys")
def surveys(
    api_token: Annotated[str | None, typer.Option(envvar="QUALTRICS_API_TOKEN", hidden=True)] = None,
    data_center: Annotated[str | None, typer.Option(envvar="QUALTRICS_DATA_CENTER")] = None,
) -> None:
    """List surveys available to the API token."""
    with _client(api_token, data_center) as client:
        for survey in client.surveys.iter():
            typer.echo(f"{survey.id}\t{survey.name}")


@app.command("flow")
def survey_flow(
    survey_id: Annotated[str, typer.Option("--survey-id", help="Survey whose flow to download")],
    output: Annotated[Path, typer.Option("--output", "-o", dir_okay=False)],
    api_token: Annotated[str | None, typer.Option(envvar="QUALTRICS_API_TOKEN", hidden=True)] = None,
    data_center: Annotated[str | None, typer.Option(envvar="QUALTRICS_DATA_CENTER")] = None,
    retries: Annotated[int, typer.Option(min=0, help="Retries per safe request; 0 disables retries")] = 3,
) -> None:
    """Download a flow definition for offline inspection and report walkthroughs."""
    validate_survey_ids([survey_id])
    try:
        with _client(api_token, data_center, max_retries=retries) as client:
            flow = client.survey_definitions.get_flow(survey_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".qualtrics-flow-", dir=output.parent) as temporary:
            staged = Path(temporary) / "flow.json"
            staged.write_text(json.dumps(flow, ensure_ascii=False, indent=2), encoding="utf-8")
            staged.replace(output)
    except (QualtricsAPIError, httpx.HTTPError, OSError, ValueError) as error:
        typer.echo(f"Could not download survey flow: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(output)


def _export_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise typer.BadParameter("dates must be ISO 8601, for example 2026-01-01 or 2026-01-01T09:00:00Z") from error
    # Date-only values and timestamps without offsets are interpreted as UTC.
    parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return parsed.isoformat().replace("+00:00", "Z")


@app.command("export")
def export_responses(
    survey_ids: Annotated[list[str], typer.Argument(help="One or more survey IDs")],
    output: Annotated[Path, typer.Option("--output", "-o")],
    api_token: Annotated[str | None, typer.Option(envvar="QUALTRICS_API_TOKEN", hidden=True)] = None,
    data_center: Annotated[str | None, typer.Option(envvar="QUALTRICS_DATA_CENTER")] = None,
    use_labels: Annotated[bool, typer.Option("--labels/--codes")] = True,
    naming: Annotated[FilenameStrategy, typer.Option()] = FilenameStrategy.SURVEY_ID,
    filename: Annotated[str | None, typer.Option()] = None,
    survey_name: Annotated[str | None, typer.Option()] = None,
    batch_size: Annotated[int, typer.Option(min=1, help="Maximum concurrent survey exports")] = 1,
    no_progress: Annotated[bool, typer.Option("--no-progress", help="Hide export progress")] = False,
    retries: Annotated[int, typer.Option(min=0, help="Retries per safe request; 0 disables retries")] = 3,
    format: Annotated[str, typer.Option(help="csv, tsv, json, ndjson, xml, or spss")] = "csv",
    compress: Annotated[bool, typer.Option("--compress/--no-compress")] = True,
    start_date: Annotated[
        str | None, typer.Option(help="Recorded-response lower bound (ISO 8601, UTC by default)")
    ] = None,
    end_date: Annotated[
        str | None, typer.Option(help="Recorded-response upper bound (ISO 8601, UTC by default)")
    ] = None,
    question_ids: Annotated[
        list[str] | None, typer.Option("--question-id", help="Question ID; repeat to select more")
    ] = None,
    embedded_data_ids: Annotated[
        list[str] | None, typer.Option("--embedded-data-id", help="Embedded field; repeat for more")
    ] = None,
    metadata_ids: Annotated[
        list[str] | None, typer.Option("--metadata-id", help="Survey metadata ID; repeat for more")
    ] = None,
    filter_id: Annotated[str | None, typer.Option(help="Saved Qualtrics export filter ID")] = None,
    limit: Annotated[int | None, typer.Option(min=1, help="Maximum exported responses")] = None,
    display_order: Annotated[bool, typer.Option("--display-order", help="Include randomized display order")] = False,
    label_columns: Annotated[bool, typer.Option("--label-columns", help="Include extra label columns")] = False,
    newline_replacement: Annotated[str | None, typer.Option(help="Replace newlines in response values")] = None,
    allow_continuation: Annotated[bool, typer.Option("--allow-continuation")] = False,
    continuation_token: Annotated[str | None, typer.Option(help="Resume one survey using a prior export token")] = None,
    sort_by_last_modified_date: Annotated[bool, typer.Option("--sort-by-last-modified-date")] = False,
    poll_interval: Annotated[float, typer.Option(min=0.1, help="Seconds between export status checks")] = 1.0,
    timeout: Annotated[
        float, typer.Option(min=0.1, help="Polling deadline in seconds (in-flight requests may finish later)")
    ] = 900.0,
) -> None:
    """Export one or more surveys, keeping successful files if another survey fails."""
    validate_survey_ids(survey_ids)
    if not math.isfinite(poll_interval) or not math.isfinite(timeout):
        raise typer.BadParameter("poll-interval and timeout must be finite")
    if format not in {"csv", "tsv", "json", "ndjson", "xml", "spss"}:
        raise typer.BadParameter("format must be csv, tsv, json, ndjson, xml, or spss")
    start_date, end_date = _export_date(start_date), _export_date(end_date)
    if start_date and end_date and datetime.fromisoformat(start_date) > datetime.fromisoformat(end_date):
        raise typer.BadParameter("start-date must not be later than end-date")
    if naming == FilenameStrategy.CUSTOM and not filename:
        raise typer.BadParameter("--filename is required with --naming custom")
    for values in (question_ids, embedded_data_ids, metadata_ids):
        if values and any(not value.strip() for value in values):
            raise typer.BadParameter("selected question and metadata IDs must not be empty")
    if len(survey_ids) > 1:
        if output.is_file() or (output.suffix and not output.is_dir()):
            raise typer.BadParameter("--output must be a directory when exporting multiple surveys")
        if continuation_token or filter_id or survey_name:
            raise typer.BadParameter("--continuation-token, --filter-id and --survey-name require a single survey")
    options = ResponseExportRequest(
        format=format,
        compress=compress,
        useLabels=use_labels,
        startDate=start_date,
        endDate=end_date,
        questionIds=question_ids,
        embeddedDataIds=embedded_data_ids,
        surveyMetadataIds=metadata_ids,
        filterId=filter_id,
        limit=limit,
        includeDisplayOrder=display_order,
        includeLabelColumns=label_columns,
        newlineReplacement=newline_replacement,
        allowContinuation=allow_continuation,
        continuationToken=continuation_token,
        sortByLastModifiedDate=sort_by_last_modified_date,
    )
    with _client(api_token, data_center, max_retries=retries) as client:

        def export_one(survey_id: str, on_progress: ExportCallback) -> ExportResult:
            # Qualtrics and user-provided names can repeat between surveys.
            target = output / survey_id if len(survey_ids) > 1 and naming != FilenameStrategy.SURVEY_ID else output
            return client.response_exports.export(
                survey_id,
                target,
                options=options,
                naming=naming,
                filename=filename,
                survey_name=survey_name,
                poll_interval=poll_interval,
                timeout=timeout,
                on_progress=on_progress,
            )

        results, failures = run_surveys(survey_ids, export_one, batch_size=batch_size, show_progress=not no_progress)
    for survey_id, result in results.items():
        typer.echo(result.path)
        if result.continuation_token:
            typer.echo(f"{survey_id} continuation token: {result.continuation_token}", err=True)
    for survey_id, error in failures.items():
        typer.echo(f"{survey_id}: {error}", err=True)
    if failures:
        raise typer.Exit(1)


@app.command("import")
def import_responses(
    survey_id: Annotated[str, typer.Argument()],
    source: Annotated[Path, typer.Argument(exists=True, readable=True, dir_okay=False)],
    api_token: Annotated[str | None, typer.Option(envvar="QUALTRICS_API_TOKEN", hidden=True)] = None,
    data_center: Annotated[str | None, typer.Option(envvar="QUALTRICS_DATA_CENTER")] = None,
) -> None:
    """Import a UTF-8 CSV response file and wait for Qualtrics to process it."""
    with _client(api_token, data_center) as client:
        started = client.responses.import_file(survey_id, source, format=ImportFormat.CSV)
        if not started.progress_id:
            raise typer.BadParameter("Qualtrics did not return a progressId")
        result = client.responses.wait_for_import(survey_id, started.progress_id)
    typer.echo(f"{result.progress_id}\t{result.status}")
