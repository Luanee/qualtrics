"""Import a UTF-8 Qualtrics response CSV and wait for processing to finish."""

from pathlib import Path
from typing import Annotated

import typer

from qualtrics import QualtricsClient


def main(
    survey_id: Annotated[str, typer.Argument(help="Target survey ID, such as SV_123")],
    csv: Annotated[Path, typer.Argument(exists=True, readable=True, dir_okay=False)],
) -> None:
    """Import responses using constructor arguments or QUALTRICS_* environment settings."""
    with QualtricsClient() as client:
        started = client.responses.import_file(survey_id, csv)
        if not started.progress_id:
            raise RuntimeError("Qualtrics did not return a progressId")
        completed = client.responses.wait_for_import(survey_id, started.progress_id)
        typer.echo(f"Import {completed.progress_id}: {completed.status}")


if __name__ == "__main__":
    typer.run(main)
