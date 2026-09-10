"""Small, survey-scoped aggregates for the offline Summary dashboard."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime
from statistics import median
from typing import Any

from .._common.analytics.report import QuestionKey, ReportAnalytics
from .._common.models import EntitySet
from .._common.models.question_types import resolve_question_type
from .insights import field_value_type
from .question_presentation import numeric_distribution, option_counts

Row = dict[str, Any]


def _recorded_date(value: object) -> str | None:
    """Keep the export's calendar date; never shift it into another timezone."""
    raw = str(value or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}(?:$|[Tt ])", raw):
        return None
    try:
        return datetime.fromisoformat(raw).date().isoformat()
    except ValueError:
        return None


def _field_label(fields: list[Row], question: Row, *, multiple: bool) -> str:
    field = fields[0]
    label = str(field.get("statement_text") or field.get("field_text") or "")
    if " ".join(label.split()).casefold() == " ".join(str(question.get("question_text") or "").split()).casefold():
        return ""
    return label or (str(field["field_id"]) if multiple else "")


def _numeric_data(answers: list[Row]) -> tuple[int, list[Row], str, Row] | None:
    values = []
    for answer in answers:
        value = answer.get("answer_numeric")
        if value is None:
            value = str(answer["answer_text"]).replace(",", "")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(number):
            values.append(number)
    if not values:
        return None
    bins = [{"label": label, "count": count} for label, count in numeric_distribution(values)]
    note = f"Percentages use {len(values):,} numeric values. "
    note += "Up to 12 distinct values appear individually; larger domains use up to eight equal-width intervals."
    excluded = len(answers) - len(values)
    if excluded:
        note += f" {excluded:,} non-numeric or non-finite values excluded."
    middle = median(values)
    if not math.isfinite(middle):
        # The sum in an even-size median can overflow although every value is finite.
        ordered = sorted(values)
        index = len(ordered) // 2
        middle = ordered[index - 1] / 2 + ordered[index] / 2
    metric = {"label": "Median", "value": f"{middle:,.2f}".rstrip("0").rstrip(".")}
    return len(values), bins, note, metric


def _categorical_data(answers: list[Row], options: list[Row], *, multiple: bool) -> tuple[int, list[Row], str] | None:
    if not answers:
        return None
    counts = option_counts(answers, options)
    if not any(item.count for item in counts):
        return None
    denominator = len({str(answer["response_id"]) for answer in answers})
    bins = [
        {"label": item.label + (" (unknown option)" if item.answer_id is None else ""), "count": item.count}
        for item in counts
    ]
    note = f"Percentages use {denominator:,} respondents with a recorded answer in this distribution."
    if multiple:
        note += " Each respondent is counted once per option. Multiple selections can total more than 100%."
    unknown = sum(item.count for item in counts if item.answer_id is None)
    if unknown:
        unit = "selection" if unknown == 1 else "selections"
        note += f" {unknown:,} respondent-option {unit} without a defined option."
    return denominator, bins, note


