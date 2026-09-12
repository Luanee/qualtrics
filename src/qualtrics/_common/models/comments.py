"""Derive written-answer rows without changing their authoritative source answers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .question_types import classify_question_role, field_value_type, resolve_question_type

if TYPE_CHECKING:
    from .entities import EntitySet

COMMENT_COLUMNS = (
    "response_answer_id",
    "response_id",
    "survey_id",
    "question_id",
    "question_field_id",
    "answer_text",
    "raw_value",
    "user_language",
)


def is_comment_answer(question: dict[str, Any], field: dict[str, Any], answer: dict[str, Any]) -> bool:
    """Select nonblank respondent text using persisted evidence or legacy field types."""
    value = answer.get("answer_text")
    if not isinstance(value, str) or not value.strip():
        return False
    role = question.get("question_role") or classify_question_role(
        {"QuestionType": question.get("question_type"), "Selector": question.get("selector")},
        [str(field.get("import_external_id") or field.get("source_import_id") or "")],
    )
    resolved = resolve_question_type(
        question.get("question_type"), question.get("selector"), question.get("sub_selector")
    )
    if role != "response" or resolved.answer_value_type == "non_response":
        return False
    if (
        question.get("question_type")
        and resolved.answer_value_type not in {"text", "categorical"}
        and resolved.canonical_question_type != "side_by_side"
    ):
        return False
    evidence = field.get("is_comment_field")
    if isinstance(evidence, bool):
        return evidence
    return field_value_type(question, field) == "text"


def build_comments(entities: EntitySet) -> list[dict[str, Any]]:
    """Return fresh comment rows; language is authoritative only on the response."""
    questions = {(str(row.get("survey_id")), str(row.get("question_id"))): row for row in entities.questions}
    fields = {
        (str(row.get("question_id")), str(row.get("question_field_id") or row.get("field_id"))): row
        for row in entities.question_fields
    }
    responses = {(str(row.get("survey_id")), str(row.get("response_id"))): row for row in entities.responses}
    comments = []
    for answer in entities.response_answers:
        question_key = (str(answer.get("survey_id")), str(answer.get("question_id")))
        field_id = answer.get("question_field_id") or answer.get("field_id")
        question = questions.get(question_key)
        field = fields.get((question_key[1], str(field_id)))
        response = responses.get((question_key[0], str(answer.get("response_id"))))
        if question is None or field is None or response is None or not is_comment_answer(question, field, answer):
            continue
        if field.get("survey_id") is not None and str(field["survey_id"]) != question_key[0]:
            continue
        comment = {column: answer.get(column) for column in COMMENT_COLUMNS}
        comment["question_field_id"] = field_id
        comment["user_language"] = response.get("user_language")
        comments.append(comment)
    return comments
