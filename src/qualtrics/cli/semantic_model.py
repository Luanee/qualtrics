from pathlib import Path
from typing import Annotated

import typer

from ..models.semantic import SEMANTIC_TABLE_NAMES, build_semantic_model
from ..serialization import load_entities
from ..serialization.semantic import write_semantic_model
from .entity_folders import validate_entity_collection

app = typer.Typer(help="Build analysis-ready semantic tables from normalized entities.")


@app.command("build")
def build_semantic(
    folder: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")],
    format: Annotated[str, typer.Option("--format", "-f")] = "parquet",
) -> None:
    if format not in {"csv", "json", "parquet"}:
        raise typer.BadParameter("format must be csv, json, or parquet")
    validate_entity_collection(folder)
    existing = [
        output / f"{name}.{extension}"
        for name in SEMANTIC_TABLE_NAMES
        for extension in ("csv", "json", "parquet")
        if (output / f"{name}.{extension}").exists()
    ]
    if existing:
        raise typer.BadParameter(f"output already contains semantic tables: {output}")
    try:
        model = build_semantic_model(load_entities(folder))
        write_semantic_model(model, output, format)
    except (ValueError, RuntimeError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Wrote {len(SEMANTIC_TABLE_NAMES)} {format} semantic tables to {output}")
