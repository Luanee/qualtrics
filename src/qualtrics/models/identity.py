from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from typing import Any


def _text(value: str) -> str:
    decoded = html.unescape(value)
    without_tags = re.sub(r"<[^>]+>", " ", decoded)
    return " ".join(unicodedata.normalize("NFKC", without_tags).split()).casefold()


def canonicalize(value: Any) -> Any:
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, dict):
        return {str(key): canonicalize(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple, set)):
        items = [canonicalize(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    return value


def _digest(domain: str, parts: tuple[object, ...]) -> str:
    digest = hashlib.sha256()
    for part in (domain, *parts):
        encoded = json.dumps(part, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def entity_id(domain: str, *parts: object) -> str:
    return _digest(f"entity:{domain}", parts)


def semantic_id(domain: str, content: object) -> str:
    return _digest(f"semantic:{domain}", (canonicalize(content),))
