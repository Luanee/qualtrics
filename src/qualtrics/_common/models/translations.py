"""Prepare display text through a user-owned translator without changing facts."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

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
            row[text_key] = None
            row[hash_key] = None
            row[language_key] = None
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
        row[text_key] = _call(callback, request)
        row[hash_key] = digest
        row[language_key] = source_language
    for row in entities.comments:
        row.setdefault(text_key, None)
        row.setdefault(hash_key, None)
        row.setdefault(language_key, None)
    entities._present_columns["comments"] = (
        set(COMMENT_COLUMNS)
        | set(entities._present_columns.get("comments", set()))
        | {text_key, hash_key, language_key}
        | {key for row in entities.comments for key in row}
    )


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
        manifest = prepared.survey_manifests.get(survey_id)
        if manifest is not None:
            registry = manifest.setdefault(
                "languages",
                {
                    "base_language": survey.get("default_language"),
                    "available_languages": [],
                    "all_languages": [str(survey["default_language"])] if survey.get("default_language") else [],
                },
            )
            targets = registry.setdefault("prepared_languages", [])
            if target not in targets:
                targets.append(target)
        _definition_labels(prepared, survey_id, target, callbacks)
        _written_answers(prepared, survey_id, target, callbacks["comment"])
    prepared.comments = build_comments(prepared)
    prepared._present_columns["comments"] = (
        set(COMMENT_COLUMNS)
        | set(prepared._present_columns.get("comments", set()))
        | {key for row in prepared.comments for key in row}
    )
    return prepared
