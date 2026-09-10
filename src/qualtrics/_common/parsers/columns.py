"""Classify exported columns from source evidence before reading response values."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..models.question_types import classify_question_role, resolve_question_type
from ..models.response_columns import RESPONSE_SYSTEM_COLUMNS, allocate_response_column

SYSTEM_COLUMNS = {
    "StartDate": "started_at",
    "EndDate": "ended_at",
    "RecordedDate": "recorded_at",
    "ResponseId": "response_external_id",
    "Finished": "is_finished",
    "UserLanguage": "user_language",
    "Status": "status",
    "IPAddress": "ip_address",
    "Progress": "progress",
    "Duration (in seconds)": "duration_seconds",
    "RecipientLastName": "recipient_last_name",
    "RecipientFirstName": "recipient_first_name",
    "RecipientEmail": "recipient_email",
    "ExternalReference": "external_reference",
    "DistributionChannel": "distribution_channel",
}
BROWSER_METADATA_FIELDS = {
    "BROWSER": "browser",
    "VERSION": "browser_version",
    "OS": "operating_system",
    "RESOLUTION": "screen_resolution",
    "USERAGENT": "user_agent",
}
QUALITY_COLUMNS = {
    "Q_RecaptchaScore",
    "Q_RecaptchaStatus",
    "Q_RelevantIDDuplicate",
    "Q_RelevantIDDuplicateScore",
    "Q_RelevantIDFraudScore",
    "Q_RelevantIDLastStartDate",
    "Q_DuplicateRespondent",
    "Q_BallotBoxStuffing",
    "Q_StraightliningCount",
    "Q_StraightliningPercentage",
    "Q_Speeding",
}


def _normalized(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


_SYSTEM_IMPORTS = {_normalized(source): target for source, target in SYSTEM_COLUMNS.items()}
_SYSTEM_IMPORTS.update({
    "recordid": "response_external_id",
    "duration": "duration_seconds",
    "externaldatareference": "external_reference",
})
_QUALITY_IMPORTS = {_normalized(source) for source in QUALITY_COLUMNS}
_EXTRA_SYSTEM_IMPORTS = {"locationlatitude", "locationlongitude"}


@dataclass(frozen=True)
class SourceColumn:
    source_column: str
    source_column_index: int
    source_import_id: str
    label: str
    kind: str
    reason: str
    storage_table: str
    storage_column: str
    question_external_id: str | None
    field_key: str
    metadata: dict[str, Any]

    def descriptor(self) -> dict[str, Any]:
        return {
            "source_column": self.source_column,
            "source_column_index": self.source_column_index,
            "source_import_id": self.source_import_id or None,
            "label": self.label,
            "kind": self.kind,
            "reason": self.reason,
            "storage_table": self.storage_table,
            "storage_column": self.storage_column,
            **({"question_external_id": self.question_external_id} if self.question_external_id else {}),
        }


def parse_column_metadata(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _question_id(value: str) -> str | None:
    # Loop & Merge exports prefix the native question ID with a numeric iteration.
    match = re.match(r"^(?:\d+_)*(QID\d+|Q\d+)(?=$|[^A-Za-z0-9])", value, re.I)
    return match.group(1).upper() if match else None


def field_source_parts(column: SourceColumn, definition: dict[str, Any]) -> tuple[str | None, str, str]:
    """Separate a matched export tag from choice/text suffixes without inventing an ImportId."""
    question_id = column.question_external_id or ""
    import_id = column.source_import_id
    suffix = (import_id.replace(question_id, "", 1).strip("_") or None) if import_id else None
    if _question_id(import_id) == question_id:
        return suffix, import_id, column.field_key
    tag = str(definition.get("DataExportTag") or "")
    if tag and (column.source_column == tag or column.source_column.startswith(tag + "_")):
        suffix = column.source_column[len(tag) :].strip("_") or None
        return suffix, "", suffix or ""
    return suffix, import_id, column.field_key


def embedded_field_names(source: object) -> set[str]:
    """Collect declared field names without using configured default values."""
    fields: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, dict):
            embedded = value.get("EmbeddedData")
            if isinstance(embedded, list):
                fields.update(str(item["Field"]) for item in embedded if isinstance(item, dict) and item.get("Field"))
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(source)
    return fields


def _embedded_fields(entry: dict[str, Any]) -> set[str]:
    fields = {str(value) for value in entry.get("_source_embedded_fields") or ()}
    try:
        definition = json.loads(str(entry.get("flow_definition_json") or "{}"))
    except ValueError:
        return fields
    return fields | embedded_field_names(definition)


def _export_question(column: str, questions: dict[str, dict[str, Any]]) -> tuple[str | None, bool]:
    exact = [qid for qid, question in questions.items() if str(question.get("DataExportTag") or "") == column]
    if exact:
        return (exact[0], False) if len(exact) == 1 else (None, True)
    candidates = []
    for qid, question in questions.items():
        tag = str(question.get("DataExportTag") or "")
        if tag and column.startswith(tag + "_"):
            suffix = column[len(tag) + 1 :]
            if re.fullmatch(
                r"(?:\d+[_#]?|TEXT|NPS_GROUP|FIRST_CLICK|LAST_CLICK|PAGE_SUBMIT|CLICK_COUNT)+", suffix, re.I
            ):
                candidates.append(qid)
    return (candidates[0], False) if len(candidates) == 1 else (None, len(candidates) > 1)


def _classify(
    column: str, import_id: str, metadata: dict[str, Any], questions: dict[str, dict[str, Any]], embedded: set[str]
) -> tuple[str, str, str | None, str | None]:
    explicit = str(metadata.get("questionId") or metadata.get("QuestionID") or metadata.get("questionID") or "")
    question_id = _question_id(explicit) or _question_id(import_id)
    reason = "CSV questionId metadata" if _question_id(explicit) else "CSV question ImportId"
    if not question_id:
        target = _SYSTEM_IMPORTS.get(_normalized(import_id)) if import_id else None
        if target:
            return "system", "Standard Qualtrics response ImportId", None, target
        if _normalized(import_id or column) in _EXTRA_SYSTEM_IMPORTS:
            return "system", "Standard Qualtrics response geolocation metadata", None, None
        if _normalized(import_id or column) in _QUALITY_IMPORTS:
            return "quality", "Known Qualtrics response quality field", None, None
        if column in embedded:
            return "embedded", "Field declared in survey flow embedded data", None, None
        question_id, ambiguous = _export_question(column, questions)
        reason = "Unique question export tag in survey definition"
        if ambiguous:
            return "unclassified", "Export tag matches multiple questions; association is unresolved", None, None
        if not question_id and (not import_id or import_id.casefold() == column.casefold()):
            target = SYSTEM_COLUMNS.get(column)
            if target:
                return "system", "Standard Qualtrics response export column", None, target
    if not question_id and (not import_id or import_id == column):
        question_id = _question_id(column)
        reason = "Question-shaped export column; no conflicting ImportId"
    if question_id:
        definition = questions.get(question_id, {})
        role = classify_question_role(definition, [import_id or column])
        suffix = (import_id or column).removeprefix(question_id).strip("_").upper()
        if role == "metadata":
            return (
                "metadata",
                f"{reason}; browser or metadata question",
                question_id,
                BROWSER_METADATA_FIELDS.get(suffix),
            )
        if role == "timing":
            return "timing", f"{reason}; timing measurement", question_id, None
        resolved = resolve_question_type(
            definition.get("QuestionType"), definition.get("Selector"), definition.get("SubSelector")
        )
        if resolved.answer_value_type == "non_response":
            return "metadata", f"{reason}; non-response question type", question_id, None
        if (import_id or column).upper().endswith("_NPS_GROUP"):
            return "derived", f"{reason}; derived NPS classification", question_id, None
        return "question", reason, question_id, None
    return "unclassified", "No unambiguous question or response-property definition", None, None


def classify_columns(
    columns: list[str],
    headers: list[str],
    metadata: list[str],
    questions: dict[str, dict[str, Any]],
    entry: dict[str, Any],
) -> list[SourceColumn]:
    embedded = _embedded_fields(entry)
    used_properties: set[str] = {name.casefold() for name in RESPONSE_SYSTEM_COLUMNS}
    assigned_system: set[str] = set()
    used_fields: set[str] = set()
    original_fields = set(columns)
    result = []
    for index, (column, header, raw_metadata) in enumerate(zip(columns, headers, metadata, strict=True)):
        parsed = parse_column_metadata(raw_metadata)
        import_id = str(parsed.get("ImportId") or "")
        kind, reason, question_id, preferred = _classify(column, import_id, parsed, questions, embedded)
        field_key = column
        if question_id:
            suffix = 2
            while field_key in used_fields:
                field_key = f"{column}__{suffix}"
                suffix += 1
                if field_key in original_fields:
                    field_key = column
            used_fields.add(field_key)
        if kind in {"question", "derived"}:
            table, storage_column = "response_answers", field_key
        else:
            table = "responses"
            if preferred and preferred not in assigned_system:
                storage_column = preferred
                assigned_system.add(preferred)
            else:
                storage_column = allocate_response_column(column, used_properties)
        result.append(
            SourceColumn(
                column, index, import_id, header, kind, reason, table, storage_column, question_id, field_key, parsed
            )
        )
    return result
