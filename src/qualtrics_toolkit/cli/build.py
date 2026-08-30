from pathlib import Path
from typing import Annotated

import typer

from ..parsers import parse_survey, parse_surveys
from ..serialization import write_entities


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
