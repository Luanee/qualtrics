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
    if not field.get("is_text_field"):
        return label

    suffix = str(field.get("source_field_suffix") or "")
    option_match = re.fullmatch(r"(.+)_TEXT", suffix, flags=re.IGNORECASE)
    if option_match:
        option = answer_options.get((str(field.get("survey_id")), str(field.get("question_id")), option_match.group(1)))
        if option and option.get("answer_text"):
            label = str(option["answer_text"])
    label = re.sub(r"\s*-\s*Text\s*$", "", label, flags=re.IGNORECASE).strip()
    question_text = str(question.get("question_text") or "")
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
        f"<option value='{html.escape(str(item['survey_id']), quote=True)}' "
        f"data-responses='{survey_response_counts.get(str(item['survey_id']), 0)}' "
        f"data-finished='{survey_finished_counts.get(str(item['survey_id']), 0)}' "
        f"data-questions='{survey_question_counts.get(str(item['survey_id']), 0)}' "
        f"data-answers='{survey_answer_counts.get(str(item['survey_id']), 0)}' "
        f"data-unanswered='{survey_unanswered_counts.get(str(item['survey_id']), 0)}' "
        f"data-unused-fields='{survey_unused_field_counts.get(str(item['survey_id']), 0)}'>"
        f"{html.escape(str(item.get('survey_name') or item['survey_id']))}</option>"
        for item in entities.surveys
    )
    question_choices = []
    coverage_rows = []
    for key, question in response_questions.items():
        question_id = question["question_id"]
        survey_id = str(key[0])
        question_token = f"{survey_id}::{question_id}"
        label = str(question.get("question_text") or question_id)
        block_name = str(question.get("block_name") or "")
        choice_label = html.escape(label)
        if len(entities.surveys) > 1:
            choice_label += (
                f"<em>{html.escape(str(survey_lookup.get(survey_id, {}).get('survey_name') or survey_id))}</em>"
            )
        count = len(question_responses.get(key, set()))
        question_response_total = survey_response_counts.get(survey_id, 0)
        rate = round((count / question_response_total * 100) if question_response_total else 0)
        question_choices.append(
            f"<label data-survey='{html.escape(survey_id, quote=True)}'><input class='question-choice' "
            f"type='checkbox' value='{html.escape(question_token, quote=True)}' "
            f"checked><span>{choice_label}</span><small>{count}/{question_response_total}</small></label>"
        )
        coverage_rows.append(
            f"<tr data-survey='{html.escape(survey_id, quote=True)}'><td><strong>{html.escape(label)}</strong>"
            f"<small>{html.escape(question_id)}"
            f"{f' · {html.escape(block_name)}' if block_name else ''}"
            "</small></td>"
            f"<td>{count:,}</td><td><div class='meter'><i style='width:{rate}%'></i></div>{rate}%</td></tr>"
        )

    def issue_list(items: list[dict[str, Any]], label_key: str, empty: str) -> str:
        if not items:
            return f"<p class='meta'>{empty}</p>"
        labels = [str(item.get(label_key) or item.get("question_id") or "Unknown") for item in items]
        preview = "".join(f"<li>{html.escape(label)}</li>" for label in labels[:8])
        remaining = f"<li>…and {len(labels) - 8} more</li>" if len(labels) > 8 else ""
        return f"<ul>{preview}{remaining}</ul>"

    quality_panels = []
    for survey_id, survey in survey_lookup.items():
        quality_groups = [
            (
                "Questions without responses",
                [item for item in unanswered_questions if str(item["survey_id"]) == survey_id],
                "question_text",
            ),
            (
                "Fields without values",
                [item for item in unused_fields if str(item["survey_id"]) == survey_id],
                "field_text",
            ),
            (
                "Defined options not observed",
                [item for item in unused_options if str(item["survey_id"]) == survey_id],
                "answer_text",
            ),
        ]
        quality_html = "".join(
            f"<div class='quality-group'><strong>{html.escape(title)}</strong>{issue_list(items, label_key, '')}</div>"
            for title, items, label_key in quality_groups
            if items
        )
        if not quality_html:
            quality_html = (
                "<div class='healthy'><strong>No coverage gaps detected</strong>"
                "<span>Every response question and concrete field has data.</span></div>"
            )
        survey_label = str(survey.get("survey_name") or survey_id)
        quality_panels.append(
            f"<div class='quality' data-survey='{html.escape(survey_id, quote=True)}'>"
            "<div class='quality-head'><i></i><strong>Data quality"
            f"{f' · {html.escape(survey_label)}' if len(entities.surveys) > 1 else ''}</strong></div>"
            f"<div class='quality-groups'>{quality_html}</div></div>"
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

    question_analytics = []
    categorical_types = {"MC", "MATRIX", "SBS", "DD", "DRILLDOWN", "RO", "RANKORDER"}
    numeric_types = {"SLIDER", "CS", "CONSTANTSUM"}
    for key, question in response_questions.items():
        question_id = str(question["question_id"])
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
        question_analytics.append(
            f"<details class='question-analysis' data-survey='{html.escape(str(key[0]), quote=True)}' "
            f"data-question='{html.escape(question_id)}'>"
            f"<summary><span class='analysis-title'>{html.escape(label)}<small>{html.escape(question_id)}"
            f" · {html.escape(type_label)}{f' · {html.escape(selector)}' if selector else ''}"
            f"{f' · Block: {html.escape(block_label)}' if block_label else ''}</small></span>"
            f"<span class='analysis-summary'>{summary}</span></summary>"
            f"<div class='analysis-body'>{analysis_body}</div></details>"
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
        "<main class='shell'><div class='survey-switcher'><label for='survey-select'>Survey</label>"
        f"<select id='survey-select'><option value='' data-responses='{response_count}' "
        f"data-finished='{finished_count}' data-questions='{len(response_questions)}' "
        f"data-answers='{content_answer_count}' data-unanswered='{len(unanswered_questions)}' "
        f"data-unused-fields='{len(unused_fields)}'>All surveys</option>{survey_options}</select></div>"
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
        "<div class='panel'><h3>Question coverage</h3><table><thead><tr><th>Question</th>"
        f"<th>Responses</th><th>Coverage</th></tr></thead><tbody>{''.join(coverage_rows)}</tbody></table></div>"
        "</section><section id='question-analytics'><h2>Question analytics</h2>"
        "<p class='section-intro'>Answer patterns summarized according to each question type. "
        "Expand a question to inspect its fields and distributions.</p>"
        f"{''.join(question_analytics)}</section><section id='by-responses'><h2>By responses</h2>"
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
            str(response["response_id"]),
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
                field_rows.append(
                    f"<div class='field-answer{text_class}'><span class='field'>{html.escape(field_label)}</span>"
                    f"<span class='value'>{html.escape(str(answer['answer_text']))}</span></div>"
                )
            question_meta = " · ".join(
                item for item in (type_label, f"Block: {block_name}" if block_name else "") if item
            )
            rows.append(
                f"<div class='answer' data-question='"
                f"{html.escape(f'{response_survey_id}::{question_id}', quote=True)}'>"
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
            f"<summary><span class='identity'>{html.escape(str(response['response_id']))}</span>"
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
