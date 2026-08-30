from pathlib import Path
from typing import Annotated

import typer

from ..reporting import render_report
from ..serialization import load_entities


def report(
    output: Annotated[Path, typer.Option("--output", "-o")],
    folder: Annotated[Path | None, typer.Option(exists=True, file_okay=False)] = None,
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
    if folder is None and not paths:
        raise typer.BadParameter("provide --folder or at least one entity path")
    render_report(load_entities(folder, **paths), output)
    typer.echo(f"Wrote HTML report to {output}")
