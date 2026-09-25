"""Prepare display text through a user-owned translator without changing facts."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, TypeVar

from .comments import COMMENT_COLUMNS, build_comments
from .entities import EntitySet
from .localization import ensure_localized_entities
from .translation_columns import source_text_hash, translation_columns

TranslationKind = Literal["question", "field", "answer_option", "comment"]


@dataclass(frozen=True)
class TranslationRequest:
    """Text plus source, target, kind, and base-entity lineage for an adapter."""

    kind: TranslationKind
    text: str
    source_language: str | None
    target_language: str
    survey_id: str
    question_id: str | None = None
    question_field_id: str | None = None
    answer_option_id: str | None = None
    response_answer_id: str | None = None


TranslationCallback = Callable[[TranslationRequest], str]
LabelRow = TypeVar("LabelRow", bound=Mapping[str, object])


def current_definition_label(base: LabelRow, variant: LabelRow | None, text_key: str) -> LabelRow:
    """Return a usable localized row, falling back when callback text is stale."""
    if variant is None:
        return base
    if variant.get("label_origin") == "callback" and variant.get("label_source_text_hash") != source_text_hash(
        str(base.get(text_key) or "")
    ):
        return base
    return variant


def _call(callback: TranslationCallback, request: TranslationRequest) -> str:
    translated = callback(request)
    if not isinstance(translated, str) or not translated.strip():
        raise ValueError(f"Translator returned no text for {request.kind} in {request.target_language}")
    return translated


def _target(entities: EntitySet, survey_id: str, language: str | None) -> str:
    if language is not None:
        if not isinstance(language, str) or not language.strip() or language != language.strip():
            raise ValueError("Target languages must be nonblank language codes")
        return language.upper()
    survey = next(row for row in entities.surveys if str(row["survey_id"]) == survey_id)
    base = survey.get("default_language")
    if not isinstance(base, str) or not base.strip():
        raise ValueError(f"Survey {survey_id} has no SurveyLanguage; pass language explicitly")
    return base.upper()


def _prepare_label(
    base: dict,
    variant: dict,
    *,
    kind: TranslationKind,
    text_key: str,
    source_language: str | None,
    target_language: str,
    callback: TranslationCallback | None,
    question_id: str,
    question_field_id: str | None = None,
    answer_option_id: str | None = None,
) -> None:
    if callback is None or not isinstance(base.get(text_key), str) or not base[text_key].strip():
        return
    if source_language is not None and source_language.casefold() == target_language.casefold():
        return
    source = str(base[text_key])
    digest = source_text_hash(source)
    if variant.get("label_origin") == "callback":
        if variant.get("label_source_text_hash") == digest:
            return
    elif str(variant.get("label_source_language") or "").casefold() == target_language.casefold():
        return
    request = TranslationRequest(
        kind=kind,
        text=source,
        source_language=source_language,
        target_language=target_language,
        survey_id=str(base["survey_id"]),
        question_id=question_id,
        question_field_id=question_field_id,
        answer_option_id=answer_option_id,
    )
    variant[text_key] = _call(callback, request)
    variant["label_source_language"] = target_language
    variant["label_origin"] = "callback"
    variant["label_source_text_hash"] = digest


def _definition_labels(
    entities: EntitySet,
    survey_id: str,
    target: str,
    callbacks: dict[TranslationKind, TranslationCallback | None],
) -> None:
    if not any(callbacks[kind] for kind in ("question", "field", "answer_option")):
        return
    ensure_localized_entities(entities, survey_id, target)
    base_questions = {
        str(row["question_id"]): row
        for row in entities.questions
        if str(row["survey_id"]) == survey_id and not row.get("is_localized")
    }
    variants = {
        (str(row["question_external_id"]), str(row.get("language_code") or "").casefold()): row
        for row in entities.questions
        if str(row["survey_id"]) == survey_id and row.get("is_localized")
    }
    base_fields = {
        str(row["question_field_id"]): row
        for row in entities.question_fields
        if str(row["survey_id"]) == survey_id and not row.get("is_localized")
    }
    variant_fields = {
        (
            str(row["question_external_id"]),
            str(row.get("field_external_id")),
            str(row.get("language_code") or "").casefold(),
        ): row
        for row in entities.question_fields
        if str(row["survey_id"]) == survey_id and row.get("is_localized")
    }
    base_options = [
        row for row in entities.answer_options if str(row["survey_id"]) == survey_id and not row.get("is_localized")
    ]
    variant_options = {
        (str(row["question_external_id"]), str(row["question_field_id"]), str(row["answer_external_id"])): row
        for row in entities.answer_options
        if str(row["survey_id"]) == survey_id
        and row.get("is_localized")
        and str(row.get("language_code") or "").casefold() == target.casefold()
    }
    source_language = entities.survey_manifests.get(survey_id, {}).get("languages", {}).get("base_language")
    source_language = str(source_language) if source_language else None
    for base in base_questions.values():
        variant = variants.get((str(base["question_external_id"]), target.casefold()))
        if variant is not None:
            _prepare_label(
                base,
                variant,
                kind="question",
                text_key="question_text",
                source_language=source_language,
                target_language=target,
                callback=callbacks["question"],
                question_id=str(base["question_id"]),
            )
    for base in base_fields.values():
        variant = variant_fields.get((
            str(base["question_external_id"]),
            str(base.get("field_external_id")),
            target.casefold(),
        ))
        if variant is None:
            continue
        _prepare_label(
            base,
            variant,
            kind="field",
            text_key="field_text",
            source_language=source_language,
            target_language=target,
            callback=callbacks["field"],
            question_id=str(base["question_id"]),
            question_field_id=str(base["question_field_id"]),
        )
    for base in base_options:
        base_field = base_fields[str(base["question_field_id"])]
        variant_field = variant_fields.get((
            str(base["question_external_id"]),
            str(base_field.get("field_external_id")),
            target.casefold(),
        ))
        if variant_field is None:
            continue
        variant = variant_options.get((
            str(base["question_external_id"]),
            str(variant_field["question_field_id"]),
            str(base["answer_external_id"]),
        ))
        if variant is None:
            continue
        _prepare_label(
            base,
            variant,
            kind="answer_option",
            text_key="answer_text",
            source_language=source_language,
            target_language=target,
            callback=callbacks["answer_option"],
            question_id=str(base["question_id"]),
            question_field_id=str(base["question_field_id"]),
            answer_option_id=str(base["answer_option_id"]),
        )
        if variant.get("label_origin") == "callback":
            variant["choice_value"] = variant["answer_text"]
            if variant.get("recode_value") is None:
                variant["value"] = variant["answer_text"]


def _written_answers(entities: EntitySet, survey_id: str, target: str, callback: TranslationCallback | None) -> None:
    if callback is None:
        return
    entities.comments = build_comments(entities)
    text_key, hash_key, language_key = translation_columns(target)
    for row in entities.comments:
        if str(row["survey_id"]) != survey_id:
            continue
        source_language = str(row.get("user_language") or "").strip() or None
        if source_language is not None and source_language.casefold() == target.casefold():
            _set_comment_translation(row, target, None)
            continue
        text = str(row["answer_text"])
        digest = source_text_hash(text)
        if row.get(hash_key) == digest and row.get(language_key) == source_language and row.get(text_key):
            continue
        request = TranslationRequest(
            kind="comment",
            text=text,
            source_language=source_language,
            target_language=target,
            survey_id=survey_id,
            question_id=str(row["question_id"]),
            question_field_id=str(row["question_field_id"]),
            response_answer_id=str(row["response_answer_id"]),
        )
        _set_comment_translation(row, target, _call(callback, request))
    entities._present_columns["comments"] = (
        set(COMMENT_COLUMNS)
        | set(entities._present_columns.get("comments", set()))
        | {text_key, hash_key, language_key}
        | {key for row in entities.comments for key in row}
    )


def _set_comment_translation(row: dict, target: str, text: str | None) -> None:
    text_key, hash_key, language_key = translation_columns(target)
    row[text_key] = text
    row[hash_key] = source_text_hash(str(row["answer_text"])) if text is not None else None
    row[language_key] = (str(row.get("user_language") or "").strip() or None) if text is not None else None


def _register_comment_target(entities: EntitySet, survey_id: str, target: str) -> None:
    manifest = entities.survey_manifests.get(survey_id)
    if manifest is None:
        return
    registry = manifest.setdefault("languages", {})
    targets = registry.setdefault("prepared_languages", [])
    if target not in targets:
        targets.append(target)


def _finalize_comments(entities: EntitySet) -> EntitySet:
    entities.comments = build_comments(entities)
    entities._present_columns["comments"] = (
        set(COMMENT_COLUMNS)
        | set(entities._present_columns.get("comments", set()))
        | {key for row in entities.comments for key in row}
    )
    entities._present_entities.add("comments")
    return entities


def import_comment_translation_records(entities: EntitySet, records: Iterable[Mapping[str, object]]) -> EntitySet:
    """Import prepared records after checking original-text hashes and identity."""
    prepared = deepcopy(entities)
    prepared.comments = build_comments(prepared)
    comments = {str(row["response_answer_id"]): row for row in prepared.comments}
    incoming: set[tuple[str, str]] = set()
    required = {"response_answer_id", "target_language", "source_text_hash", "translated_text"}
    for record in records:
        if set(record) != required:
            raise ValueError(
                "Translation input must have exactly response_answer_id, target_language, "
                "source_text_hash, translated_text"
            )
        answer_id, target = record["response_answer_id"], record["target_language"]
        if not isinstance(answer_id, str) or answer_id not in comments:
            raise ValueError(f"Unknown written response answer: {answer_id}")
        if not isinstance(target, str):
            raise ValueError("Translation target_language must be a nonblank language code")
        translation_columns(target)
        row = comments[answer_id]
        if record["source_text_hash"] != source_text_hash(str(row["answer_text"])):
            raise ValueError(f"Translation source hash does not match answer {answer_id}")
        translated = record["translated_text"]
        if not isinstance(translated, str) or not translated.strip():
            raise ValueError(f"Translation text must be nonblank for {answer_id}")
        key = answer_id, target
        if key in incoming:
            raise ValueError(f"Duplicate translation for {answer_id} in {target}")
        incoming.add(key)
        _set_comment_translation(row, target, translated)
        _register_comment_target(prepared, str(row["survey_id"]), target)
    return _finalize_comments(prepared)


def prepare_translations(
    entities: EntitySet,
    *,
    language: str | None = None,
    translate: TranslationCallback | None = None,
    question: TranslationCallback | None = None,
    field: TranslationCallback | None = None,
    answer_option: TranslationCallback | None = None,
    comment: TranslationCallback | None = None,
) -> EntitySet:
    """Return a prepared collection; supplied translators own all external calls."""
    callbacks: dict[TranslationKind, TranslationCallback | None] = {
        "question": question or translate,
        "field": field or translate,
        "answer_option": answer_option or translate,
        "comment": comment or translate,
    }
    prepared = deepcopy(entities)
    if not any(callbacks.values()):
        return prepared
    for survey in prepared.surveys:
        survey_id = str(survey["survey_id"])
        target = _target(prepared, survey_id, language)
        _register_comment_target(prepared, survey_id, target)
        _definition_labels(prepared, survey_id, target, callbacks)
        _written_answers(prepared, survey_id, target, callbacks["comment"])
    return _finalize_comments(prepared)
