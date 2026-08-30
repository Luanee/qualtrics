"""Parse several Qualtrics CSV exports into one canonical entity collection."""

from pathlib import Path
from typing import Annotated

import typer

from qualtrics import parse_surveys, render_report, write_entities


def main(
    folder: Annotated[Path, typer.Argument(exists=True, file_okay=False, readable=True)],
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("entities"),
    report: Annotated[Path, typer.Option()] = Path("report.html"),
) -> None:
    """Parse all CSV files in a folder, discovering same-name QSF files."""
    csv_paths = sorted(folder.glob("*.csv"))
    if not csv_paths:
        raise typer.BadParameter(f"No CSV files found in {folder}")
    entities = parse_surveys(csv_paths)
    write_entities(entities, output, "json")
    render_report(entities, report)
    typer.echo(f"Parsed {len(entities.surveys)} surveys and {len(entities.responses)} responses")


if __name__ == "__main__":
    typer.run(main)
