"""Compose the offline report from explicit context, pages and document layout."""

from pathlib import Path

from ..models.entities import EntitySet
from .context import ReportContext
from .layouts.document import render_document
from .pages.codebook import render_codebook
from .pages.flow import render_flow
from .pages.overview import render_overview
from .pages.questions import render_questions
from .pages.responses import render_responses
from .pages.written import render_written_answers


def render_report(entities: EntitySet, output: str | Path) -> None:
    context = ReportContext.build(entities)
    questions = render_questions(context)
    pages = (
        render_overview(context, questions.findings),
        questions.markup,
        render_written_answers(context),
        render_codebook(context),
        render_flow(context, questions.flow_question_targets),
        render_responses(context),
    )
    Path(output).write_text(render_document(context, pages), encoding="utf-8")
