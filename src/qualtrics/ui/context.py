"""Explicit inputs shared by the six report pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..analytics import ReportAnalytics, analyze_entities
from ..models.entities import EntitySet


@dataclass(frozen=True)
class ReportContext:
    entities: EntitySet
    analysis: ReportAnalytics
    answer_options: dict[tuple[str, str, str], dict[str, Any]]
    question_options: dict[tuple[str, str], list[dict[str, Any]]]
    question_catalog_lookup: dict[str, dict[str, Any]]

    @classmethod
    def build(cls, entities: EntitySet) -> ReportContext:
        options: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for option in entities.answer_options:
            options.setdefault((str(option["survey_id"]), str(option["question_id"])), []).append(option)
        return cls(
            entities=entities,
            analysis=analyze_entities(entities),
            answer_options={
                (str(o["survey_id"]), str(o["question_id"]), str(o["answer_id"])): o for o in entities.answer_options
            },
            question_options=options,
            question_catalog_lookup={str(q["question_catalog_id"]): q for q in entities.question_catalog},
        )
