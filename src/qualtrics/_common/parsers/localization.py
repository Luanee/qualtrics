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
