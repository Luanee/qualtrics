"""List every quota for a Qualtrics survey."""

from typing import Annotated

import typer

from qualtrics import QualtricsClient


def main(
    survey_id: Annotated[str, typer.Argument(help="Qualtrics survey ID")],
) -> None:
    """Print quota progress for one survey."""
    with QualtricsClient() as client:
        for quota in client.survey_quotas.iter(survey_id):
            typer.echo(f"{quota.id}\t{quota.count}/{quota.quota}\t{quota.name}")


if __name__ == "__main__":
    typer.run(main)
