# ruff: noqa: E501 -- HTML markup
from __future__ import annotations

import html

from ..components.field_labels import display_field_label
from ..components.primitives import empty_state, page_heading, pagination, search_control
from ..context import ReportContext
from ..insights import field_value_type


def render_written_answers(context: ReportContext) -> str:
    questions = context.analysis.questions
    fields = context.analysis.fields
    answers = context.analysis.answers
    survey_lookup = context.analysis.survey_lookup
    response_questions = context.analysis.response_questions
    entities = context.entities
    answer_options = context.answer_options
    written_answers = []
    written_questions: dict[str, tuple[str, str]] = {}
    for response_index, response in enumerate(entities.responses, 1):
        for answer in answers.get((response["survey_id"], response["response_id"]), []):
            key = (answer["survey_id"], answer["question_id"])
            if key not in response_questions:
                continue
            question = questions.get(key, {})
            field = fields.get((*key, answer["field_id"]), {})
            if field_value_type(question, field) != "text":
                continue
            survey_id = str(response["survey_id"])
            label = str(question.get("question_text") or answer["question_id"])
            token = f"{survey_id}::{question.get('question_external_id') or answer['question_id']}"
            written_questions[token] = (label, survey_id)
            field_label = display_field_label(field, question, answer_options)
            metadata = " · ".join(
                item
                for item in (str(survey_lookup.get(survey_id, {}).get("survey_name") or survey_id), field_label)
                if item
            )
            written_answers.append(
                f"<article class='written-answer' id='written-{len(written_answers) + 1}' "
                f"data-survey='{html.escape(survey_id, quote=True)}' data-question-token='{html.escape(token, quote=True)}' "
                f"data-response-target='response-{response_index}' "
                f"data-field-id='{html.escape(str(answer['field_id']), quote=True)}'>"
                f"<h3 class='written-question'>{html.escape(label)}</h3><small>{html.escape(metadata)}</small>"
                f"<p class='written-value'>{html.escape(str(answer['answer_text']))}</p>"
                f"<a href='#response-{response_index}'>Response {html.escape(str(response.get('response_external_id') or response['response_id']))}</a></article>"
            )
    written_options = "".join(
        f"<option value='{html.escape(token, quote=True)}' data-survey='{html.escape(survey_id, quote=True)}' "
        f"data-label='{html.escape(label, quote=True)}'>{html.escape(label)}</option>"
        for token, (label, survey_id) in written_questions.items()
    )

    return (
        f"<section id='written-answers' class='report-view'>{page_heading('Written answers', 'Read text responses and open the full response for context.')}"
        f"<div class='toolbar'>{search_control('written-search', 'Search written answers')}"
        "<label for='written-question'>Question</label><select id='written-question'><option value=''>All questions</option>"
        f"{written_options}</select><span id='written-count' role='status'>{len(written_answers):,} written answers</span></div>"
        f"<div id='written-list'>{''.join(written_answers)}</div>"
        f"{empty_state('written-empty', 'No written answers in the selected surveys.', hidden=bool(written_answers))}"
        f"{pagination('written-pagination')}</section>"
    )
