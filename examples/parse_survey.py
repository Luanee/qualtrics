"""Parse one Qualtrics CSV and create entity files plus an HTML report."""

from pathlib import Path
from typing import Annotated

import typer

from qualtrics_toolkit import parse_survey, render_report, write_entities


def main(
    csv: Annotated[Path, typer.Argument(exists=True, readable=True)],
    qsf: Annotated[Path | None, typer.Option(exists=True, readable=True)] = None,
    output: Annotated[Path, typer.Option("--output", "-o")] = Path("entities"),
    format: Annotated[str, typer.Option("--format", "-f")] = "json",
    report: Annotated[Path, typer.Option()] = Path("report.html"),
) -> None:
    """Parse a CSV; a same-name QSF is discovered when --qsf is omitted."""
    if format not in {"json", "csv", "parquet"}:
        raise typer.BadParameter("format must be json, csv, or parquet")
    entities = parse_survey(csv, qsf)
    write_entities(entities, output, format)
    render_report(entities, report)
    typer.echo(f"Parsed {len(entities.responses)} responses")
    typer.echo(f"Wrote entities to {output} and report to {report}")


if __name__ == "__main__":
    typer.run(main)
