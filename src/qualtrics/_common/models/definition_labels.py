"""Occurrence-scoped label lookup and callback freshness for display consumers."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any, Literal, TypeVar

from .entities import EntitySet
from .translation_columns import source_text_hash

LabelKind = Literal["question", "field", "answer_option"]
LabelRow = TypeVar("LabelRow", bound=Mapping[str, object])


def definition_label_is_stale(base: Mapping[str, object], variant: Mapping[str, object], text_key: str) -> bool:
    """Check callback provenance against the current base text."""
    return variant.get("label_origin") == "callback" and variant.get("label_source_text_hash") != source_text_hash(
        str(base.get(text_key) or "")
    )


def current_definition_label(base: LabelRow, variant: LabelRow | None, text_key: str) -> LabelRow:
    """Return a usable localized row, falling back when callback text is stale."""
    if variant is None or definition_label_is_stale(base, variant, text_key):
        return base
    return variant


def _field_key(row: dict[str, Any]) -> tuple[str, ...]:
    survey_id = str(row.get("survey_id"))
    question_id, field_id = row.get("question_external_id"), row.get("field_external_id")
    if question_id is not None and field_id is not None:
        return survey_id, "occurrence", str(question_id), str(field_id)
    return survey_id, "catalog", str(row.get("question_field_catalog_id"))


class DefinitionLabelIndex:
    """Index one collection per operation; rows and freshness remain source-owned.

    Catalogs are a legacy fallback only when they identify one base field.
    Missing or ambiguous lineage must never borrow another occurrence's label.
    """

    def __init__(self, entities: EntitySet) -> None:
        self._fields = {
            str(row.get("question_field_id") or row.get("field_id")): row for row in entities.question_fields
        }
        self._field_counts = Counter(_field_key(row) for row in entities.question_fields if not row.get("is_localized"))
        self._base: dict[tuple[str, ...], dict[str, Any]] = {}
        self._variants: dict[tuple[str, ...], dict[str, Any]] = {}
        tables: tuple[tuple[LabelKind, list[dict[str, Any]]], ...] = (
            ("question", entities.questions),
            ("field", entities.question_fields),
            ("answer_option", entities.answer_options),
        )
        for kind, rows in tables:
            for row in rows:
                key = self._key(kind, row)
                if key is None:
                    continue
                self._variants[(*key, str(row.get("language_code") or "").casefold())] = row
                if not row.get("is_localized"):
                    self._base[key] = row

    def _key(self, kind: LabelKind, row: dict[str, Any]) -> tuple[str, ...] | None:
        if kind == "question":
            return kind, str(row.get("survey_id")), str(row.get("question_external_id"))
        field = row if kind == "field" else self._fields.get(str(row.get("question_field_id") or row.get("field_id")))
        if field is None or self._field_counts[_field_key(field)] != 1:
            return None
        key = (kind, *_field_key(field))
        return (*key, str(row.get("answer_external_id"))) if kind == "answer_option" else key

    def get(self, kind: LabelKind, row: dict[str, Any], language: str | None = None) -> dict[str, Any] | None:
        """Find the base occurrence, or its requested language variant, without fallback."""
        key = self._key(kind, row)
        if key is None:
            return None
        return self._base.get(key) if language is None else self._variants.get((*key, language.casefold()))
