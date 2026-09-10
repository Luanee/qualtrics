"""Survey and question scope controls preserve the shared browser filter contract."""

import html

from ..context import ReportContext


def render_survey_choices(context: ReportContext) -> str:
    survey_response_counts = context.analysis.survey_response_counts
    survey_finished_counts = context.analysis.survey_finished_counts
    survey_answer_counts = context.analysis.survey_answer_counts
    survey_question_counts = context.analysis.survey_question_counts
    survey_unanswered_counts = context.analysis.survey_unanswered_counts
    survey_unused_field_counts = context.analysis.survey_unused_field_counts
    entities = context.entities
    return "".join(
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


def render_question_choices(context: ReportContext) -> str:
    response_questions = context.analysis.response_questions
    survey_lookup = context.analysis.survey_lookup
    question_responses = context.analysis.question_responses
    survey_response_counts = context.analysis.survey_response_counts
    entities = context.entities
    question_choices = []
    for key, question in response_questions.items():
        question_id = str(question["question_id"])
        question_external_id = str(question.get("question_external_id") or question_id)
        survey_id = str(key[0])
        question_token = f"{survey_id}::{question_external_id}"
        label = str(question.get("question_text") or question_id)
        survey_label = str(survey_lookup.get(survey_id, {}).get("survey_name") or survey_id)
        choice_label = html.escape(label)
        if len(entities.surveys) > 1:
            choice_label += f"<em>{html.escape(survey_label)}</em>"
        count = len(question_responses.get(key, set()))
        question_response_total = survey_response_counts.get(survey_id, 0)
        question_choices.append(
            f"<label data-survey='{html.escape(survey_id, quote=True)}'><input class='question-choice' "
            f"type='checkbox' value='{html.escape(question_token, quote=True)}' "
            f"checked><span>{choice_label}</span><small>{count}/{question_response_total}</small></label>"
        )
    return "".join(question_choices)
