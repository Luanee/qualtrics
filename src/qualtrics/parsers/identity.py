from __future__ import annotations

import hashlib
import html
import re
from typing import Any


def _clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _qid(value: str) -> str | None:
    match = re.search(r"(QID\d+|Q\d+)", value, re.I)
    return match.group(1).upper() if match else None


def _question_role(definition: dict[str, Any], import_ids: list[str]) -> str:
    question_type = str(definition.get("QuestionType") or "").casefold()
    selector = str(definition.get("Selector") or "").casefold()
    if question_type in {"meta", "metadata"} or selector == "browser":
        return "metadata"
    if question_type == "timing" or selector == "timing":
        return "timing"
    technical = " ".join(import_ids).upper()
    metadata_suffixes = ("_BROWSER", "_VERSION", "_OS", "_RESOLUTION", "_USERAGENT")
    if technical and all(
        any(code in item.upper() for code in metadata_suffixes) for item in import_ids
    ):
        return "metadata"
    timing_suffixes = ("FIRST_CLICK", "LAST_CLICK", "PAGE_SUBMIT", "CLICK_COUNT")
    if any(code in technical for code in timing_suffixes):
        return "timing"
    return "response"


def _field_text(header: str, question_text: str, column: str, suffix: str | None) -> str:
    """Return a compact field label without losing its technical identity."""
    cleaned_header = _clean(header)
    if cleaned_header.casefold().startswith((question_text + " - ").casefold()):
        return cleaned_header[len(question_text) + 3 :]
    if cleaned_header.casefold().endswith((" - " + question_text).casefold()):
        candidate = cleaned_header[: -(len(question_text) + 3)]
        if not candidate.startswith(("http://", "https://")):
            return candidate
    number = re.match(r"(\d+)", str(suffix or column))
    if cleaned_header.startswith(("http://", "https://")) and number:
        return f"Item {number.group(1)}"
    return cleaned_header or str(suffix or column)
