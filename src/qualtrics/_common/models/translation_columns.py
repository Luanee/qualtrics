"""Reversible, collision-free column names for prepared comment targets."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

PREFIXES = (
    "translated_text__",
    "translation_source_hash__",
    "translation_source_language__",
)


def _suffix(code: str) -> str:
    if not isinstance(code, str) or not code.strip() or code != code.strip():
        raise ValueError("Target languages must be nonblank language codes")
    return "".join(
        chr(byte) if 65 <= byte <= 90 or 48 <= byte <= 57 else f"_{byte:02X}_" for byte in code.upper().encode("utf-8")
    )


def translation_columns(code: str) -> tuple[str, str, str]:
    """Return text, source-hash, and source-language columns for a target."""
    suffix = _suffix(code)
    return (
        f"{PREFIXES[0]}{suffix}",
        f"{PREFIXES[1]}{suffix}",
        f"{PREFIXES[2]}{suffix}",
    )


def translation_is_current_column(code: str) -> str:
    """Name a semantic-only freshness column for one target."""
    return f"translation_is_current__{_suffix(code)}"


def source_text_hash(text: str) -> str:
    """Hash exact stored source text, including whitespace and Unicode spelling."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def translation_is_current(row: dict[str, Any], code: str) -> bool:
    """Check a prepared target against current text and respondent language."""
    text_key, hash_key, language_key = translation_columns(code)
    translated = row.get(text_key)
    current_language = str(row.get("user_language") or "").strip().casefold() or None
    stored_language = str(row.get(language_key) or "").strip().casefold() or None
    return (
        isinstance(translated, str)
        and bool(translated.strip())
        and row.get(hash_key) == source_text_hash(str(row.get("answer_text") or ""))
        and stored_language == current_language
    )


def _decode_suffix(suffix: str) -> str:
    encoded = bytearray()
    index = 0
    while index < len(suffix):
        if suffix[index] == "_":
            if index + 3 >= len(suffix) or suffix[index + 3] != "_":
                raise ValueError("Invalid translation target column")
            try:
                encoded.append(int(suffix[index + 1 : index + 3], 16))
            except ValueError as exc:
                raise ValueError("Invalid translation target column") from exc
            index += 4
        else:
            char = suffix[index]
            if not ("A" <= char <= "Z" or "0" <= char <= "9"):
                raise ValueError("Invalid translation target column")
            encoded.append(ord(char))
            index += 1
    try:
        code = encoded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Invalid translation target column") from exc
    if not code or _suffix(code) != suffix:
        raise ValueError("Invalid translation target column")
    return code


def target_from_column(column: str) -> str | None:
    """Decode a recognized column, or return None for non-translation columns."""
    for prefix in PREFIXES:
        if column.startswith(prefix):
            return _decode_suffix(column[len(prefix) :])
    return None


def prepared_targets(columns: Iterable[str]) -> set[str]:
    """Collect target codes from recognized prepared columns."""
    return {target for column in columns if (target := target_from_column(column)) is not None}
