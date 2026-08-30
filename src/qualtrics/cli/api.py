import os
from pathlib import Path
from typing import Annotated

import typer

from ..api import FilenameStrategy, ImportFormat, QualtricsClient, ResponseExportRequest

app = typer.Typer(help="Call the Qualtrics API v3.")


def _client(api_token: str | None, data_center: str | None) -> QualtricsClient:
    if api_token or data_center:
        return QualtricsClient(
            api_token or os.environ.get("QUALTRICS_API_TOKEN", ""),
            data_center=data_center or os.environ.get("QUALTRICS_DATA_CENTER"),
            base_url=os.environ.get("QUALTRICS_BASE_URL"),
        )
    return QualtricsClient()


@app.command("surveys")
def surveys(
    api_token: Annotated[
        str | None, typer.Option(envvar="QUALTRICS_API_TOKEN", hidden=True)
    ] = None,
    data_center: Annotated[str | None, typer.Option(envvar="QUALTRICS_DATA_CENTER")] = None,
) -> None:
    """List surveys available to the API token."""
    with _client(api_token, data_center) as client:
        for survey in client.surveys.iter():
            typer.echo(f"{survey.id}\t{survey.name}")


@app.command("export")
def export_responses(
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


@app.command("import")
def import_responses(
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
