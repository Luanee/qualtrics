from pathlib import Path
from typing import Annotated

import typer

from ..models import merge_entity_sets
from ..models.entities import ENTITY_NAMES
from ..serialization import load_entities, write_entities
from .entity_folders import ENTITY_EXTENSIONS, resolve_entity_folders, validate_entity_collection

app = typer.Typer(help="Work with canonical entity collections.")


@app.command()
def combine(
    folders: Annotated[list[Path], typer.Argument(exists=True, file_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")],
    format: Annotated[str, typer.Option("--format", "-f")] = "parquet",
) -> None:
    """Combine entity collections from multiple folders."""
    if format not in {"csv", "json", "parquet"}:
        raise typer.BadParameter("format must be csv, json, or parquet")
    entity_folders = list(
        dict.fromkeys(entity_folder.resolve() for folder in folders for entity_folder in resolve_entity_folders(folder))
    )
    for folder in entity_folders:
        validate_entity_collection(folder)
    existing_output_files = [
        output / f"{name}.{extension}"
        for name in ENTITY_NAMES
        for extension in ENTITY_EXTENSIONS
        if (output / f"{name}.{extension}").is_file()
    ]
    if existing_output_files:
        raise typer.BadParameter(f"output already contains entity files: {output}")
    try:
        entities = merge_entity_sets([load_entities(folder) for folder in entity_folders])
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    write_entities(entities, output, format)
    typer.echo(f"Combined {len(entities.surveys)} survey(s) as {format} entities in {output}")
