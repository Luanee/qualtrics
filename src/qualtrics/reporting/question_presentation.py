"""Offline question summaries using the declared answer types and option domains."""

from __future__ import annotations

import html
import math
from collections import Counter
from dataclasses import dataclass
from statistics import mean, median, stdev
from typing import Any

from ..models.question_types import resolve_question_type

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


def _distribution_row(label: str, count: int, denominator: int, *, choice: bool = False) -> str:
    rate = count / denominator * 100 if denominator else 0
    classes = " option-row" if choice else ""
    if choice and not count:
        classes += " option-zero"
    return (
        f"<div class='distribution-row{classes}'><span title='{html.escape(label, quote=True)}'>"
        f"{html.escape(label)}</span><div class='distribution-bar'><i style='width:{min(rate, 100):.1f}%'></i>"
        f"</div><b>{count:,}</b><small>{rate:.0f}%</small></div>"
    )


def _option_distribution(answers: list[Row], options: list[Row], denominator: int) -> str:
    return (
        "".join(
            _distribution_row(item.label, item.count, denominator, choice=True)
            for item in option_counts(answers, options)
        )
        or "<p class='meta'>No answer options defined or observed.</p>"
    )


def _text_distribution(values: list[str]) -> str:
    if not values:
        return "<p class='meta'>No values observed.</p>"
    counts = Counter(values)
    leading = counts.most_common(12)
    content = "".join(_distribution_row(value, count, len(values)) for value, count in leading)
    hidden = len(values) - sum(count for _, count in leading)
    if hidden:
        content += f"<p class='meta'>Other values: {hidden:,}</p>"
    return content


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
    excluded = len(answers) - len(values)
    exclusion_note = f"<p class='meta'>{excluded:,} non-numeric or non-finite values excluded.</p>" if excluded else ""
    if not values:
        return "<p class='meta'>No numeric values observed.</p>" + exclusion_note

    def format_number(number: float | None) -> str:
        return f"{number:,.2f}".rstrip("0").rstrip(".") if number is not None else "—"

    measures = (
        ("Minimum", min(values)),
        ("Average", mean(values)),
        ("Median", median(values)),
        ("Maximum", max(values)),
        ("Standard deviation", stdev(values) if len(values) > 1 else None),
    )
    return (
        "<div class='numeric-summary'>"
        + "".join(f"<span><b>{format_number(value)}</b> {label}</span>" for label, value in measures)
        + f"</div><p class='meta'>{len(values):,} numeric values. "
        "Sample standard deviation (n − 1); requires at least two values.</p>" + exclusion_note
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
    headings = "".join(f"<th scope='col'><span>{html.escape(label)}</span></th>" for label in columns.values())
    rendered_rows = []
    for label, counts, denominator in rows:
        cells = []
        for key in columns:
            count = counts.get(key)
            if count is None:
                cells.append("<td class='matrix-cell unavailable' title='No exported option for this row'>—</td>")
                continue
            rate = count / denominator * 100 if denominator else 0
            percentage = f"{rate:.0f}%" if denominator else "—"
            zero = " option-zero" if not count else ""
            cells.append(
                f"<td class='matrix-cell{zero}'><b>{count:,}</b><small>{percentage}</small>"
                f"<span class='matrix-meter' aria-hidden='true'><i style='width:{min(rate, 100):.1f}%'></i></span></td>"
            )
        rendered_rows.append(
            f"<tr><th scope='row'>{html.escape(label)}</th><td class='matrix-n'>{denominator:,}</td>"
            f"{''.join(cells)}</tr>"
        )
    return (
        "<div class='field-analysis matrix-analysis'><div class='matrix-scroll' tabindex='0' "
        "role='region' aria-label='Matrix answer distribution'><table class='matrix-summary'>"
        "<caption>Responses by statement and answer option</caption><thead><tr>"
        f"<th scope='col'>Statement</th><th scope='col'>Answered (n)</th>{headings}</tr></thead>"
        f"<tbody>{''.join(rendered_rows)}</tbody></table></div>"
        "<p class='meta'>Each cell shows a respondent count and percentage of respondents who answered that row. "
        "Answer options follow the survey definition order. Multiple selections can total more than 100%. "
        "A missing answer does not tell us whether the question was shown. "
        "— means no row responses or no exported option for that row.</p></div>"
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
                "<div class='field-analysis option-analysis'>"
                + _option_distribution(choice_answers, options, respondents)
                + f"<p class='meta'>{note}</p></div>"
            )
        else:
            for field in choice_fields:
                field_id = str(field["field_id"])
                observed = [answer for answer in answers if str(answer["field_id"]) == field_id]
                heading = f"<h4>{html.escape(labels.get(field_id) or 'Answer')}</h4>" if len(choice_fields) > 1 else ""
                bodies.append(
                    f"<div class='field-analysis option-analysis'>{heading}"
                    + _option_distribution(observed, options, respondents)
                    + f"<p class='meta'>{note}</p></div>"
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
        heading = f"<h4>{html.escape(label)}</h4>" if label else ""
        kind = value_type(field)
        style = ""
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
            content += f"<p class='meta'>Percentages use {n:,} respondents who answered this field.</p>"
            style = " option-analysis"
        else:
            values = [str(answer["answer_text"]) for answer in observed]
            content = (
                f"<p class='meta'>{len(values):,} written responses · {len(set(values)):,} unique. "
                "Most frequent values:</p>"
                if kind == "text" and values
                else ""
            ) + _text_distribution(values)
            style = " text-analysis" if kind == "text" else ""
        bodies.append(f"<div class='field-analysis{style}'>{heading}{content}</div>")
    return "".join(bodies) or "<p class='meta'>No values observed.</p>", value_count, value_label
