"""Optional prepared text indexed by comment answer and target language."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from typing import TYPE_CHECKING

from .comments import build_comments
from .identity import entity_id

if TYPE_CHECKING:
    from .entities import EntitySet

TRANSLATION_COLUMNS = (
    "comment_translation_id",
    "response_answer_id",
    "survey_id",
    "source_language",
    "target_language",
    "source_text_hash",
    "translated_text",
)


def source_text_hash(text: str) -> str:
    """Hash the exact stored answer, including whitespace and Unicode spelling."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def translation_id(response_answer_id: str, target_language: str) -> str:
    return entity_id("comment-translation", response_answer_id, target_language)


def prepare_comment_translations(
    entities: EntitySet,
    target_languages: Iterable[str],
    translate: Callable[[str, str | None, str], str],
) -> EntitySet:
    """Call a user-supplied translator only for requested, missing or stale targets."""
    targets = list(dict.fromkeys(target_languages))
    if any(not isinstance(code, str) or not code.strip() or code != code.strip() for code in targets):
        raise ValueError("Target languages must be nonblank language codes")
    prepared = {
        (str(row["response_answer_id"]), str(row["target_language"])): dict(row)
        for row in entities.comment_translations
    }
    for comment in build_comments(entities):
        answer_id = str(comment["response_answer_id"])
        text = str(comment["answer_text"])
        language = str(comment.get("user_language") or "").strip() or None
        digest = source_text_hash(text)
        for target in targets:
            if target == language:
                continue
            key = answer_id, target
            if prepared.get(key, {}).get("source_text_hash") == digest:
                continue
            translated = translate(text, language, target)
            if not isinstance(translated, str) or not translated.strip():
                raise ValueError(f"Translator returned no text for {answer_id} in {target}")
            prepared[key] = {
                "comment_translation_id": translation_id(answer_id, target),
                "response_answer_id": answer_id,
                "survey_id": str(comment["survey_id"]),
                "source_language": language,
                "target_language": target,
                "source_text_hash": digest,
                "translated_text": translated,
            }
    return replace(entities, comment_translations=list(prepared.values()))


def import_comment_translations(entities: EntitySet, records: Iterable[Mapping[str, object]]) -> EntitySet:
    """Attach prepared rows only when their hashes match current written answers."""
    comments = {str(row["response_answer_id"]): row for row in build_comments(entities)}
    prepared = {
        (str(row["response_answer_id"]), str(row["target_language"])): dict(row)
        for row in entities.comment_translations
    }
    incoming: set[tuple[str, str]] = set()
    required = {"response_answer_id", "target_language", "source_text_hash", "translated_text"}
    for source in records:
        if set(source) != required:
            raise ValueError(
                "Translation input must have exactly response_answer_id, target_language, "
                "source_text_hash, translated_text"
            )
        answer_id = source["response_answer_id"]
        target = source["target_language"]
        digest = source["source_text_hash"]
        translated = source["translated_text"]
        if not isinstance(answer_id, str) or answer_id not in comments:
            raise ValueError(f"Unknown written response answer: {answer_id}")
        if not isinstance(target, str) or not target.strip() or target != target.strip():
            raise ValueError("Translation target_language must be a nonblank language code")
        if digest != source_text_hash(str(comments[answer_id]["answer_text"])):
            raise ValueError(f"Translation source hash does not match answer {answer_id}")
        if not isinstance(translated, str) or not translated.strip():
            raise ValueError(f"Translation text must be nonblank for {answer_id}")
        key = answer_id, target
        if key in incoming:
            raise ValueError(f"Duplicate translation for {answer_id} in {target}")
        incoming.add(key)
        comment = comments[answer_id]
        prepared[key] = {
            "comment_translation_id": translation_id(answer_id, target),
            "response_answer_id": answer_id,
            "survey_id": str(comment["survey_id"]),
            "source_language": str(comment.get("user_language") or "").strip() or None,
            "target_language": target,
            "source_text_hash": digest,
            "translated_text": translated,
        }
    return replace(entities, comment_translations=list(prepared.values()))
