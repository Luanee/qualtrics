# ruff: noqa: E501 -- HTML markup
from __future__ import annotations

import html
from typing import Any

from ..components.primitives import empty_state, metric, page_heading
from ..context import ReportContext
from ..dashboard_view import render_dashboard


def render_overview(context: ReportContext, findings: tuple[str, ...]) -> str:
    questions = context.analysis.questions
    survey_lookup = context.analysis.survey_lookup
    survey_name = context.analysis.survey_name
    response_questions = context.analysis.response_questions
    question_responses = context.analysis.question_responses
    unanswered_questions = context.analysis.unanswered_questions
    unused_fields = context.analysis.unused_fields
    unused_options = context.analysis.unused_options
    response_count = context.analysis.response_count
    content_answer_count = context.analysis.content_answer_count
    finished_count = context.analysis.finished_count
    survey_response_counts = context.analysis.survey_response_counts
    entities = context.entities
    analysis = context.analysis
    question_catalog_lookup = context.question_catalog_lookup
    coverage_by_catalog: dict[str, dict[str, Any]] = {}
    for key, question in response_questions.items():
        question_id = str(question["question_id"])
        question_external_id = str(question.get("question_external_id") or question_id)
        survey_id = str(key[0])
        question_token = f"{survey_id}::{question_external_id}"
        label = str(question.get("question_text") or question_id)
        block_name = str(question.get("block_name") or "")
        survey_label = str(survey_lookup.get(survey_id, {}).get("survey_name") or survey_id)
        catalog_id = str(question.get("question_catalog_id") or question_token)
        catalog_label = str(question_catalog_lookup.get(catalog_id, {}).get("question_text") or label)
        count = len(question_responses.get(key, set()))
        question_response_total = survey_response_counts.get(survey_id, 0)
        rate = round((count / question_response_total * 100) if question_response_total else 0)
        occurrence_metadata = f"Import ID: {question_external_id}"
        if block_name:
            occurrence_metadata += f" · Section: {block_name}"
        coverage_row = (
            f"<tr class='coverage-survey-row survey-occurrence' data-survey='{html.escape(survey_id, quote=True)}'>"
            f"<td><strong>{html.escape(survey_label)}</strong><small>{html.escape(occurrence_metadata)}</small></td>"
            f"<td>{count:,}</td><td><div class='meter'><i style='width:{rate}%'></i></div>{rate}%</td></tr>"
        )
        group = coverage_by_catalog.setdefault(catalog_id, {"label": catalog_label, "rows": []})
        group["rows"].append(coverage_row)

    coverage_groups = []
    for catalog_id, group in coverage_by_catalog.items():
        rows = group["rows"]
        occurrence_label = "survey occurrence" if len(rows) == 1 else "survey occurrences"
        coverage_groups.append(
            f"<details class='coverage-question catalog-group' data-catalog='{html.escape(catalog_id, quote=True)}'>"
            f"<summary><span class='analysis-title'>{html.escape(str(group['label']))}"
            f"<small class='occurrence-count'>{len(rows)} {occurrence_label}</small></span></summary>"
            "<div class='catalog-body'><table><thead><tr><th>Survey occurrence</th><th>Responses</th>"
            f"<th>Coverage</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>"
        )

    def issue_groups(items: list[dict[str, Any]], label_key: str, empty: str) -> str:
        if not items:
            return f"<p class='meta'>{empty}</p>"
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            grouped.setdefault(str(item.get("question_id") or "Unknown"), []).append(item)
        groups = []
        for question_id, question_items in grouped.items():
            survey_id = str(question_items[0].get("survey_id") or "")
            question = questions.get((survey_id, question_id), {})
            question_label = str(question.get("question_text") or question_id)
            block_name = str(question.get("block_name") or "")
            external_id = str(question.get("question_external_id") or question_id)
            metadata = external_id + (f" · Section: {block_name}" if block_name else "")
            labels = "".join(
                f"<li>{html.escape(str(item.get(label_key) or item.get('field_id') or item.get('answer_id') or 'Unknown'))}</li>"
                for item in question_items
            )
            groups.append(
                f"<div class='quality-question'><strong>{html.escape(question_label)}</strong><small>{html.escape(metadata)}</small><ul>{labels}</ul></div>"
            )
        return "".join(groups)

    quality_panels = []
    for survey_id, survey in survey_lookup.items():
        survey_unused_fields = [item for item in unused_fields if str(item["survey_id"]) == survey_id]
        survey_unused_options = [item for item in unused_options if str(item["survey_id"]) == survey_id]
        field_count = len(survey_unused_fields)
        option_count = len(survey_unused_options)
        field_summary = "field without values" if field_count == 1 else "fields without values"
        option_summary = "defined option not observed" if option_count == 1 else "defined options not observed"
        survey_label = str(survey.get("survey_name") or survey_id)
        quality_panels.append(
            f"<details class='quality' data-survey='{html.escape(survey_id, quote=True)}'>"
            "<summary class='quality-head'><i></i><span class='quality-title'><strong>Data quality"
            f"{f' · {html.escape(survey_label)}' if len(entities.surveys) > 1 else ''}</strong></span>"
            f"<span class='quality-summary'><span><b>{field_count}</b> {field_summary}</span>"
            f"<span><b>{option_count}</b> {option_summary}</span></span></summary>"
            "<div class='quality-body'><div class='quality-groups'>"
            "<div class='quality-group'><h4>Fields without values</h4>"
            f"{issue_groups(survey_unused_fields, 'field_text', 'No fields without values.')}</div>"
            "<div class='quality-group'><h4>Defined options not observed</h4>"
            f"{issue_groups(survey_unused_options, 'answer_text', 'Every defined option was observed.')}</div>"
            "</div></div></details>"
        )

    return "".join((
        f"<section id='overview' class='report-view'>{page_heading('Summary', survey_name)}",
        "<div class='stats'>"
        f"{metric('stat-responses', len(entities.responses), 'Responses', kind='stat')}"
        f"<div class='stat'><strong id='overview-finished'>{finished_count:,}</strong><span>Finished · "
        f"<span id='overview-completion'>{(finished_count / response_count * 100 if response_count else 0):.0f}%</span></span></div>"
        f"{metric('overview-other', response_count - finished_count, 'Not marked finished', kind='stat')}</div>",
        render_dashboard(entities, analysis),
        "<details class='summary-details'><summary>Observed highlights</summary>"
        f"<div class='findings'>{''.join(findings)}</div>"
        f"{empty_state('findings-empty', 'No observed highlights for the selected surveys.', hidden=bool(findings))}</details>",
        "<details id='summary-details' class='summary-details'><summary>Coverage and data quality</summary>"
        "<div class='section-body'><p class='meta'>Counts describe recorded answers. Missing values do not establish whether a question was shown.</p>"
        "<div class='analytics'>"
        f"{metric('stat-questions', len(response_questions), 'Response questions', kind='analytic')}"
        f"{metric('stat-answers', content_answer_count, 'Respondent answers', kind='analytic')}"
        f"{metric('overview-unanswered', len(unanswered_questions), 'Unanswered questions', kind='analytic')}"
        f"{metric('overview-unused-fields', len(unused_fields), 'Unused fields', kind='analytic')}</div>",
        f"{''.join(quality_panels)}",
        "<details id='question-coverage' class='panel report-section'><summary class='section-summary'>"
        "<span><strong>Question coverage</strong><small>Compare response coverage across survey occurrences.</small></span>"
        f"<span id='coverage-count' class='section-count'>{len(coverage_groups)} canonical questions</span></summary>"
        f"<div class='section-body'>{''.join(coverage_groups)}</div></details></div></details></section>",
    ))
