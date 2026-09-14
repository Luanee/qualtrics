"""Import prepared comment translations without calling a translation provider."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Annotated

import typer

from .._common.models.comment_translations import import_comment_translations
from .._common.models.entities import ALL_ENTITY_NAMES
from .._common.models.survey_manifest import MANIFEST_FILENAME
from .._common.serialization import load_entities, write_entities
from .entity_folders import ENTITY_EXTENSIONS, validate_entity_collection

app = typer.Typer(help="Attach optional, prepared written-answer translations.")

INPUT_COLUMNS = ("response_answer_id", "target_language", "source_text_hash", "translated_text")


def _read_prepared(path: Path) -> list[dict[str, object]]:
    if path.suffix.casefold() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or tuple(reader.fieldnames) != INPUT_COLUMNS:
                raise ValueError(f"Translation CSV must have columns: {', '.join(INPUT_COLUMNS)}")
            rows = list(reader)
            if any(None in row for row in rows):
                raise ValueError("Translation CSV has extra values in a row")
            return rows
    if path.suffix.casefold() == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("PyArrow is required for Parquet input") from exc
        table = pq.read_table(path)
        if tuple(table.schema.names) != INPUT_COLUMNS:
            raise ValueError(f"Translation Parquet must have columns: {', '.join(INPUT_COLUMNS)}")
        return table.to_pylist()
    raise ValueError("Translation input must be CSV or Parquet")


@app.command("import")
def import_prepared(
    folder: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
    prepared_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option("--output", "-o")],
    format: Annotated[str, typer.Option("--format", "-f")] = "parquet",
) -> None:
    """Write a new entity folder with hash-checked, prepared translations."""
    if format not in {"csv", "json", "parquet"}:
        raise typer.BadParameter("format must be csv, json, or parquet")
    validate_entity_collection(folder)
    existing = [
        output / f"{name}.{extension}"
        for name in ALL_ENTITY_NAMES
        for extension in ENTITY_EXTENSIONS
        if (output / f"{name}.{extension}").exists()
    ]
    if existing or (output / MANIFEST_FILENAME).exists():
        raise typer.BadParameter(f"output already contains entity files: {output}")
    try:
        entities = load_entities(folder)
        rows = _read_prepared(prepared_file)
        translated = import_comment_translations(entities, rows)
        write_entities(translated, output, format)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Imported {len(rows)} prepared translation(s) into {output}")
