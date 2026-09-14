"""Materialize locale-specific definition labels without duplicating answer facts."""

from __future__ import annotations

from collections.abc import Mapping

from ..models.entities import EntitySet
from ..models.identity import entity_id
from .identity import _clean


def _translated_display(translation: Mapping[str, object], collection: str, native_id: object) -> str | None:
    values = translation.get(collection)
    if not isinstance(values, dict):
        return None
    value = values.get(str(native_id))
    label = _clean(value.get("Display") if isinstance(value, dict) else value)
    return label or None


def _translation(definition: Mapping[str, object], language_code: str) -> dict[str, object]:
    languages = definition.get("Language")
    candidate = languages.get(language_code) if isinstance(languages, dict) else None
    return candidate if isinstance(candidate, dict) else {}


def append_localized_entities(
    entities: EntitySet,
    definitions: Mapping[str, dict[str, object]],
    languages: Mapping[str, object],
) -> None:
    """Clone base definitions per survey language with stable, locale-scoped IDs."""
    base_language = languages.get("base_language")
    base_code = str(base_language) if base_language is not None else None
    all_codes = languages.get("all_languages")
    locale_codes = [str(code) for code in all_codes if code != base_code] if isinstance(all_codes, list) else []
    base_questions = tuple(entities.questions)
    base_fields = tuple(entities.question_fields)
    base_options = tuple(entities.answer_options)
    questions_by_id = {str(row["question_id"]): row for row in base_questions}
    field_by_id = {str(row["question_field_id"]): row for row in base_fields}
    question_ids: dict[tuple[str, str], str] = {}
    field_ids: dict[tuple[str, str], str] = {}

    for question in base_questions:
        question["language_code"] = base_code
        question["label_source_language"] = base_code
        question["is_localized"] = False
        native_id = str(question["question_external_id"])
        definition = definitions.get(native_id, {})
        for locale in locale_codes:
            translated = _translation(definition, locale)
            label = _clean(translated.get("QuestionText"))
            localized_id = entity_id("question", question["survey_id"], native_id, locale)
            question_ids[(str(question["question_id"]), locale)] = localized_id
            entities.questions.append({
                **question,
                "question_id": localized_id,
                "question_text": label or question["question_text"],
                "language_code": locale,
                "label_source_language": locale if label else base_code,
                "is_localized": True,
            })

    for field in base_fields:
        field["language_code"] = base_code
        field["label_source_language"] = base_code
        field["is_localized"] = False
        question = questions_by_id[str(field["question_id"])]
        definition = definitions.get(str(question["question_external_id"]), {})
        for locale in locale_codes:
            translated = _translation(definition, locale)
            choice_label = _translated_display(translated, "Choices", field.get("choice_external_id"))
            question_label = _clean(translated.get("QuestionText"))
            if field.get("is_text_field"):
                # QSF translates the choice, not the export's companion-field suffix.
                label = None
            elif choice_label:
                label = choice_label
            elif question_label and field.get("field_text") == question.get("question_text"):
                label = question_label
            else:
                label = None
            localized_question_id = question_ids[(str(field["question_id"]), locale)]
            localized_field_id = entity_id("question-field", localized_question_id, field["field_external_id"])
            field_ids[(str(field["question_field_id"]), locale)] = localized_field_id
            entities.question_fields.append({
                **field,
                "question_id": localized_question_id,
                "question_field_id": localized_field_id,
                "field_id": localized_field_id,
                "field_text": label or field["field_text"],
                "statement_text": choice_label or field.get("statement_text"),
                "import_external_id": None,
                "source_column_index": None,
                "language_code": locale,
                "label_source_language": locale if label else base_code,
                "is_localized": True,
            })

    for option in base_options:
        option["language_code"] = base_code
        option["label_source_language"] = base_code
        option["is_localized"] = False
        question = questions_by_id[str(option["question_id"])]
        field = field_by_id[str(option["question_field_id"])]
        definition = definitions.get(str(question["question_external_id"]), {})
        collection = "Answers" if str(question.get("canonical_question_type")) == "matrix" else "Choices"
        for locale in locale_codes:
            translated = _translation(definition, locale)
            label = _translated_display(translated, collection, option["answer_external_id"])
            localized_field_id = field_ids[(str(field["question_field_id"]), locale)]
            entities.answer_options.append({
                **option,
                "question_id": question_ids[(str(question["question_id"]), locale)],
                "question_field_id": localized_field_id,
                "field_id": localized_field_id,
                "answer_option_id": entity_id("answer-option", localized_field_id, option["answer_external_id"]),
                "answer_text": label or option["answer_text"],
                "choice_value": label or option.get("choice_value"),
                "value": option.get("recode_value")
                if option.get("recode_value") is not None
                else label or option.get("value"),
                "source_import_id": None,
                "language_code": locale,
                "label_source_language": locale if label else base_code,
                "is_localized": True,
            })


def link_translated_answers(entities: EntitySet) -> None:
    """Resolve respondent-language display aliases to base options, never locale IDs."""
    fields = {str(row["question_field_id"]): row for row in entities.question_fields}
    base_fields = {
        (str(row["survey_id"]), str(row["question_external_id"]), str(row["field_external_id"])): row
        for row in entities.question_fields
        if not row.get("is_localized")
    }
    base_options = {
        (str(row["question_field_id"]), str(row["answer_external_id"])): row
        for row in entities.answer_options
        if not row.get("is_localized")
    }
    protected_aliases: set[tuple[str, str]] = set()
    translated_aliases: dict[tuple[str, str, str], set[str]] = {}
    for option in entities.answer_options:
        if not option.get("is_localized"):
            field_id = str(option["question_field_id"])
            for key in ("answer_external_id", "recode_value"):
                value = option.get(key)
                if value is not None:
                    protected_aliases.add((field_id, str(value).casefold()))
            continue
        language = str(option.get("language_code") or "").casefold()
        if str(option.get("label_source_language") or "").casefold() != language:
            continue
        field = fields[str(option["question_field_id"])]
        base_field = base_fields.get((
            str(field["survey_id"]),
            str(field["question_external_id"]),
            str(field["field_external_id"]),
        ))
        if base_field is None:
            continue
        base_field_id = str(base_field["question_field_id"])
        native_id = str(option["answer_external_id"])
        base_option = base_options.get((base_field_id, native_id))
        label = _clean(option.get("answer_text")).casefold()
        if base_option is not None and label:
            translated_aliases.setdefault((base_field_id, language, label), set()).add(
                str(base_option["answer_option_id"])
            )

    for answer in entities.response_answers:
        if answer.get("answer_value_type") != "categorical":
            continue
        language = str(answer.get("user_language") or "").casefold()
        label = _clean(answer.get("answer_text")).casefold()
        if not language or not label:
            continue
        field_id = str(answer["question_field_id"])
        if (field_id, label) in protected_aliases:
            continue
        candidates = translated_aliases.get((field_id, language, label))
        if candidates is not None:
            answer["answer_option_id"] = next(iter(candidates)) if len(candidates) == 1 else None
