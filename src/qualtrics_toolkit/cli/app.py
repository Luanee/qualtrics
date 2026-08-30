from pathlib import Path
from typing import Annotated

import typer

from .._core import load_entities, parse_survey, parse_surveys, render_report, write_entities
from ..api import FilenameStrategy, ImportFormat, QualtricsClient, ResponseExportRequest

app = typer.Typer(help="Parse, model, analyze, report, and export Qualtrics surveys.")
api_app = typer.Typer(help="Call the Qualtrics API v3.")
app.add_typer(api_app, name="api")


@app.command()
def build(
    csv_paths: Annotated[list[Path], typer.Argument(exists=True, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")],
    qsf: Annotated[list[Path] | None, typer.Option(exists=True, readable=True)] = None,
    format: Annotated[str, typer.Option("--format", "-f")] = "json",
    survey_id: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Build canonical entities from one or more CSV/QSF exports."""
    if format not in {"csv", "json", "parquet"}:
        raise typer.BadParameter("format must be csv, json, or parquet")
    expanded_csvs = [
        child
        for path in csv_paths
        for child in (sorted(path.glob("*.csv")) if path.is_dir() else [path])
    ]
    expanded_qsfs = [
        child
        for path in (qsf or [])
        for child in (sorted(path.glob("*.qsf")) if path.is_dir() else [path])
    ]
    if not expanded_csvs:
        raise typer.BadParameter("no CSV files found")
    if len(expanded_csvs) == 1 and len(expanded_qsfs) > 1:
        raise typer.BadParameter("provide at most one QSF for one CSV")
    if survey_id and len(expanded_csvs) != 1:
        raise typer.BadParameter("--survey-id can only be used with one CSV")
    entities = (
        parse_survey(
            expanded_csvs[0],
            expanded_qsfs[0] if expanded_qsfs else None,
            survey_id=survey_id,
        )
        if len(expanded_csvs) == 1
        else parse_surveys(expanded_csvs, expanded_qsfs)
    )
    write_entities(entities, output, format)
    typer.echo(f"Wrote {len(entities.surveys)} survey(s) as {format} entities to {output}")


@app.command()
def report(
    output: Annotated[Path, typer.Option("--output", "-o")],
    folder: Annotated[Path | None, typer.Option(exists=True, file_okay=False)] = None,
    surveys: Annotated[Path | None, typer.Option(exists=True)] = None,
    question_catalog: Annotated[Path | None, typer.Option(exists=True)] = None,
    question_field_catalog: Annotated[Path | None, typer.Option(exists=True)] = None,
    questions: Annotated[Path | None, typer.Option(exists=True)] = None,
    answer_options: Annotated[Path | None, typer.Option(exists=True)] = None,
    question_fields: Annotated[Path | None, typer.Option(exists=True)] = None,
    responses: Annotated[Path | None, typer.Option(exists=True)] = None,
    response_answers: Annotated[Path | None, typer.Option(exists=True)] = None,
) -> None:
    """Render a self-contained HTML report from entity files."""
    paths = {
        name: path
        for name, path in {
            "surveys": surveys,
            "question_catalog": question_catalog,
            "question_field_catalog": question_field_catalog,
            "questions": questions,
            "answer_options": answer_options,
            "question_fields": question_fields,
            "responses": responses,
            "response_answers": response_answers,
        }.items()
        if path is not None
    }
    if folder is None and not paths:
        raise typer.BadParameter("provide --folder or at least one entity path")
    render_report(load_entities(folder, **paths), output)
    typer.echo(f"Wrote HTML report to {output}")


def _client(api_token: str | None, data_center: str | None) -> QualtricsClient:
    if api_token or data_center:
        import os

        return QualtricsClient(
            api_token or os.environ.get("QUALTRICS_API_TOKEN", ""),
            data_center=data_center or os.environ.get("QUALTRICS_DATA_CENTER"),
            base_url=os.environ.get("QUALTRICS_BASE_URL"),
        )
    return QualtricsClient()


@api_app.command("surveys")
def api_surveys(
    api_token: Annotated[
        str | None, typer.Option(envvar="QUALTRICS_API_TOKEN", hidden=True)
    ] = None,
    data_center: Annotated[str | None, typer.Option(envvar="QUALTRICS_DATA_CENTER")] = None,
) -> None:
    """List surveys available to the API token."""
    with _client(api_token, data_center) as client:
        for survey in client.surveys.iter():
            typer.echo(f"{survey.id}\t{survey.name}")


@api_app.command("export")
def api_export(
    survey_id: Annotated[str, typer.Argument()],
    output: Annotated[Path, typer.Option("--output", "-o")],
    api_token: Annotated[
        str | None, typer.Option(envvar="QUALTRICS_API_TOKEN", hidden=True)
    ] = None,
    data_center: Annotated[str | None, typer.Option(envvar="QUALTRICS_DATA_CENTER")] = None,
    use_labels: Annotated[bool, typer.Option("--labels/--codes")] = True,
    naming: Annotated[FilenameStrategy, typer.Option()] = FilenameStrategy.SURVEY_ID,
    filename: Annotated[str | None, typer.Option()] = None,
    survey_name: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Export survey responses as CSV through the asynchronous API workflow."""
    with _client(api_token, data_center) as client:
        result = client.response_exports.export(
            survey_id,
            output,
            options=ResponseExportRequest(format="csv", useLabels=use_labels),
            naming=naming,
            filename=filename,
            survey_name=survey_name,
        )
    typer.echo(result.path)


@api_app.command("import")
def api_import(
    survey_id: Annotated[str, typer.Argument()],
    source: Annotated[Path, typer.Argument(exists=True, readable=True, dir_okay=False)],
    api_token: Annotated[
        str | None, typer.Option(envvar="QUALTRICS_API_TOKEN", hidden=True)
    ] = None,
    data_center: Annotated[str | None, typer.Option(envvar="QUALTRICS_DATA_CENTER")] = None,
) -> None:
    """Import a UTF-8 CSV response file and wait for Qualtrics to process it."""
    with _client(api_token, data_center) as client:
        started = client.responses.import_file(survey_id, source, format=ImportFormat.CSV)
        if not started.progress_id:
            raise typer.BadParameter("Qualtrics did not return a progressId")
        result = client.responses.wait_for_import(survey_id, started.progress_id)
    typer.echo(f"{result.progress_id}\t{result.status}")
