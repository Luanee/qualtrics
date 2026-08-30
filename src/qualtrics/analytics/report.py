from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from ..models import EntitySet
from ..parsers.identity import _question_role

QuestionKey = tuple[str, str]
FieldKey = tuple[str, str, str]
Row = dict[str, Any]


@dataclass(frozen=True)
class ReportAnalytics:
    questions: dict[QuestionKey, Row]
    fields: dict[FieldKey, Row]
    answers: dict[QuestionKey, list[Row]]
    survey_lookup: dict[str, Row]
    survey_name: str
    question_roles: dict[QuestionKey, str]
    response_questions: dict[QuestionKey, Row]
    question_responses: dict[QuestionKey, set[str]]
    question_answers: dict[QuestionKey, list[Row]]
    unanswered_questions: list[Row]
    unused_fields: list[Row]
    unused_options: list[Row]
    response_count: int
    content_answer_count: int
    finished_count: int
    survey_response_counts: Counter[str]
    survey_finished_counts: Counter[str]
    survey_answer_counts: Counter[str]
    survey_question_counts: Counter[str]
    survey_unanswered_counts: Counter[str]
    survey_unused_field_counts: Counter[str]


def analyze_entities(entities: EntitySet) -> ReportAnalytics:
    """Calculate report metrics independently from HTML presentation."""
    questions = {
        (str(question["survey_id"]), str(question["question_id"])): question for question in entities.questions
    }
    fields = {
        (str(field["survey_id"]), str(field["question_id"]), str(field["field_id"])): field
        for field in entities.question_fields
    }
    answers: dict[QuestionKey, list[Row]] = {}
    for answer in entities.response_answers:
        answers.setdefault((str(answer["survey_id"]), str(answer["response_id"])), []).append(answer)
    survey_lookup = {str(item["survey_id"]): item for item in entities.surveys}
    survey_name = (
        str(entities.surveys[0].get("survey_name") or "Qualtrics survey")
        if len(entities.surveys) == 1
        else "Qualtrics survey collection"
    )
    question_roles = {
        key: str(
            question.get("question_role")
            or _question_role(
                question,
                [str(item.get("source_import_id") or "") for field_key, item in fields.items() if field_key[:2] == key],
            )
        )
        for key, question in questions.items()
    }
    response_questions = {key: question for key, question in questions.items() if question_roles[key] == "response"}
    question_responses: dict[QuestionKey, set[str]] = {key: set() for key in response_questions}
    question_answers: dict[QuestionKey, list[Row]] = {key: [] for key in response_questions}
    used_fields: set[FieldKey] = set()
    used_values: dict[QuestionKey, set[str]] = {}
    for answer in entities.response_answers:
        question_key = (str(answer["survey_id"]), str(answer["question_id"]))
        if question_roles.get(question_key, "response") != "response":
            continue
        question_responses.setdefault(question_key, set()).add(str(answer["response_id"]))
        question_answers.setdefault(question_key, []).append(answer)
        used_fields.add((*question_key, str(answer["field_id"])))
        used_values.setdefault(question_key, set()).add(str(answer["answer_text"]).casefold())
    unanswered_questions = [question for key, question in response_questions.items() if not question_responses.get(key)]
    unused_fields = [
        item
        for key, item in fields.items()
        if question_roles.get(key[:2], "response") == "response" and key not in used_fields
    ]
    unused_options = [
        option
        for option in entities.answer_options
        if question_roles.get((str(option["survey_id"]), str(option["question_id"])), "response") == "response"
        and str(option["answer_id"]).casefold()
        not in used_values.get((str(option["survey_id"]), str(option["question_id"])), set())
        and str(option["answer_text"]).casefold()
        not in used_values.get((str(option["survey_id"]), str(option["question_id"])), set())
    ]
    survey_response_counts = Counter(str(item["survey_id"]) for item in entities.responses)
    survey_finished_counts = Counter(
        str(item["survey_id"])
        for item in entities.responses
        if str(item.get("is_finished", "")).casefold() in {"true", "1"}
    )
    survey_answer_counts = Counter(
        survey_id
        for survey_id, _, _ in {
            (str(item["survey_id"]), str(item["response_id"]), str(item["question_id"]))
            for item in entities.response_answers
            if question_roles.get((str(item["survey_id"]), str(item["question_id"])), "response") == "response"
        }
    )
    content_answer_count = sum(survey_answer_counts.values())
    finished_count = sum(survey_finished_counts.values())
    return ReportAnalytics(
        questions=questions,
        fields=fields,
        answers=answers,
        survey_lookup=survey_lookup,
        survey_name=survey_name,
        question_roles=question_roles,
        response_questions=response_questions,
        question_responses=question_responses,
        question_answers=question_answers,
        unanswered_questions=unanswered_questions,
        unused_fields=unused_fields,
        unused_options=unused_options,
        response_count=len(entities.responses),
        content_answer_count=content_answer_count,
        finished_count=finished_count,
        survey_response_counts=survey_response_counts,
        survey_finished_counts=survey_finished_counts,
        survey_answer_counts=survey_answer_counts,
        survey_question_counts=Counter(str(key[0]) for key in response_questions),
        survey_unanswered_counts=Counter(str(item["survey_id"]) for item in unanswered_questions),
        survey_unused_field_counts=Counter(str(item["survey_id"]) for item in unused_fields),
    )
