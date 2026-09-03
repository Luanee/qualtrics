from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .entities import EntitySet
from .entity_set import validate_entity_set

SEMANTIC_TABLE_NAMES = (
    "fact_responses",
    "fact_response_answers",
    "dim_surveys",
    "dim_questions",
    "dim_answer_options",
)


@dataclass
class SemanticModel:
    fact_responses: list[dict[str, Any]] = field(default_factory=list)
    fact_response_answers: list[dict[str, Any]] = field(default_factory=list)
    dim_surveys: list[dict[str, Any]] = field(default_factory=list)
    dim_questions: list[dict[str, Any]] = field(default_factory=list)
    dim_answer_options: list[dict[str, Any]] = field(default_factory=list)


def build_semantic_model(entities: EntitySet) -> SemanticModel:
    validate_entity_set(entities, strict=True)
    questions = {str(row["question_id"]): row for row in entities.questions}
    sections = {str(row["section_id"]): row for row in entities.sections}
    question_catalog = {str(row["question_catalog_id"]): row for row in entities.question_catalog}
    field_catalog = {str(row["question_field_catalog_id"]): row for row in entities.question_field_catalog}
    dimensions = []
    for field_row in entities.question_fields:
        question = questions[str(field_row["question_id"])]
        section = sections.get(str(question.get("section_id") or ""), {})
        catalog = question_catalog.get(str(question["question_catalog_id"]), {})
        field_definition = field_catalog.get(str(field_row["question_field_catalog_id"]), {})
        dimensions.append({**catalog, **field_definition, **section, **question, **field_row})
    return SemanticModel(
        fact_responses=[dict(row) for row in entities.responses],
        fact_response_answers=[dict(row) for row in entities.response_answers],
        dim_surveys=[dict(row) for row in entities.surveys],
        dim_questions=dimensions,
        dim_answer_options=[dict(row) for row in entities.answer_options],
    )