def _question_spotlights(
    question: Row, fields: list[Row], answers: list[Row], options: list[Row], occurrence: int
) -> list[Row]:
    resolved = resolve_question_type(
        question.get("question_type"), question.get("selector"), question.get("sub_selector")
    )
    canonical = str(question.get("canonical_question_type") or resolved.canonical_question_type)
    field_lookup = {str(field["field_id"]): field for field in fields}
    by_field: dict[str, list[Row]] = {}
    for answer in answers:
        field_id = str(answer["field_id"])
        field_lookup.setdefault(field_id, {"field_id": field_id})
        by_field.setdefault(field_id, []).append(answer)
    option_fields: dict[str, list[Row]] = {}
    for option in options:
        field_id = str(option.get("question_field_id") or option.get("field_id") or "")
        option_fields.setdefault(field_id, []).append(option)

    groups: dict[tuple[str, str], list[Row]] = {}
    for field_id, field in field_lookup.items():
        kind = field_value_type(question, field)
        if kind not in {"numeric", "categorical"}:
            continue
        group_id = field_id
        if kind == "categorical":
            if canonical == "multiple_choice_multiple":
                group_id = "question"
            elif canonical == "matrix":
                group_id = str(field.get("choice_external_id") or field_id)
        groups.setdefault((kind, group_id), []).append(field)

    spotlights = []
    for index, ((kind, _), group_fields) in enumerate(groups.items(), 1):
        observed = [answer for field in group_fields for answer in by_field.get(str(field["field_id"]), [])]
        metric = None
        if kind == "numeric":
            numeric = _numeric_data(observed)
            if numeric is None:
                continue
            denominator, bins, note, metric = numeric
            if canonical == "nps":
                kind = "nps"
                note += " This is the recorded score distribution, not a calculated NPS."
        else:
            scoped = [*option_fields.get("", [])]
            for field in group_fields:
                scoped.extend(option_fields.get(str(field["field_id"]), []))
            multiple = canonical == "multiple_choice_multiple" or (canonical == "matrix" and len(group_fields) > 1)
            categorical = _categorical_data(observed, scoped, multiple=multiple)
            if categorical is None:
                continue
            denominator, bins, note = categorical
        label = (
            ""
            if canonical == "multiple_choice_multiple" and kind == "categorical"
            else _field_label(group_fields, question, multiple=len(groups) > 1)
        )
        spotlights.append({
            "id": f"spotlight-{occurrence}-{index}",
            "survey": str(question["survey_id"]),
            "label": str(question.get("question_text") or question["question_id"]),
            "field": label,
            "kind": kind,
            "target": f"question-detail-{occurrence}",
            "denominator": denominator,
            "bins": bins,
            "note": note,
            "metric": metric,
        })
    return spotlights


def build_dashboard(entities: EntitySet, analysis: ReportAnalytics) -> dict[str, list[Row]]:
    """Aggregate once in Python; browser filters never walk individual answers."""
    dates: dict[str, Counter[str]] = {}
    undated: Counter[str] = Counter()
    for response in entities.responses:
        survey_id = str(response["survey_id"])
        recorded = _recorded_date(response.get("recorded_at"))
        if recorded is None:
            undated[survey_id] += 1
        else:
            dates.setdefault(survey_id, Counter())[recorded] += 1
    surveys = [
        {
            "id": survey_id,
            "label": str(survey.get("survey_name") or survey_id),
            "responses": analysis.survey_response_counts[survey_id],
            "finished": analysis.survey_finished_counts[survey_id],
            "dates": [[day, count] for day, count in sorted(dates.get(survey_id, {}).items())],
            "undated": undated[survey_id],
        }
        for survey_id, survey in analysis.survey_lookup.items()
    ]
    fields: dict[QuestionKey, list[Row]] = {}
    for key, field in analysis.fields.items():
        fields.setdefault(key[:2], []).append(field)
    options: dict[QuestionKey, list[Row]] = {}
    for option in entities.answer_options:
        key = str(option["survey_id"]), str(option["question_id"])
        options.setdefault(key, []).append(option)
    coverage = []
    spotlights = []
    for occurrence, (key, question) in enumerate(analysis.response_questions.items(), 1):
        coverage.append({
            "survey": key[0],
            "label": str(question.get("question_text") or question["question_id"]),
            "answered": len(analysis.question_responses.get(key, set())),
            "total": analysis.survey_response_counts[key[0]],
            "target": f"question-detail-{occurrence}",
        })
        spotlights.extend(
            _question_spotlights(
                question, fields.get(key, []), analysis.question_answers.get(key, []), options.get(key, []), occurrence
            )
        )
    priority = {"nps": 0, "numeric": 1, "categorical": 2}
    spotlights.sort(key=lambda item: (priority[item["kind"]], -item["denominator"]))
    return {"surveys": surveys, "coverage": coverage, "spotlights": spotlights}
