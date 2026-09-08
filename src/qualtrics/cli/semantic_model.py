import sqlite3
from pathlib import Path
from typing import Annotated

import typer

from ..models.semantic import SEMANTIC_TABLE_NAMES, build_semantic_model
from ..serialization import load_entities
from ..serialization.semantic import SEMANTIC_SQLITE_FILENAME, write_semantic_model
from .entity_folders import validate_entity_collection

app = typer.Typer(help="Build analysis-ready semantic tables from normalized entities.")


@app.command("build")
def build_semantic(
    folder: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o", file_okay=False, help="Destination directory.")],
    format: Annotated[str, typer.Option("--format", "-f", help="parquet, sqlite, csv, or json.")] = "parquet",
) -> None:
    if format not in {"csv", "json", "parquet", "sqlite"}:
        raise typer.BadParameter("format must be csv, json, parquet, or sqlite")
    validate_entity_collection(folder)
    existing = [
        output / f"{name}.{extension}"
        for name in SEMANTIC_TABLE_NAMES
        for extension in ("csv", "json", "parquet")
        if (output / f"{name}.{extension}").exists()
    ]
    database = output / SEMANTIC_SQLITE_FILENAME
    if existing or database.exists() or database.is_symlink():
        raise typer.BadParameter(f"output already contains semantic tables: {output}")
    try:
        model = build_semantic_model(load_entities(folder))
        write_semantic_model(model, output, format)
    except (ValueError, RuntimeError, OSError, sqlite3.Error) as exc:
        raise typer.BadParameter(str(exc)) from exc
    destination = database if format == "sqlite" else output
    typer.echo(f"Wrote {len(SEMANTIC_TABLE_NAMES)} {format} semantic tables to {destination}")
