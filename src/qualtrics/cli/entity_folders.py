from pathlib import Path

import typer

from ..models.entities import ENTITY_NAMES

ENTITY_EXTENSIONS = ("json", "csv", "parquet")


def has_entities(folder: Path) -> bool:
    return any((folder / f"surveys.{extension}").is_file() for extension in ENTITY_EXTENSIONS)


def entity_files(folder: Path, name: str) -> list[Path]:
    return [
        folder / f"{name}.{extension}" for extension in ENTITY_EXTENSIONS if (folder / f"{name}.{extension}").is_file()
    ]


def validate_entity_collection(folder: Path) -> None:
    missing = [name for name in ENTITY_NAMES if not entity_files(folder, name)]
    ambiguous = [name for name in ENTITY_NAMES if len(entity_files(folder, name)) > 1]
    if missing:
        raise typer.BadParameter(f"{folder} is missing entity files: {', '.join(missing)}")
    if ambiguous:
        raise typer.BadParameter(f"{folder} has multiple formats for entities: {', '.join(ambiguous)}")


def resolve_entity_folders(folder: Path) -> list[Path]:
    if has_entities(folder):
        return [folder]
    if has_entities(folder / "entities"):
        return [folder / "entities"]
    discovered = [
        child / "entities" for child in sorted(folder.iterdir()) if child.is_dir() and has_entities(child / "entities")
    ]
    if discovered:
        return discovered
    raise typer.BadParameter(f"no entity files or survey entity folders found under {folder}")
