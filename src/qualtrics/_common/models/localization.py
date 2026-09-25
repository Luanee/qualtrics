"""Materialize locale-specific entity rows after parsing."""

from __future__ import annotations

from .entities import EntitySet
from .identity import entity_id


def ensure_localized_entities(entities: EntitySet, survey_id: str, language_code: str) -> None:
    """Add fallback locale rows for a requested language absent from the QSF."""
    registry = entities.survey_manifests.get(survey_id, {}).get("languages", {})
    base_code = registry.get("base_language") if isinstance(registry, dict) else None
    if str(base_code or "").casefold() == language_code.casefold():
        return
    base_questions = [
        row for row in entities.questions if str(row["survey_id"]) == survey_id and not row.get("is_localized")
    ]
    base_fields = [
        row for row in entities.question_fields if str(row["survey_id"]) == survey_id and not row.get("is_localized")
    ]
    base_options = [
        row for row in entities.answer_options if str(row["survey_id"]) == survey_id and not row.get("is_localized")
    ]
    question_variants = {
        str(row["question_external_id"]): row
        for row in entities.questions
        if str(row["survey_id"]) == survey_id
        and row.get("is_localized")
        and str(row.get("language_code") or "").casefold() == language_code.casefold()
    }
    for base in base_questions:
        native_id = str(base["question_external_id"])
        if native_id in question_variants:
            continue
        localized = {
            **base,
            "question_id": entity_id("question", survey_id, native_id, language_code),
            "language_code": language_code,
            "label_source_language": base_code,
            "label_origin": "fallback",
            "is_localized": True,
        }
        entities.questions.append(localized)
        question_variants[native_id] = localized
    field_variants = {
        (str(row["question_external_id"]), str(row.get("field_external_id"))): row
        for row in entities.question_fields
        if str(row["survey_id"]) == survey_id
        and row.get("is_localized")
        and str(row.get("language_code") or "").casefold() == language_code.casefold()
    }
    for base in base_fields:
        key = (str(base["question_external_id"]), str(base.get("field_external_id")))
        if key in field_variants:
            continue
        localized_question_id = question_variants[key[0]]["question_id"]
        localized_field_id = entity_id("question-field", localized_question_id, base["field_external_id"])
        localized = {
            **base,
            "question_id": localized_question_id,
            "question_field_id": localized_field_id,
            "field_id": localized_field_id,
            "import_external_id": None,
            "source_column_index": None,
            "language_code": language_code,
            "label_source_language": base_code,
            "label_origin": "fallback",
            "is_localized": True,
        }
        entities.question_fields.append(localized)
        field_variants[key] = localized
    base_fields_by_id = {str(row["question_field_id"]): row for row in base_fields}
    option_variants = {
        (str(row["question_field_id"]), str(row["answer_external_id"]))
        for row in entities.answer_options
        if str(row["survey_id"]) == survey_id
        and row.get("is_localized")
        and str(row.get("language_code") or "").casefold() == language_code.casefold()
    }
    for base in base_options:
        base_field = base_fields_by_id[str(base["question_field_id"])]
        key = (str(base["question_external_id"]), str(base_field.get("field_external_id")))
        localized_field_id = field_variants[key]["question_field_id"]
        option_key = (str(localized_field_id), str(base["answer_external_id"]))
        if option_key in option_variants:
            continue
        entities.answer_options.append({
            **base,
            "question_id": question_variants[key[0]]["question_id"],
            "question_field_id": localized_field_id,
            "field_id": localized_field_id,
            "answer_option_id": entity_id("answer-option", localized_field_id, base["answer_external_id"]),
            "source_import_id": None,
            "language_code": language_code,
            "label_source_language": base_code,
            "label_origin": "fallback",
            "is_localized": True,
        })
        option_variants.add(option_key)
