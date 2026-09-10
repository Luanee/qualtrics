"""Prepare canonical question groups, occurrences, and linked findings."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..components.field_labels import display_field_label
from ..context import ReportContext
from ..insights import question_highlight
from ..question_presentation import render_question_analysis
from ..templating import render_template, trusted_html


@dataclass(frozen=True)
class QuestionPageResult:
    markup: str
    findings: tuple[str, ...]
    flow_question_targets: dict[tuple[str, str], str]


@dataclass(frozen=True)
class QuestionOccurrence:
    id: str
    survey_id: str
    external_id: str
    label: str
    section: str
    token: str
    survey_label: str
    metadata: str
    respondents: int
    coverage: float
    value_count: int
    value_label: str
    body: str


@dataclass
class QuestionGroup:
    id: str
    label: str
    occurrences: list[QuestionOccurrence] = field(default_factory=list)


def render_questions(context: ReportContext) -> QuestionPageResult:
    analysis = context.analysis
    groups: dict[str, QuestionGroup] = {}
    flow_question_targets: dict[tuple[str, str], str] = {}
    findings = []
    for occurrence_index, (key, question) in enumerate(analysis.response_questions.items(), 1):
        qid = str(question["question_id"])
        external_id = str(question.get("question_external_id") or qid)
        label = str(question.get("question_text") or qid)
        question_type = str(question.get("question_type") or "Unknown").upper()
        selector = str(question.get("selector") or "")
        observed = analysis.question_answers.get(key, [])
        respondents = len(analysis.question_responses.get(key, set()))
        total = analysis.survey_response_counts.get(str(key[0]), 0)
        coverage = respondents / total * 100 if total else 0
        question_fields = [item for field_key, item in analysis.fields.items() if field_key[:2] == key]
        field_labels = {
            str(item["field_id"]): display_field_label(item, question, context.answer_options)
            for item in question_fields
        }
        body, value_count, value_label = render_question_analysis(
            question, question_fields, observed, context.question_options.get(key, []), field_labels, respondents
        )
        type_label = {"MC": "Multiple choice", "TE": "Text entry"}.get(
            question_type, question_type.replace("_", " ").title()
        )
        block_label = str(question.get("block_name") or "")
        sid = str(key[0])
        anchor = f"question-detail-{occurrence_index}"
        flow_question_targets[(sid, external_id)] = anchor
        survey_label = str(analysis.survey_lookup.get(sid, {}).get("survey_name") or sid)
        catalog_id = str(question.get("question_catalog_id") or f"{sid}::{qid}")
        catalog_label = str(context.question_catalog_lookup.get(catalog_id, {}).get("question_text") or label)
        metadata = f"Import ID: {external_id} · {type_label}"
        if selector:
            metadata += f" · {selector}"
        if block_label:
            metadata += f" · Section: {block_label}"
        highlight = question_highlight(
            question, question_fields, observed, context.question_options.get(key, []), respondents
        )
        if highlight:
            findings.append(
                render_template(
                    "components/finding.html.jinja",
                    survey_id=sid,
                    target=anchor,
                    label=label,
                    survey_label=survey_label,
                    highlight=highlight,
                )
            )
        group = groups.setdefault(catalog_id, QuestionGroup(catalog_id, catalog_label))
        group.occurrences.append(
            QuestionOccurrence(
                id=anchor,
                survey_id=sid,
                external_id=external_id,
                label=label,
                section=block_label,
                token=f"{sid}::{external_id}",
                survey_label=survey_label,
                metadata=metadata,
                respondents=respondents,
                coverage=coverage,
                value_count=value_count,
                value_label=value_label,
                body=trusted_html(body),
            )
        )
    return QuestionPageResult(
        render_template("pages/questions.html.jinja", groups=tuple(groups.values())),
        tuple(findings),
        flow_question_targets,
    )
