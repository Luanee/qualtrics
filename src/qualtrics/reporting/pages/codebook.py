from ..codebook import render_codebook as render_codebook_content
from ..context import ReportContext


def render_codebook(context: ReportContext) -> str:
    return render_codebook_content(context.entities)
