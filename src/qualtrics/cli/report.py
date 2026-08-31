from pathlib import Path
from typing import Annotated

import typer

from ..models import merge_entity_sets
from ..reporting import render_report
from ..serialization import load_entities
from .entity_folders import resolve_entity_folders


def report(
    output: Annotated[Path, typer.Option("--output", "-o")],
    folder: Annotated[list[Path] | None, typer.Option("--folder", exists=True, file_okay=False)] = None,
    surveys: Annotated[Path | None, typer.Option(exists=True)] = None,
    question_catalog: Annotated[Path | None, typer.Option(exists=True)] = None,
    question_field_catalog: Annotated[Path | None, typer.Option(exists=True)] = None,
    questions: Annotated[Path | None, typer.Option(exists=True)] = None,
    answer_options: Annotated[Path | None, typer.Option(exists=True)] = None,
    question_fields: Annotated[Path | None, typer.Option(exists=True)] = None,
    responses: Annotated[Path | None, typer.Option(exists=True)] = None,
    response_answers: Annotated[Path | None, typer.Option(exists=True)] = None,
) -> None:
    """Render a self-contained HTML report from entity files."""
    paths = {
        name: path
        for name, path in {
            "surveys": surveys,
            "question_catalog": question_catalog,
            "question_field_catalog": question_field_catalog,
            "questions": questions,
            "answer_options": answer_options,
            "question_fields": question_fields,
            "responses": responses,
            "response_answers": response_answers,
        }.items()
        if path is not None
    }
    if not folder and not paths:
        raise typer.BadParameter("provide --folder or at least one entity path")
    entity_folders = list(
        dict.fromkeys(
            entity_folder.resolve() for source in (folder or []) for entity_folder in resolve_entity_folders(source)
        )
    )
    if len(entity_folders) > 1 and paths:
        raise typer.BadParameter("explicit entity paths cannot be combined with multiple folders")
    entity_sets = [load_entities(entity_folder, **paths) for entity_folder in entity_folders]
    entities = (
        merge_entity_sets(entity_sets)
        if len(entity_sets) > 1
        else entity_sets[0]
        if entity_sets
        else load_entities(**paths)
    )
    render_report(entities, output)
    typer.echo(f"Wrote HTML report to {output}")
