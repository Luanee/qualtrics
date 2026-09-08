from __future__ import annotations

import csv
import html
from io import StringIO
from typing import Any

from ..models import EntitySet

CODEBOOK_COLUMNS = (
    "survey_id",
    "survey",
    "export_column",
    "import_id",
    "question_id",
    "question",
    "field",
    "section",
    "question_type",
    "value_type",
    "choices",
)


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _order(value: object) -> int:
    try:
        return int(str(value))
    except (ValueError, TypeError):
        return 2**31


def _choice(option: dict[str, Any]) -> str:
    identifier = _text(option.get("answer_external_id", option.get("answer_id")))
    code = _text(option.get("answer_code"))
    label = _text(option.get("answer_text"))
    text = f"{code or identifier} = {label}"
    details = []
    if code and code != identifier and identifier:
        details.append(f"choice ID: {identifier}")
    if option.get("answer_export_tag"):
        details.append(f"export tag: {option['answer_export_tag']}")
    return text + (f" ({'; '.join(details)})" if details else "")


def build_codebook(entities: EntitySet) -> list[dict[str, str]]:
    """Describe exported question fields without inspecting respondent values."""
    surveys = {str(row["survey_id"]): row for row in entities.surveys}
    survey_order = {survey_id: index for index, survey_id in enumerate(surveys)}
    questions = {(str(row["survey_id"]), str(row["question_id"])): row for row in entities.questions}
    sections = {(str(row["survey_id"]), str(row["section_id"])): row for row in entities.sections}
    domains: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for option in entities.answer_options:
        key = (
            str(option["survey_id"]),
            str(option["question_id"]),
            str(option.get("question_field_id") or option.get("field_id")),
        )
        domains.setdefault(key, []).append(option)
    fields = sorted(
        entities.question_fields,
        key=lambda row: (
            survey_order.get(str(row["survey_id"]), len(surveys)),
            str(row["survey_id"]),
            _order(row.get("source_column_index")),
            str(row.get("field_external_id") or row.get("field_id")),
        ),
    )
    entries = []
    for field in fields:
        survey_id = str(field["survey_id"])
        question_id = str(field["question_id"])
        question = questions.get((survey_id, question_id), {})
        section = sections.get((survey_id, str(question.get("section_id"))), {})
        field_id = str(field.get("question_field_id") or field.get("field_id"))
        options = sorted(
            domains.get((survey_id, question_id, field_id), []), key=lambda row: _order(row.get("answer_order"))
        )
        entries.append({
            "survey_id": survey_id,
            "survey": _text(surveys.get(survey_id, {}).get("survey_name") or survey_id),
            "export_column": _text(field.get("field_external_id") or field.get("field_id")),
            "import_id": _text(field.get("import_external_id") or field.get("source_import_id")),
            "question_id": _text(question.get("question_external_id") or question_id),
            "question": _text(question.get("question_text")),
            "field": _text(field.get("field_text")),
            "section": _text(section.get("section_name") or question.get("block_name")),
            "question_type": _text(
                question.get("canonical_question_type") or question.get("question_type") or "Unknown"
            ),
            "value_type": _text(field.get("answer_value_type") or question.get("answer_value_type") or "Unknown"),
            "choices": "\n".join(_choice(option) for option in options),
        })
    return entries


def _csv_line(values: list[str]) -> str:
    # CSV is also opened in spreadsheets; keep survey labels as literal text.
    safe = ["'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value for value in values]
    buffer = StringIO(newline="")
    csv.writer(buffer).writerow(safe)
    return buffer.getvalue().removesuffix("\r\n")


def render_codebook(entities: EntitySet) -> str:
    entries = build_codebook(entities)
    rows = []
    for entry in entries:
        escaped = {key: html.escape(value, quote=True) for key, value in entry.items()}
        search = html.escape(" ".join(entry.values()).lower(), quote=True)
        csv_data = html.escape(_csv_line([entry[key] for key in CODEBOOK_COLUMNS]), quote=True)
        rows.append(
            f"<tr class='codebook-row' data-survey='{escaped['survey_id']}' "
            f"data-search='{search}' data-csv='{csv_data}'>"
            f"<td>{escaped['survey']}</td>"
            f"<td><code>{escaped['export_column']}</code>"
            f"<small>ImportId: {escaped['import_id'] or 'Unavailable'}</small></td>"
            f"<td><strong>{escaped['question'] or escaped['question_id']}</strong><small>{escaped['question_id']}"
            f"{(' · ' + escaped['section']) if escaped['section'] else ''}</small></td>"
            f"<td>{escaped['field']}</td>"
            f"<td>{escaped['question_type'].replace('_', ' ')}<small>{escaped['value_type']}</small></td>"
            f"<td class='codebook-choices'>{escaped['choices'] or '—'}</td></tr>"
        )
    empty_message = (
        "No question fields are available." if not entries else "No fields match the selected surveys and search."
    )
    csv_header = html.escape(_csv_line(list(CODEBOOK_COLUMNS)), quote=True)
    return (
        "<details id='codebook' class='report-section'><summary class='section-summary'>"
        "<span><strong>Codebook</strong>"
        "<small>Understand exported columns, question types, and answer codes.</small></span>"
        f"<span class='section-count'>{len(entries)} fields</span></summary><div class='section-body'>"
        "<p class='meta'>One row per exported question field. Choices come from the survey definition when available. "
        "Response metadata columns are not included.</p>"
        "<div class='codebook-controls'><label for='codebook-search'>Find a field</label>"
        "<input id='codebook-search' type='search' placeholder='Question, column, code, or label…'>"
        "<span id='codebook-count' aria-live='polite'></span>"
        f"<button id='codebook-download' type='button' data-header='{csv_header}'>"
        "Download CSV</button></div>"
        "<div class='codebook-scroll' tabindex='0' role='region' aria-label='Codebook table'>"
        "<table class='codebook-table'><caption>Exported question fields</caption>"
        "<thead><tr><th scope='col'>Survey</th><th scope='col'>Export column</th>"
        "<th scope='col'>Question</th><th scope='col'>Field / part</th><th scope='col'>Type</th>"
        f"<th scope='col'>Codes and labels</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        f"<p id='codebook-empty' class='meta'{'' if not entries else ' hidden'}>{empty_message}</p>"
        "</div></details>"
    )
