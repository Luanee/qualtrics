# ruff: noqa: E501 -- HTML markup
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any

from ..components.field_labels import display_field_label
from ..components.primitives import page_heading, search_control
from ..context import ReportContext
from ..insights import question_highlight
from ..question_presentation import render_question_analysis


@dataclass(frozen=True)
class QuestionPageResult:
    markup: str
    findings: tuple[str, ...]
    flow_question_targets: dict[tuple[str, str], str]


def render_questions(context: ReportContext) -> QuestionPageResult:
    fields = context.analysis.fields
    survey_lookup = context.analysis.survey_lookup
    response_questions = context.analysis.response_questions
    question_responses = context.analysis.question_responses
    question_answers = context.analysis.question_answers
    survey_response_counts = context.analysis.survey_response_counts
    answer_options = context.answer_options
    question_options = context.question_options
    question_catalog_lookup = context.question_catalog_lookup
    analytics_by_catalog: dict[str, dict[str, Any]] = {}
    flow_question_targets: dict[tuple[str, str], str] = {}
    findings = []
    for occurrence_index, (key, question) in enumerate(response_questions.items(), 1):
        question_id = str(question["question_id"])
        question_external_id = str(question.get("question_external_id") or question_id)
        label = str(question.get("question_text") or question_id)
        question_type = str(question.get("question_type") or "Unknown").upper()
        selector = str(question.get("selector") or "")
        observed = question_answers.get(key, [])
        respondent_count = len(question_responses.get(key, set()))
        question_response_total = survey_response_counts.get(str(key[0]), 0)
        coverage = respondent_count / question_response_total * 100 if question_response_total else 0
        question_fields = [field for field_key, field in fields.items() if field_key[:2] == key]
        field_labels = {
            str(field["field_id"]): display_field_label(field, question, answer_options) for field in question_fields
        }
        analysis_body, value_count, value_label = render_question_analysis(
            question, question_fields, observed, question_options.get(key, []), field_labels, respondent_count
        )
        summary = f"<span><b>{respondent_count:,}</b> respondents</span><span><b>{coverage:.0f}%</b> coverage</span><span><b>{value_count:,}</b> {value_label}</span>"
        type_label = {"MC": "Multiple choice", "TE": "Text entry"}.get(
            question_type, question_type.replace("_", " ").title()
        )
        block_label = str(question.get("block_name") or "")
        survey_id = str(key[0])
        flow_question_targets[(survey_id, question_external_id)] = f"question-detail-{occurrence_index}"
        survey_label = str(survey_lookup.get(survey_id, {}).get("survey_name") or survey_id)
        catalog_id = str(question.get("question_catalog_id") or f"{survey_id}::{question_id}")
        catalog_label = str(question_catalog_lookup.get(catalog_id, {}).get("question_text") or label)
        occurrence_metadata = f"Import ID: {question_external_id} · {type_label}"
        if selector:
            occurrence_metadata += f" · {selector}"
        if block_label:
            occurrence_metadata += f" · Section: {block_label}"
        highlight = question_highlight(
            question, question_fields, observed, question_options.get(key, []), respondent_count
        )
        if highlight:
            findings.append(
                f"<article class='finding' data-survey='{html.escape(survey_id, quote=True)}'>"
                f"<a href='#question-detail-{occurrence_index}'>{html.escape(label)}</a>"
                f"<small>{html.escape(survey_label)}</small><p>{html.escape(highlight)}</p></article>"
            )
        occurrence = (
            f"<details class='survey-analysis survey-occurrence' data-survey='{html.escape(survey_id, quote=True)}' "
            f"id='question-detail-{occurrence_index}' data-question='{html.escape(question_external_id, quote=True)}' "
            f"data-label='{html.escape(label, quote=True)}' data-section='{html.escape(block_label, quote=True)}' "
            f"data-question-token='{html.escape(f'{survey_id}::{question_external_id}', quote=True)}'>"
            f"<summary><span class='analysis-title'>{html.escape(survey_label)}"
            f"<small>{html.escape(occurrence_metadata)}</small></span>"
            f"<span class='analysis-summary'>{summary}</span></summary>"
            f"<div class='analysis-body'>{analysis_body}</div></details>"
        )
        group = analytics_by_catalog.setdefault(catalog_id, {"label": catalog_label, "occurrences": []})
        group["occurrences"].append(occurrence)

    question_analytics = []
    for catalog_id, group in analytics_by_catalog.items():
        occurrences = group["occurrences"]
        occurrence_label = "survey occurrence" if len(occurrences) == 1 else "survey occurrences"
        question_analytics.append(
            f"<details class='question-analysis catalog-group' data-catalog='{html.escape(catalog_id, quote=True)}'>"
            f"<summary><span class='analysis-title'>{html.escape(str(group['label']))}"
            f"<small class='occurrence-count'>{len(occurrences)} {occurrence_label}</small></span></summary>"
            f"<div class='catalog-body'>{''.join(occurrences)}</div></details>"
        )

    markup = (
        "<details id='question-analytics' class='report-section report-view' open>"
        f"{page_heading('Questions', 'Type-aware answer patterns grouped across surveys.', disclosure=True, count=f'{len(question_analytics)} canonical questions', count_id='analytics-count')}"
        "<div class='section-body'><div class='question-browser'><div class='question-sidebar'>"
        f"{search_control('question-filter', 'Find a question')}"
        "<div id='question-navigator'></div><p id='question-empty' hidden>No matching questions in the selected surveys.</p></div>"
        f"<div class='question-detail'>{''.join(question_analytics)}</div></div></div></details>"
    )
    return QuestionPageResult(markup, tuple(findings), flow_question_targets)
