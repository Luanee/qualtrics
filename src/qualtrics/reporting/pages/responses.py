# ruff: noqa: E501 -- HTML markup
from __future__ import annotations

import html
from typing import Any

from ..components.controls import render_question_choices
from ..components.field_labels import display_field_label
from ..components.primitives import page_heading
from ..context import ReportContext


def render_responses(context: ReportContext) -> str:
    questions = context.analysis.questions
    fields = context.analysis.fields
    answers = context.analysis.answers
    survey_lookup = context.analysis.survey_lookup
    question_roles = context.analysis.question_roles
    entities = context.entities
    answer_options = context.answer_options
    question_choices = render_question_choices(context)
    parts = [
        f"<section id='by-responses' class='report-view'>{page_heading('Responses', 'Review individual answers and filter to the questions you need.')}",
        "<div class='toolbar'><label for='search'>Search responses</label><input id='search' type='search' "
        "placeholder='Search responses, questions, or answers…'><span id='count'></span>"
        "<div class='filter-wrap'><button id='question-toggle' type='button' aria-expanded='false'>"
        "Questions · <span id='selected-count'>All</span></button><div id='question-menu' "
        "class='question-menu' hidden>"
        "<div class='selector-actions'><button id='select-all' type='button'>Select all</button>"
        "<button id='clear-all' type='button'>Clear</button></div>"
        f"{question_choices}</div></div>"
        "<button id='expand'>Expand all</button><button id='collapse'>Collapse</button></div><div id='response-list'>",
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
                field_label = display_field_label(field_definition, q, answer_options)
                text_class = " text-field" if field_definition.get("is_text_field") else ""
                field_id = html.escape(str(answer["field_id"]), quote=True)
                if field_label:
                    field_rows.append(
                        f"<div class='field-answer{text_class}' data-field-id='{field_id}'><span class='field'>{html.escape(field_label)}</span>"
                        f"<span class='value'>{html.escape(str(answer['answer_text']))}</span></div>"
                    )
                else:
                    field_rows.append(
                        f"<div class='field-answer value-only' data-field-id='{field_id}'><span class='value'>{html.escape(str(answer['answer_text']))}</span></div>"
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
            f"<details class='respondent' id='response-{index + 1}' data-survey='{html.escape(response_survey_id, quote=True)}' "
            f"data-total-answers='{len(rows)}' data-search='{searchable}'{' open' if index == 0 else ''}>"
            f"<summary><span class='identity'>{html.escape(str(response.get('response_external_id') or response['response_id']))}</span>"
            f"<span class='badge'>{len(rows)} answers</span></summary>"
            f"<div class='response-meta'>{''.join(metadata_values)}</div>"
            f"<div class='answers'>{''.join(rows)}"
            "<div class='no-selected' hidden>No selected questions were answered in this response.</div>"
            "</div></details>"
        )
    parts.append(
        "</div><div id='response-pagination' class='pagination'></div><div id='empty' class='empty hidden'>No matching responses.</div></section>"
    )
    return "".join(parts)
