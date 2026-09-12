"""Factual, type-aware observations without inferred sentiment or exposure."""

from __future__ import annotations

import math
from statistics import median
from typing import Any

from .._common.models.question_types import field_value_type as field_value_type
from .._common.models.question_types import resolve_question_type
from .question_presentation import option_counts

Row = dict[str, Any]


def question_highlight(
    question: Row, fields: list[Row], answers: list[Row], options: list[Row], respondents: int
) -> str | None:
    """Return plain text; callers escape it. Counts preserve option/field scope."""
    if not answers or not respondents:
        return None
    lookup = {str(field["field_id"]): field for field in fields}
    for answer in answers:
        lookup.setdefault(str(answer["field_id"]), {"field_id": str(answer["field_id"])})
    resolved = resolve_question_type(
        question.get("question_type"), question.get("selector"), question.get("sub_selector")
    )
    canonical = str(question.get("canonical_question_type") or resolved.canonical_question_type)
    choice_ids = {key for key, field in lookup.items() if field_value_type(question, field) == "categorical"}
    groups = []
    if canonical == "multiple_choice_multiple" and choice_ids:
        groups.append((
            "",
            "categorical",
            [a for a in answers if str(a["field_id"]) in choice_ids],
            options,
            respondents,
        ))
    for key, field in lookup.items():
        kind = field_value_type(question, field)
        if canonical == "multiple_choice_multiple" and key in choice_ids:
            continue
        observed = [a for a in answers if str(a["field_id"]) == key]
        scoped = [o for o in options if str(o.get("question_field_id") or o.get("field_id") or "") in {"", key}]
        label = str(field.get("statement_text") or field.get("field_text") or key) if len(lookup) > 1 else ""
        denominator = (
            respondents
            if canonical == "multiple_choice_single" and kind == "categorical"
            else len({str(a["response_id"]) for a in observed})
        )
        groups.append((label, kind, observed, scoped, denominator))
    observations = []
    for label, kind, observed, scoped, denominator in groups:
        if not observed or not denominator:
            continue
        observation = ""
        if kind == "categorical":
            counts = option_counts(observed, scoped)
            highest = max((item.count for item in counts), default=0)
            if not highest:
                continue
            leaders = [
                item.label + (" (unknown option)" if item.answer_id is None else "")
                for item in counts
                if item.count == highest
            ]
            prefix = "Tied most selected" if len(leaders) > 1 else "Most selected"
            each = " each" if len(leaders) > 1 else ""
            if len(leaders) > 4:
                prefix += f" ({len(leaders)} options)"
                leaders = [*leaders[:3], f"and {len(leaders) - 3} others"]
            observation = (
                f"{prefix}: {'; '.join(leaders)} — {highest:,} of {denominator:,} respondents{each} "
                f"({highest / denominator * 100:.0f}%)."
            )
        elif kind == "numeric":
            numbers = []
            for answer in observed:
                value = answer.get("answer_numeric")
                if value is None:
                    value = str(answer["answer_text"]).replace(",", "")
                try:
                    number = float(value)
                except (ValueError, TypeError):
                    continue
                if math.isfinite(number):
                    numbers.append(number)
            if not numbers:
                continue
            formatted = f"{median(numbers):,.2f}".rstrip("0").rstrip(".")
            excluded = len(observed) - len(numbers)
            note = f"; {excluded:,} non-numeric or non-finite values excluded" if excluded else ""
            observation = f"Median: {formatted} ({len(numbers):,} numeric values{note})."
        elif kind == "text":
            observation = f"{len(observed):,} written values from {denominator:,} respondents."
        if observation:
            observations.append(f"{label}: {observation}" if label else observation)
    if len(observations) > 3:
        observations = [*observations[:3], f"See question details for {len(observations) - 3} more fields."]
    return " ".join(observations) or None
