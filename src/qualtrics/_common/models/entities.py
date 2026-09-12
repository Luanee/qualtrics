from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CORE_ENTITY_NAMES = (
    "surveys",
    "sections",
    "question_catalog",
    "question_field_catalog",
    "questions",
    "answer_options",
    "question_fields",
    "responses",
    "response_answers",
)
ENTITY_NAMES = (*CORE_ENTITY_NAMES, "comments")


@dataclass
class EntitySet:
    _present_entities: set[str] = field(default_factory=set, repr=False, compare=False)
    _present_columns: dict[str, set[str]] = field(default_factory=dict, repr=False, compare=False)
    surveys: list[dict[str, Any]] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    question_catalog: list[dict[str, Any]] = field(default_factory=list)
    question_field_catalog: list[dict[str, Any]] = field(default_factory=list)
    questions: list[dict[str, Any]] = field(default_factory=list)
    answer_options: list[dict[str, Any]] = field(default_factory=list)
    question_fields: list[dict[str, Any]] = field(default_factory=list)
    responses: list[dict[str, Any]] = field(default_factory=list)
    response_answers: list[dict[str, Any]] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)
