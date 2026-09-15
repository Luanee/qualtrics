"""Convenience APIs for adding prepared text to wide comment rows."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy

from .comments import build_comments
from .entities import EntitySet
from .translation_columns import source_text_hash, translation_columns, translation_is_current


def _finish(entities: EntitySet) -> EntitySet:
    entities.comments = build_comments(entities)
    entities._present_columns["comments"] = {key for row in entities.comments for key in row}
    entities._present_entities.add("comments")
    return entities


def prepare_comment_translations(
    entities: EntitySet,
    target_languages: Iterable[str],
    translate: Callable[[str, str | None, str], str],
) -> EntitySet:
    """Prepare requested comment targets without changing source answers."""
    targets = list(dict.fromkeys(target_languages))
    for target in targets:
        translation_columns(target)
    prepared = deepcopy(entities)
    prepared.comments = build_comments(prepared)
    for row in prepared.comments:
        text = str(row["answer_text"])
        source = str(row.get("user_language") or "").strip() or None
        for target in targets:
            text_key, hash_key, language_key = translation_columns(target)
            if source is not None and source.casefold() == target.casefold():
                continue
            if translation_is_current(row, target):
                continue
            translated = translate(text, source, target)
            if not isinstance(translated, str) or not translated.strip():
                raise ValueError(f"Translator returned no text for {row['response_answer_id']} in {target}")
            row[text_key] = translated
            row[hash_key] = source_text_hash(text)
            row[language_key] = source
    return _finish(prepared)


def import_comment_translations(entities: EntitySet, records: Iterable[Mapping[str, object]]) -> EntitySet:
    """Import prepared records after checking original-text hashes and identity."""
    prepared = deepcopy(entities)
    prepared.comments = build_comments(prepared)
    comments = {str(row["response_answer_id"]): row for row in prepared.comments}
    incoming: set[tuple[str, str]] = set()
    required = {"response_answer_id", "target_language", "source_text_hash", "translated_text"}
    for source in records:
        if set(source) != required:
            raise ValueError(
                "Translation input must have exactly response_answer_id, target_language, "
                "source_text_hash, translated_text"
            )
        answer_id, target = source["response_answer_id"], source["target_language"]
        if not isinstance(answer_id, str) or answer_id not in comments:
            raise ValueError(f"Unknown written response answer: {answer_id}")
        if not isinstance(target, str):
            raise ValueError("Translation target_language must be a nonblank language code")
        text_key, hash_key, language_key = translation_columns(target)
        row = comments[answer_id]
        if source["source_text_hash"] != source_text_hash(str(row["answer_text"])):
            raise ValueError(f"Translation source hash does not match answer {answer_id}")
        translated = source["translated_text"]
        if not isinstance(translated, str) or not translated.strip():
            raise ValueError(f"Translation text must be nonblank for {answer_id}")
        key = answer_id, target
        if key in incoming:
            raise ValueError(f"Duplicate translation for {answer_id} in {target}")
        incoming.add(key)
        row[text_key] = translated
        row[hash_key] = source["source_text_hash"]
        row[language_key] = str(row.get("user_language") or "").strip() or None
    return _finish(prepared)
