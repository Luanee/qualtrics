"""List accessible surveys and optionally export one survey's responses."""

from pathlib import Path
from typing import Annotated

import typer

from qualtrics_toolkit import QualtricsClient
from qualtrics_toolkit.api import FilenameStrategy, ResponseExportRequest


def main(
    survey_id: Annotated[str | None, typer.Option(help="Survey to export")] = None,
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("exports"),
) -> None:
    """Use QUALTRICS_* environment settings unless constructor values are supplied."""
    with QualtricsClient() as client:
        for survey in client.surveys.iter():
            typer.echo(f"{survey.id}\t{survey.name}")
        if survey_id:
            result = client.responses.export(
                survey_id,
                output,
                options=ResponseExportRequest(format="csv", use_labels=True),
                naming=FilenameStrategy.SURVEY_ID,
            )
            typer.echo(f"Downloaded {result.path}")


if __name__ == "__main__":
    typer.run(main)
