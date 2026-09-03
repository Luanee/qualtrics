# ruff: noqa: E501 -- report markup remains readable at natural line lengths
from __future__ import annotations

import contextlib
import html
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..analytics import analyze_entities
from ..models.entities import EntitySet
from .assets import load_asset


def _normalized_label(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def _display_field_label(
    field: dict[str, Any],
    question: dict[str, Any],
    answer_options: dict[tuple[str, str, str], dict[str, Any]],
) -> str:
    label = str(field.get("field_text") or field.get("field_id") or "Answer")
    question_text = str(question.get("question_text") or "")
    if not field.get("is_text_field"):
        if _normalized_label(label) == _normalized_label(question_text):
            return ""
        return label

    suffix = str(field.get("source_field_suffix") or "")
    option_match = re.fullmatch(r"(.+)_TEXT", suffix, flags=re.IGNORECASE)
    if option_match:
        option = answer_options.get((str(field.get("survey_id")), str(field.get("question_id")), option_match.group(1)))
        if option and option.get("answer_text"):
            label = str(option["answer_text"])
    label = re.sub(r"\s*-\s*Text\s*$", "", label, flags=re.IGNORECASE).strip()
    if not label or _normalized_label(label) == _normalized_label(question_text):
        return "Written response"
    return label


def render_report(entities: EntitySet, output: str | Path) -> None:
    analysis = analyze_entities(entities)
    questions = analysis.questions
    fields = analysis.fields
    answers = analysis.answers
    survey_lookup = analysis.survey_lookup
    survey_name = analysis.survey_name
    question_roles = analysis.question_roles
    response_questions = analysis.response_questions
    question_responses = analysis.question_responses
    question_answers = analysis.question_answers
    answer_options = {
        (str(option["survey_id"]), str(option["question_id"]), str(option["answer_id"])): option
        for option in entities.answer_options
    }
    question_options: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for option in entities.answer_options:
        question_options.setdefault((str(option["survey_id"]), str(option["question_id"])), []).append(option)
    unanswered_questions = analysis.unanswered_questions
    unused_fields = analysis.unused_fields
    unused_options = analysis.unused_options
    response_count = analysis.response_count
    content_answer_count = analysis.content_answer_count
    finished_count = analysis.finished_count
    survey_response_counts = analysis.survey_response_counts
    survey_finished_counts = analysis.survey_finished_counts
    survey_answer_counts = analysis.survey_answer_counts
    survey_question_counts = analysis.survey_question_counts
    survey_unanswered_counts = analysis.survey_unanswered_counts
    survey_unused_field_counts = analysis.survey_unused_field_counts
    survey_options = "".join(
        f"<label><input class='survey-choice' type='checkbox' "
        f"value='{html.escape(str(item['survey_id']), quote=True)}' checked "
        f"data-responses='{survey_response_counts.get(str(item['survey_id']), 0)}' "
        f"data-finished='{survey_finished_counts.get(str(item['survey_id']), 0)}' "
        f"data-questions='{survey_question_counts.get(str(item['survey_id']), 0)}' "
        f"data-answers='{survey_answer_counts.get(str(item['survey_id']), 0)}' "
        f"data-unanswered='{survey_unanswered_counts.get(str(item['survey_id']), 0)}' "
        f"data-unused-fields='{survey_unused_field_counts.get(str(item['survey_id']), 0)}'>"
        f"<span>{html.escape(str(item.get('survey_name') or item['survey_id']))}</span></label>"
        for item in entities.surveys
    )
    question_catalog_lookup = {str(item["question_catalog_id"]): item for item in entities.question_catalog}
    question_choices = []
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
        choice_label = html.escape(label)
        if len(entities.surveys) > 1:
            choice_label += f"<em>{html.escape(survey_label)}</em>"
        count = len(question_responses.get(key, set()))
        question_response_total = survey_response_counts.get(survey_id, 0)
        rate = round((count / question_response_total * 100) if question_response_total else 0)
        question_choices.append(
            f"<label data-survey='{html.escape(survey_id, quote=True)}'><input class='question-choice' "
            f"type='checkbox' value='{html.escape(question_token, quote=True)}' "
            f"checked><span>{choice_label}</span><small>{count}/{question_response_total}</small></label>"
        )
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
                "<div class='quality-question'>"
                f"<strong>{html.escape(question_label)}</strong><small>{html.escape(metadata)}</small>"
                f"<ul>{labels}</ul></div>"
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

    def distribution(values: list[str], denominator: int) -> str:
        counts = Counter(values)
        rows = []
        for value, count in counts.most_common(12):
            rate = count / denominator * 100 if denominator else 0
            rows.append(
                f"<div class='distribution-row'><span title='{html.escape(value, quote=True)}'>"
                f"{html.escape(value)}</span><div class='distribution-bar'><i style='width:{rate:.1f}%'></i>"
                f"</div><b>{count:,}</b><small>{rate:.0f}%</small></div>"
            )
        hidden_count = sum(counts.values()) - sum(count for _, count in counts.most_common(12))
        if hidden_count:
            rows.append(f"<p class='meta'>Other values: {hidden_count:,}</p>")
        return "".join(rows) or "<p class='meta'>No values observed.</p>"

    def option_distribution(
        observed_answers: list[dict[str, Any]],
        defined_options: list[dict[str, Any]],
        denominator: int,
    ) -> str:
        aliases = {
            str(alias).casefold(): str(option["answer_id"])
            for option in defined_options
            for alias in (option["answer_id"], option["answer_text"])
        }
        labels = {str(option["answer_id"]): str(option["answer_text"]) for option in defined_options}
        selections: set[tuple[str, str]] = set()
        unknown_labels: dict[str, str] = {}
        for answer in observed_answers:
            raw_value = str(answer["answer_text"])
            option_id = aliases.get(raw_value.casefold())
            if option_id is None:
                option_id = f"unknown:{raw_value.casefold()}"
                unknown_labels.setdefault(option_id, raw_value)
            selections.add((str(answer["response_id"]), option_id))
        counts = Counter(option_id for _, option_id in selections)
        option_ids = [str(option["answer_id"]) for option in defined_options]
        option_ids.extend(
            option_id for option_id, _ in sorted(unknown_labels.items(), key=lambda item: item[1].casefold())
        )
        rows = []
        for option_id in option_ids:
            label = labels.get(option_id) or unknown_labels[option_id]
            count = counts[option_id]
            rate = count / denominator * 100 if denominator else 0
            zero_class = " option-zero" if not count else ""
            rows.append(
                f"<div class='distribution-row option-row{zero_class}'><span title='{html.escape(label, quote=True)}'>"
                f"{html.escape(label)}</span><div class='distribution-bar'><i style='width:{min(rate, 100):.1f}%'></i>"
                f"</div><b>{count:,}</b><small>{rate:.0f}%</small></div>"
            )
        return "".join(rows) or "<p class='meta'>No answer options defined or observed.</p>"

    analytics_by_catalog: dict[str, dict[str, Any]] = {}
    categorical_types = {"MC", "MATRIX", "SBS", "DD", "DRILLDOWN", "RO", "RANKORDER"}
    numeric_types = {"SLIDER", "CS", "CONSTANTSUM"}
    for key, question in response_questions.items():
        question_id = str(question["question_id"])
        question_external_id = str(question.get("question_external_id") or question_id)
        label = str(question.get("question_text") or question_id)
        question_type = str(question.get("question_type") or "Unknown").upper()
        selector = str(question.get("selector") or "")
        observed = question_answers.get(key, [])
        respondent_count = len(question_responses.get(key, set()))
        question_response_total = survey_response_counts.get(str(key[0]), 0)
        coverage = respondent_count / question_response_total * 100 if question_response_total else 0
        field_groups: dict[str, list[str]] = {}
        answers_by_field: dict[str, list[dict[str, Any]]] = {}
        for answer in observed:
            field_id = str(answer["field_id"])
            field_groups.setdefault(field_id, []).append(str(answer["answer_text"]))
            answers_by_field.setdefault(field_id, []).append(answer)
        categorical_observed = [
            answer
            for answer in observed
            if not fields.get((key[0], key[1], str(answer["field_id"])), {}).get("is_text_field")
        ]
        value_count = len(categorical_observed) if question_type == "MC" else len(observed)
        value_label = "selections" if question_type == "MC" else "values"
        summary = (
            f"<span><b>{respondent_count:,}</b> respondents</span>"
            f"<span><b>{coverage:.0f}%</b> coverage</span>"
            f"<span><b>{value_count:,}</b> {value_label}</span>"
        )
        bodies = []
        if question_type == "MC":
            defined_options = question_options.get(key, [])
            choice_field_ids = [
                field_id
                for field_id in field_groups
                if not fields.get((key[0], key[1], field_id), {}).get("is_text_field")
            ]
            if selector.upper().startswith("MA"):
                bodies.append(
                    "<div class='field-analysis option-analysis'>"
                    + option_distribution(categorical_observed, defined_options, respondent_count)
                    + "</div>"
                )
            else:
                for field_id in choice_field_ids:
                    field_definition = fields.get((key[0], key[1], field_id), {})
                    field_label = _display_field_label(field_definition, question, answer_options)
                    heading = f"<h4>{html.escape(field_label)}</h4>" if len(choice_field_ids) > 1 else ""
                    bodies.append(
                        f"<div class='field-analysis option-analysis'>{heading}"
                        f"{option_distribution(answers_by_field[field_id], defined_options, respondent_count)}</div>"
                    )
            for field_id, values in field_groups.items():
                field_definition = fields.get((key[0], key[1], field_id), {})
                if not field_definition.get("is_text_field"):
                    continue
                field_label = _display_field_label(field_definition, question, answer_options)
                content = (
                    f"<p class='meta'>{len(values):,} written responses · {len(set(values)):,} unique. "
                    "Most frequent values:</p>" + distribution(values, len(values))
                )
                bodies.append(
                    f"<div class='field-analysis text-analysis'><h4>{html.escape(field_label)}</h4>{content}</div>"
                )
        elif question_type == "TE":
            for field_id, values in field_groups.items():
                numeric_values = []
                for value in values:
                    with contextlib.suppress(ValueError):
                        numeric_values.append(float(value.replace(",", "")))
                field_definition = fields.get((key[0], key[1], field_id), {})
                field_label = _display_field_label(field_definition, question, answer_options)
                heading = f"<h4>{html.escape(str(field_label))}</h4>" if len(field_groups) > 1 else ""
                if values and len(numeric_values) / len(values) >= 0.8:
                    content = (
                        "<div class='numeric-summary'>"
                        f"<span><b>{min(numeric_values):g}</b> Minimum</span>"
                        f"<span><b>{sum(numeric_values) / len(numeric_values):.1f}</b> Average</span>"
                        f"<span><b>{max(numeric_values):g}</b> Maximum</span></div>"
                    )
                else:
                    content = (
                        f"<p class='meta'>{len(set(values)):,} unique text answers. Most frequent values:</p>"
                        + distribution(values, len(values))
                    )
                bodies.append(f"<div class='field-analysis'>{heading}{content}</div>")
        elif question_type in numeric_types:
            for field_id, values in field_groups.items():
                numeric_values = []
                for value in values:
                    with contextlib.suppress(ValueError):
                        numeric_values.append(float(value.replace(",", "")))
                field_definition = fields.get((key[0], key[1], field_id), {})
                field_label = _display_field_label(field_definition, question, answer_options)
                if numeric_values:
                    bodies.append(
                        f"<div class='field-analysis'><h4>{html.escape(str(field_label))}</h4>"
                        f"<div class='numeric-summary'><span><b>{min(numeric_values):g}</b> Minimum</span>"
                        f"<span><b>{sum(numeric_values) / len(numeric_values):.1f}</b> Average</span>"
                        f"<span><b>{max(numeric_values):g}</b> Maximum</span></div></div>"
                    )
        else:
            for field_id, values in field_groups.items():
                field_definition = fields.get((key[0], key[1], field_id), {})
                field_label = _display_field_label(field_definition, question, answer_options)
                show_field = len(field_groups) > 1 or question_type in categorical_types
                heading = f"<h4>{html.escape(str(field_label))}</h4>" if show_field else ""
                bodies.append(f"<div class='field-analysis'>{heading}{distribution(values, len(values))}</div>")
        type_label = {"MC": "Multiple choice", "TE": "Text entry"}.get(
            question_type, question_type.replace("_", " ").title()
        )
        block_label = str(question.get("block_name") or "")
        analysis_body = "".join(bodies) or '<p class="meta">No values observed.</p>'
        survey_id = str(key[0])
        survey_label = str(survey_lookup.get(survey_id, {}).get("survey_name") or survey_id)
        catalog_id = str(question.get("question_catalog_id") or f"{survey_id}::{question_id}")
        catalog_label = str(question_catalog_lookup.get(catalog_id, {}).get("question_text") or label)
        occurrence_metadata = f"Import ID: {question_external_id} · {type_label}"
        if selector:
            occurrence_metadata += f" · {selector}"
        if block_label:
            occurrence_metadata += f" · Section: {block_label}"
        occurrence = (
            f"<details class='survey-analysis survey-occurrence' data-survey='{html.escape(survey_id, quote=True)}' "
            f"data-question='{html.escape(question_external_id)}'>"
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

    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{html.escape(survey_name)} · Response report</title>",
        f"<style>{load_asset('report.css')}</style></head><body>",
        f"<header><div class='shell'><small>RESPONSE REPORT</small><h1>{html.escape(survey_name)}</h1>"
        "<p>Search, review, expand, or print individual survey responses.</p></div></header>",
        "<div class='shell stats'>"
        f"<div class='stat'><strong id='stat-responses'>{len(entities.responses):,}</strong><span>Responses</span></div>"
        f"<div class='stat'><strong id='stat-questions'>{len(response_questions):,}</strong><span>Response questions</span></div>"
        f"<div class='stat'><strong id='stat-answers'>{content_answer_count:,}</strong><span>Respondent answers</span></div></div>",
        "<main class='shell'><div class='survey-switcher'><strong>Surveys</strong>"
        "<div class='survey-filter filter-wrap'><button id='survey-toggle' type='button' aria-expanded='false'>"
        "Surveys · <span id='survey-selected-count'>All</span></button><div id='survey-menu' "
        "class='survey-menu' hidden><div class='selector-actions'>"
        "<button id='survey-select-all' type='button'>Select all</button>"
        f"<button id='survey-clear' type='button'>Clear</button></div>{survey_options}</div></div></div>"
        "<nav><a href='#overview'>Overview</a>"
        "<a href='#question-analytics'>Question analytics</a>"
        "<a href='#by-responses'>By responses</a></nav>",
        "<section id='overview'><h2>Overview</h2><p class='section-intro'>Coverage, completion, "
        "and data-quality signals across this survey.</p><div class='analytics'>"
        f"<div class='analytic'><strong id='overview-finished'>{finished_count:,}</strong><span>Finished responses</span></div>"
        f"<div class='analytic'><strong id='overview-completion'>{(finished_count / response_count * 100 if response_count else 0):.0f}%</strong>"
        "<span>Completion rate</span></div>"
        f"<div class='analytic'><strong id='overview-unanswered'>{len(unanswered_questions):,}</strong><span>Unanswered questions</span></div>"
        f"<div class='analytic'><strong id='overview-unused-fields'>{len(unused_fields):,}</strong><span>Unused fields</span></div></div>",
        f"{''.join(quality_panels)}",
        "<details id='question-coverage' class='panel report-section'><summary class='section-summary'>"
        "<span><strong>Question coverage</strong><small>Compare response coverage across survey occurrences.</small></span>"
        f"<span id='coverage-count' class='section-count'>{len(coverage_groups)} canonical questions</span></summary>"
        f"<div class='section-body'>{''.join(coverage_groups)}</div></details></section>"
        "<details id='question-analytics' class='report-section'><summary class='section-summary'>"
        "<span><strong>Question analytics</strong><small>Type-aware answer patterns grouped across surveys.</small></span>"
        f"<span id='analytics-count' class='section-count'>{len(question_analytics)} canonical questions</span></summary>"
        f"<div class='section-body'>{''.join(question_analytics)}</div></details>"
        "<section id='by-responses'><h2>By responses</h2>"
        "<p class='section-intro'>Review individual answers and filter to the questions you need.</p>",
        "<div class='toolbar'><input id='search' type='search' "
        "placeholder='Search responses, questions, or answers…'><span id='count'></span>"
        "<div class='filter-wrap'><button id='question-toggle' type='button' aria-expanded='false'>"
        "Questions · <span id='selected-count'>All</span></button><div id='question-menu' "
        "class='question-menu' hidden>"
        "<div class='selector-actions'><button id='select-all' type='button'>Select all</button>"
        "<button id='clear-all' type='button'>Clear</button></div>"
        f"{''.join(question_choices)}</div></div>"
        "<button id='expand'>Expand all</button><button id='collapse'>Collapse</button></div>",
    ]
    for index, response in enumerate(entities.responses):
        key = (response["survey_id"], response["response_id"])
        response_survey_id = str(response["survey_id"])
        response_survey_name = str(survey_lookup.get(response_survey_id, {}).get("survey_name") or response_survey_id)
        response_answers = answers.get(key, [])
        stable_metadata = [
            ("Browser", response.get("browser")),
            ("Version", response.get("browser_version")),
            ("Operating System", response.get("operating_system")),
            ("Resolution", response.get("screen_resolution")),
            ("User Agent", response.get("user_agent")),
        ]
        search_terms = [
            str(response.get("response_external_id") or response["response_id"]),
            *(str(value) for _, value in stable_metadata if value),
        ]
        rows = []
        metadata_values = [
            f"<span><b>{html.escape(label)}</b> {html.escape(str(value))}</span>"
            for label, value in stable_metadata
            if value
        ]
        grouped_response_answers: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
        for answer in response_answers:
            q = questions.get((answer["survey_id"], answer["question_id"]), {})
            f = fields.get((answer["survey_id"], answer["question_id"], answer["field_id"]), {})
            label = q.get("question_text") or answer["question_id"]
            field_label = f.get("field_text")
            search_terms.extend((str(label), str(field_label or ""), str(answer["answer_text"])))
            question_key = (answer["survey_id"], answer["question_id"])
            if question_roles.get(question_key, "response") != "response":
                metadata_label = field_label or label
                metadata_values.append(
                    f"<span><b>{html.escape(str(metadata_label))}</b> {html.escape(str(answer['answer_text']))}</span>"
                )
                continue
            grouped_response_answers.setdefault(str(answer["question_id"]), []).append((answer, f))
        for question_id, grouped_answers in grouped_response_answers.items():
            first_answer = grouped_answers[0][0]
            q = questions.get((first_answer["survey_id"], question_id), {})
            question_external_id = str(q.get("question_external_id") or question_id)
            label = q.get("question_text") or question_id
            question_type = str(q.get("question_type") or "").upper()
            type_label = {"MC": "Multiple choice", "TE": "Text entry"}.get(
                question_type, question_type.replace("_", " ").title()
            )
            block_name = str(q.get("block_name") or "")
            field_rows = []
            for answer, field_definition in grouped_answers:
                field_label = _display_field_label(field_definition, q, answer_options)
                text_class = " text-field" if field_definition.get("is_text_field") else ""
                if field_label:
                    field_rows.append(
                        f"<div class='field-answer{text_class}'><span class='field'>{html.escape(field_label)}</span>"
                        f"<span class='value'>{html.escape(str(answer['answer_text']))}</span></div>"
                    )
                else:
                    field_rows.append(
                        "<div class='field-answer value-only'>"
                        f"<span class='value'>{html.escape(str(answer['answer_text']))}</span></div>"
                    )
            question_meta = " · ".join(
                item for item in (type_label, f"Block: {block_name}" if block_name else "") if item
            )
            rows.append(
                f"<div class='answer' data-question='"
                f"{html.escape(f'{response_survey_id}::{question_external_id}', quote=True)}'>"
                f"<div class='question-head'><span class='question'>{html.escape(str(label))}</span>"
                f"<span class='question-meta'>{html.escape(question_meta)}</span></div>"
                f"{''.join(field_rows)}</div>"
            )
        searchable = html.escape(" ".join(search_terms).casefold(), quote=True)
        metadata_parts = [
            value
            for value in (
                f"Recorded {response.get('recorded_at')}" if response.get("recorded_at") else "",
                f"Language {response.get('user_language')}" if response.get("user_language") else "",
                "Finished" if str(response.get("is_finished", "")).casefold() in {"true", "1"} else "",
            )
            if value
        ]
        metadata_values.insert(0, f"<span>{html.escape(' · '.join(metadata_parts))}</span>")
        if len(entities.surveys) > 1:
            metadata_values.insert(0, f"<span><b>Survey</b> {html.escape(response_survey_name)}</span>")
        parts.append(
            f"<details class='respondent' data-survey='{html.escape(response_survey_id, quote=True)}' "
            f"data-total-answers='{len(rows)}' data-search='{searchable}'{' open' if index == 0 else ''}>"
            f"<summary><span class='identity'>{html.escape(str(response.get('response_external_id') or response['response_id']))}</span>"
            f"<span class='badge'>{len(rows)} answers</span></summary>"
            f"<div class='response-meta'>{''.join(metadata_values)}</div>"
            f"<div class='answers'>{''.join(rows)}"
            "<div class='no-selected' hidden>No selected questions were answered in this response.</div>"
            "</div></details>"
        )
    parts.append(
        "<div id='empty' class='empty hidden'>No matching responses.</div></section></main>"
        + "<script>"
        + load_asset("report.js")
        + "</script></body></html>"
    )
    Path(output).write_text("".join(parts), encoding="utf-8")
