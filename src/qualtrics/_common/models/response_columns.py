"""Shared source-column metadata without parser or presentation dependencies."""

from __future__ import annotations

import json
from typing import Any

RESPONSE_SYSTEM_COLUMNS = (
    "response_id",
    "response_external_id",
    "survey_id",
    "started_at",
    "ended_at",
    "recorded_at",
    "is_finished",
    "user_language",
    "status",
    "ip_address",
    "progress",
    "duration_seconds",
    "recipient_last_name",
    "recipient_first_name",
    "recipient_email",
    "external_reference",
    "distribution_channel",
    "browser",
    "browser_version",
    "operating_system",
    "screen_resolution",
    "user_agent",
)


def allocate_response_column(name: str, used: set[str]) -> str:
    """Allocate a flat column name and add its casefolded form to ``used``."""
    candidate = name or "property"
    if candidate.casefold() in used:
        candidate = f"property_{name}" if name else "property"
    base = candidate
    suffix = 2
    while candidate.casefold() in used:
        candidate = f"{base}__{suffix}"
        suffix += 1
    used.add(candidate.casefold())
    return candidate


def read_source_columns(survey: dict[str, Any]) -> list[dict[str, Any]]:
    """Return independent descriptors, or an empty list for older/malformed rows."""
    raw = survey.get("source_columns_json")
    if not isinstance(raw, str):
        return []
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return []
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []
