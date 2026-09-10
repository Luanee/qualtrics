"""Prepare coverage and data-quality view models for the summary page."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..context import ReportContext
from ..dashboard_view import render_dashboard
from ..templating import render_template, trusted_html


@dataclass(frozen=True)
class CoverageRow:
    survey_id: str
    label: str
    metadata: str
    count: int
    rate: int


@dataclass
class CoverageGroup:
    id: str
    label: str
    rows: list[CoverageRow] = field(default_factory=list)


@dataclass(frozen=True)
class IssueGroup:
    label: str
    metadata: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class QualityPanel:
    survey_id: str
    label: str
    field_count: int
    option_count: int
    fields: tuple[IssueGroup, ...]
    options: tuple[IssueGroup, ...]


def _issue_groups(context: ReportContext, items: list[dict[str, Any]], label_key: str) -> tuple[IssueGroup, ...]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(str(item.get("question_id") or "Unknown"), []).append(item)
    groups = []
    for qid, question_items in grouped.items():
        sid = str(question_items[0].get("survey_id") or "")
        question = context.analysis.questions.get((sid, qid), {})
        label = str(question.get("question_text") or qid)
        block_name = str(question.get("block_name") or "")
        external_id = str(question.get("question_external_id") or qid)
        metadata = external_id + (f" · Section: {block_name}" if block_name else "")
        labels = tuple(
            str(item.get(label_key) or item.get("field_id") or item.get("answer_id") or "Unknown")
            for item in question_items
        )
        groups.append(IssueGroup(label, metadata, labels))
    return tuple(groups)


def render_overview(context: ReportContext, findings: tuple[str, ...]) -> str:
    analysis = context.analysis
    groups: dict[str, CoverageGroup] = {}
    for key, question in analysis.response_questions.items():
        qid = str(question["question_id"])
        external_id = str(question.get("question_external_id") or qid)
        sid = str(key[0])
        label = str(question.get("question_text") or qid)
        block_name = str(question.get("block_name") or "")
        survey_label = str(analysis.survey_lookup.get(sid, {}).get("survey_name") or sid)
        catalog_id = str(question.get("question_catalog_id") or f"{sid}::{external_id}")
        catalog_label = str(context.question_catalog_lookup.get(catalog_id, {}).get("question_text") or label)
        count = len(analysis.question_responses.get(key, set()))
        total = analysis.survey_response_counts.get(sid, 0)
        rate = round(count / total * 100 if total else 0)
        metadata = f"Import ID: {external_id}"
        if block_name:
            metadata += f" · Section: {block_name}"
        groups.setdefault(catalog_id, CoverageGroup(catalog_id, catalog_label)).rows.append(
            CoverageRow(survey_id=sid, label=survey_label, metadata=metadata, count=count, rate=rate)
        )
    quality = []
    for sid, survey in analysis.survey_lookup.items():
        fields = [item for item in analysis.unused_fields if str(item["survey_id"]) == sid]
        options = [item for item in analysis.unused_options if str(item["survey_id"]) == sid]
        quality.append(
            QualityPanel(
                survey_id=sid,
                label=str(survey.get("survey_name") or sid),
                field_count=len(fields),
                option_count=len(options),
                fields=_issue_groups(context, fields, "field_text"),
                options=_issue_groups(context, options, "answer_text"),
            )
        )
    return render_template(
        "pages/overview.html.jinja",
        survey_name=analysis.survey_name,
        responses=len(context.entities.responses),
        finished=analysis.finished_count,
        completion=analysis.finished_count / analysis.response_count * 100 if analysis.response_count else 0,
        other=analysis.response_count - analysis.finished_count,
        dashboard=trusted_html(render_dashboard(context.entities, analysis)),
        findings=tuple(trusted_html(finding) for finding in findings),
        response_questions=len(analysis.response_questions),
        content_answers=analysis.content_answer_count,
        unanswered=len(analysis.unanswered_questions),
        unused_fields=len(analysis.unused_fields),
        multiple_surveys=len(context.entities.surveys) > 1,
        quality_panels=quality,
        coverage_groups=tuple(groups.values()),
    )
