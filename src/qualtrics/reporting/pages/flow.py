from ..context import ReportContext
from ..flow import render_flow as render_flow_content


def render_flow(context: ReportContext, question_targets: dict[tuple[str, str], str]) -> str:
    return render_flow_content(context.entities, question_targets)
