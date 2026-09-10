"""Offline question summaries using the declared answer types and option domains."""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from statistics import mean, median, stdev
from typing import Any

from ..models.question_types import resolve_question_type
from .templating import render_template, trusted_html

Row = dict[str, Any]


@dataclass(frozen=True)
class OptionCount:
    option_id: str
    answer_id: str | None
    label: str
    count: int


def _ordered_options(options: list[Row]) -> list[Row]:
    def order(option: Row) -> float:
        try:
            return float(option.get("answer_order") or math.inf)
        except (TypeError, ValueError):
            return math.inf

    return sorted(options, key=order)


def _option_id(option: Row) -> str:
    return str(option.get("answer_option_id") or f"{option.get('field_id')}:{option['answer_id']}")


def option_counts(answers: list[Row], options: list[Row]) -> list[OptionCount]:
    """Resolve only unambiguous aliases, retaining each respondent/option once."""
    options = _ordered_options(options)
    lookup = {_option_id(option): option for option in options}
    aliases: dict[tuple[str, str], set[str]] = {}
    for option in options:
        field = str(option.get("question_field_id") or option.get("field_id") or "")
        for alias in ("answer_id", "answer_code", "answer_export_tag", "answer_text"):
            raw = option.get(alias)
            value = str(raw if raw is not None else "").casefold()
            if value:
                aliases.setdefault((field, value), set()).add(_option_id(option))
    selected: set[tuple[str, str]] = set()
    unknown: dict[str, str] = {}
    for answer in answers:
        raw = str(answer["answer_text"])
        field = str(answer.get("question_field_id") or answer.get("field_id") or "")
        linked = str(answer.get("answer_option_id") or "")
        linked_option = lookup.get(linked, {})
        linked_field = str(linked_option.get("question_field_id") or linked_option.get("field_id") or "")
        option_id = linked if linked in lookup and linked_field in {field, ""} else None
        candidates = aliases.get((field, raw.casefold()), aliases.get(("", raw.casefold()), set()))
        if option_id is None and len(candidates) == 1:
            option_id = next(iter(candidates))
        if option_id is None:
            option_id = f"unknown:{raw.casefold()}"
            unknown.setdefault(option_id, raw)
        selected.add((str(answer["response_id"]), option_id))
    counts = Counter(option_id for _, option_id in selected)
    return [
        OptionCount(option_id, str(option["answer_id"]), str(option["answer_text"]), counts[option_id])
        for option_id, option in lookup.items()
    ] + [
        OptionCount(option_id, None, label, counts[option_id])
        for option_id, label in sorted(unknown.items(), key=lambda item: item[1].casefold())
    ]


@dataclass(frozen=True)
class DistributionRow:
    label: str
    count: int
    percentage: str
    width: str
    choice: bool = False


def _distribution_rows(
    counts: list[tuple[str, int]], denominator: int, *, choice: bool = False
) -> list[DistributionRow]:
    rows = []
    for label, count in counts:
        rate = count / denominator * 100 if denominator else 0
        rows.append(DistributionRow(label, count, f"{rate:.0f}%", f"{min(rate, 100):.1f}%", choice))
    return rows


def _option_distribution(answers: list[Row], options: list[Row], denominator: int) -> str:
    counts = [(item.label, item.count) for item in option_counts(answers, options)]
    return render_template(
        "questions/distribution.html.jinja",
        rows=_distribution_rows(counts, denominator, choice=True),
        empty_message="No answer options defined or observed.",
        other_count=0,
    )


def _text_distribution(values: list[str], *, written: bool = False) -> str:
    leading = Counter(values).most_common(12)
    return render_template(
        "questions/text.html.jinja",
        rows=_distribution_rows(leading, len(values)),
        empty_message="No values observed.",
        other_count=len(values) - sum(count for _, count in leading),
        written=written,
        count=len(values),
        unique_count=len(set(values)),
    )


