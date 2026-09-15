"""Derive written-answer rows without changing their authoritative source answers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .question_types import classify_entity_question_role, field_value_type, resolve_question_type
from .translation_columns import prepared_targets, target_from_column, translation_columns

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
    role = classify_entity_question_role(question, [field])
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
    prepared = {
        str(row.get("response_answer_id")): {
            key: value for key, value in row.items() if target_from_column(key) is not None
        }
        for row in entities.comments
        if row.get("response_answer_id") is not None
    }
    targets = prepared_targets(
        [key for values in prepared.values() for key in values] + list(entities._present_columns.get("comments", set()))
    )
    prepared_columns = [column for target in sorted(targets) for column in translation_columns(target)]
    questions = {(str(row.get("survey_id")), str(row.get("question_id"))): row for row in entities.questions}
    question_fields: dict[tuple[str, str], list[dict[str, Any]]] = {}
    fields = {
        (
            str(row["survey_id"]) if row.get("survey_id") is not None else None,
            str(row.get("question_id")),
            str(row.get("question_field_id") or row.get("field_id")),
        ): row
        for row in entities.question_fields
    }
    for (survey_id, question_id, _), field in fields.items():
        if survey_id is not None:
            question_fields.setdefault((survey_id, question_id), []).append(field)
    question_roles = {
        key: classify_entity_question_role(question, question_fields.get(key, []))
        for key, question in questions.items()
    }
    responses = {(str(row.get("survey_id")), str(row.get("response_id"))): row for row in entities.responses}
    comments = []
    for answer in entities.response_answers:
        question_key = (str(answer.get("survey_id")), str(answer.get("question_id")))
        field_id = answer.get("question_field_id") or answer.get("field_id")
        question = questions.get(question_key)
        field = fields.get((*question_key, str(field_id))) or fields.get((None, question_key[1], str(field_id)))
        response = responses.get((question_key[0], str(answer.get("response_id"))))
        if (
            question is None
            or field is None
            or response is None
            or question_roles.get(question_key) != "response"
            or not is_comment_answer(question, field, answer)
        ):
            continue
        comment = {column: answer.get(column) for column in COMMENT_COLUMNS}
        comment["question_field_id"] = field_id
        comment["user_language"] = response.get("user_language")
        prepared_answer = prepared.get(str(answer.get("response_answer_id")), {})
        comment.update({column: prepared_answer.get(column) for column in prepared_columns})
        comments.append(comment)
    return comments