def numeric_distribution(values: list[float]) -> list[tuple[str, int]]:
    """Count finite values exactly for small domains, or in up to eight bins."""
    counts = Counter(value for value in values if math.isfinite(value))
    if not counts:
        return []

    def labels(numbers: list[float]) -> list[str]:
        short = [f"{number:.6g}" for number in numbers]
        return short if len(set(short)) == len(numbers) else [f"{number:.17g}" for number in numbers]

    ordered = sorted(counts)
    if len(ordered) <= 12:
        return [(label, counts[value]) for value, label in zip(ordered, labels(ordered), strict=True)]
    low, high = ordered[0], ordered[-1]
    # A convex combination avoids overflow in high - low for extreme ranges.
    edges = sorted({low, high, *(low * (1 - step / 8) + high * (step / 8) for step in range(1, 8))})
    bins = [0] * (len(edges) - 1)
    for value, count in counts.items():
        bins[min(bisect_right(edges, value) - 1, len(bins) - 1)] += count
    boundary_labels = labels(edges)
    return [
        (
            f"{boundary_labels[index]} ≤ value {'≤' if index == len(bins) - 1 else '<'} {boundary_labels[index + 1]}",
            count,
        )
        for index, count in enumerate(bins)
    ]


def _numeric_summary(answers: list[Row]) -> str:
    values = []
    for answer in answers:
        value = answer.get("answer_numeric")
        if value is None:
            value = str(answer["answer_text"]).replace(",", "")
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            values.append(number)

    def format_number(number: float | None) -> str:
        return f"{number:,.2f}".rstrip("0").rstrip(".") if number is not None else "—"

    measures = (
        (
            ("Minimum", min(values)),
            ("Average", mean(values)),
            ("Median", median(values)),
            ("Maximum", max(values)),
            ("Standard deviation", stdev(values) if len(values) > 1 else None),
        )
        if values
        else ()
    )
    return render_template(
        "questions/numeric.html.jinja",
        measures=[(label, format_number(value)) for label, value in measures],
        count=len(values),
        excluded=len(answers) - len(values),
        rows=_distribution_rows(numeric_distribution(values), len(values)),
    )


def _matrix_row_label(fields: list[Row], options: list[Row], labels: dict[str, str]) -> str:
    statements = {str(field["statement_text"]) for field in fields if field.get("statement_text")}
    if len(statements) == 1:
        return next(iter(statements))
    fallback = labels.get(str(fields[0]["field_id"])) or str(fields[0].get("field_text") or "Answer")
    # Older entity files lack the QSF statement label. Only infer a shared label
    # when every cell ends with its own defined option and the prefixes agree.
    if len(fields) > 1:
        prefixes = set()
        for field in fields:
            field_id = str(field["field_id"])
            field_options = [
                option
                for option in options
                if str(option.get("question_field_id") or option.get("field_id") or "") == field_id
            ]
            if len(field_options) != 1:
                return fallback
            label = labels.get(field_id) or str(field.get("field_text") or "")
            suffix = " - " + str(field_options[0]["answer_text"])
            if not label.endswith(suffix):
                return fallback
            prefixes.add(label[: -len(suffix)].strip())
        if len(prefixes) == 1 and "" not in prefixes:
            return next(iter(prefixes))
    return fallback


def _matrix_summary(fields: list[Row], answers: list[Row], options: list[Row], labels: dict[str, str]) -> str:
    # Multiple-answer matrices export one field per statement/option. Group these
    # by the source statement ID, never by potentially duplicated display labels.
    groups: dict[str, list[Row]] = {}
    for field in fields:
        row_id = str(field.get("choice_external_id") or field["field_id"])
        groups.setdefault(row_id, []).append(field)
    columns: dict[tuple[str | None, str], str] = {}
    for option in _ordered_options(options):
        columns.setdefault((str(option["answer_id"]), str(option["answer_text"])), str(option["answer_text"]))
    rows = []
    for row_fields in groups.values():
        field_ids = {str(field["field_id"]) for field in row_fields}
        row_answers = [answer for answer in answers if str(answer["field_id"]) in field_ids]
        row_options = [
            option
            for option in options
            if str(option.get("question_field_id") or option.get("field_id") or "") in field_ids
        ]
        counts = {(item.answer_id, item.label): item.count for item in option_counts(row_answers, row_options)}
        for key in counts:
            columns.setdefault(key, key[1])
        denominator = len({str(answer["response_id"]) for answer in row_answers})
        label = _matrix_row_label(row_fields, row_options, labels)
        rows.append((label, counts, denominator))
    matrix_rows = []
    for label, counts, denominator in rows:
        cells = []
        for key in columns:
            count = counts.get(key)
            rate = count / denominator * 100 if denominator and count is not None else 0
            cells.append(MatrixCell(count, f"{rate:.0f}%" if denominator else "—", f"{min(rate, 100):.1f}%"))
        matrix_rows.append(MatrixRow(label, denominator, cells))
    return render_template("questions/matrix.html.jinja", columns=list(columns.values()), rows=matrix_rows)


@dataclass(frozen=True)
class MatrixCell:
    count: int | None
    percentage: str
    width: str


@dataclass(frozen=True)
class MatrixRow:
    label: str
    denominator: int
    cells: list[MatrixCell]


def _field_analysis(content: str, *, heading: str = "", style: str = "", note: str = "") -> str:
    return render_template(
        "questions/field.html.jinja", content=trusted_html(content), heading=heading, style=style, note=note
    )


def render_question_analysis(
    question: Row,
    fields: list[Row],
    answers: list[Row],
    options: list[Row],
    labels: dict[str, str],
    respondents: int,
) -> tuple[str, int, str]:
    """Return body HTML plus a value count and its unit for the occurrence header."""
    resolved = resolve_question_type(
        question.get("question_type"), question.get("selector"), question.get("sub_selector")
    )
    canonical = str(question.get("canonical_question_type") or resolved.canonical_question_type)
    default_type = str(question.get("answer_value_type") or resolved.answer_value_type)
    field_lookup = {str(field["field_id"]): field for field in fields}
    for answer in answers:
        field_id = str(answer["field_id"])
        field_lookup.setdefault(field_id, {"field_id": field_id})

    def value_type(field: Row) -> str:
        if field.get("is_text_field"):
            return "text"
        return str(field.get("answer_value_type") or default_type)

    choice_fields = [field for field in field_lookup.values() if value_type(field) == "categorical"]
    choice_ids = {str(field["field_id"]) for field in choice_fields}
    choice_answers = [answer for answer in answers if str(answer["field_id"]) in choice_ids]
    multiple_choice = canonical in {"multiple_choice_single", "multiple_choice_multiple"}
    bodies = []
    handled: set[str] = set()
    value_count, value_label = len(answers), "values"
    if multiple_choice and choice_fields:
        # Respect explicit field types, including numeric metadata on MC fields.
        count_rows = option_counts(choice_answers, options)
        value_count, value_label = sum(item.count for item in count_rows), "selections"
        note = f"Percentages use {respondents:,} respondents who answered this question. "
        is_multiple = canonical == "multiple_choice_multiple" or str(question.get("selector") or "").upper().startswith(
            "MA"
        )
        if is_multiple:
            note += "Each respondent is counted once per option. Percentages can add up to more than 100%."
            bodies.append(
                _field_analysis(
                    _option_distribution(choice_answers, options, respondents), style="option-analysis", note=note
                )
            )
        else:
            for field in choice_fields:
                field_id = str(field["field_id"])
                observed = [answer for answer in answers if str(answer["field_id"]) == field_id]
                heading = (labels.get(field_id) or "Answer") if len(choice_fields) > 1 else ""
                bodies.append(
                    _field_analysis(
                        _option_distribution(observed, options, respondents),
                        heading=heading,
                        style="option-analysis",
                        note=note,
                    )
                )
        handled.update(choice_ids)
    elif canonical == "matrix" and choice_fields:
        bodies.append(_matrix_summary(choice_fields, choice_answers, options, labels))
        handled.update(choice_ids)

    for field_id, field in field_lookup.items():
        if field_id in handled:
            continue
        observed = [answer for answer in answers if str(answer["field_id"]) == field_id]
        label = labels.get(field_id) or ""
        kind = value_type(field)
        style = ""
        note = ""
        if kind == "numeric":
            content = _numeric_summary(observed)
        elif kind == "categorical":
            field_options = [
                option
                for option in options
                if str(option.get("question_field_id") or option.get("field_id") or "") == field_id
            ]
            n = len({str(answer["response_id"]) for answer in observed})
            content = _option_distribution(observed, field_options, n)
            note = f"Percentages use {n:,} respondents who answered this field."
            style = "option-analysis"
        else:
            values = [str(answer["answer_text"]) for answer in observed]
            content = _text_distribution(values, written=kind == "text")
            style = "text-analysis" if kind == "text" else ""
        bodies.append(_field_analysis(content, heading=label, style=style, note=note))
    return (
        render_template("questions/analysis.html.jinja", bodies=[trusted_html(body) for body in bodies]),
        value_count,
        value_label,
    )
