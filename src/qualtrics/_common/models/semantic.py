from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any

from .comments import COMMENT_COLUMNS, build_comments
from .entities import EntitySet
from .entity_set import validate_entity_set
from .identity import entity_id
from .translation_columns import (
    prepared_targets,
    source_text_hash,
    translation_is_current,
    translation_is_current_column,
)

SEMANTIC_TABLE_NAMES = (
    "fact_responses",
    "fact_response_answers",
    "dim_surveys",
    "dim_questions",
    "dim_answer_options",
    "fact_comments",
    "dim_display_languages",
    "dim_question_labels",
    "dim_answer_option_labels",
)


@dataclass
class SemanticModel:
    survey_manifests: dict[str, dict[str, Any]] = field(default_factory=dict, kw_only=True)
    prepared_comment_targets: tuple[str, ...] = field(default_factory=tuple, kw_only=True)
    fact_responses: list[dict[str, Any]] = field(default_factory=list)
    fact_response_answers: list[dict[str, Any]] = field(default_factory=list)
    dim_surveys: list[dict[str, Any]] = field(default_factory=list)
    dim_questions: list[dict[str, Any]] = field(default_factory=list)
    dim_answer_options: list[dict[str, Any]] = field(default_factory=list)
    fact_comments: list[dict[str, Any]] = field(default_factory=list)
    dim_display_languages: list[dict[str, Any]] = field(default_factory=list)
    dim_question_labels: list[dict[str, Any]] = field(default_factory=list)
    dim_answer_option_labels: list[dict[str, Any]] = field(default_factory=list)


def _language_dimensions(
    entities: EntitySet,
    active_fields: list[dict[str, Any]],
    active_options: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    questions = {
        (str(row["survey_id"]), str(row["question_external_id"]), str(row.get("language_code") or "").casefold()): row
        for row in entities.questions
    }
    base_questions = {
        (str(row["survey_id"]), str(row["question_external_id"])): row
        for row in entities.questions
        if not row.get("is_localized")
    }
    fields = {
        (
            str(row["survey_id"]),
            str(row["question_external_id"]),
            str(row.get("field_external_id")),
            str(row.get("language_code") or "").casefold(),
        ): row
        for row in entities.question_fields
    }
    fields_by_id = {str(row["question_field_id"]): row for row in entities.question_fields}
    options = {
        (
            str(row["survey_id"]),
            str(row["question_external_id"]),
            str(fields_by_id[str(row["question_field_id"])].get("field_external_id")),
            str(row["answer_external_id"]),
            str(row.get("language_code") or "").casefold(),
        ): row
        for row in entities.answer_options
    }

    def current_label(variant: dict[str, Any], base_row: dict[str, Any], key: str) -> dict[str, Any]:
        if variant.get("label_origin") == "callback" and variant.get("label_source_text_hash") != source_text_hash(
            str(base_row.get(key) or "")
        ):
            return base_row
        return variant

    registries = {
        str(survey["survey_id"]): entities.survey_manifests.get(str(survey["survey_id"]), {}).get("languages", {})
        for survey in entities.surveys
    }
    translation_targets: dict[str, set[str]] = {
        survey_id: {str(code).upper() for code in registry.get("prepared_languages", [])}
        for survey_id, registry in registries.items()
        if isinstance(registry, dict)
    }
    for row in entities.comments:
        translation_targets.setdefault(str(row["survey_id"]), set()).update(
            target.upper() for target in prepared_targets(row)
        )
    languages = sorted(
        {
            str(code).upper()
            for registry in registries.values()
            if isinstance(registry, dict)
            for code in registry.get("all_languages", [])
        }
        | {code for targets in translation_targets.values() for code in targets}
    )

    def is_available(survey_id: str, language: str) -> bool:
        registry = registries[survey_id]
        return language in translation_targets.get(survey_id, set()) or (
            isinstance(registry, dict)
            and (
                language == str(registry.get("base_language") or "").upper()
                or language in {str(code).upper() for code in registry.get("available_languages", [])}
            )
        )

    display_languages = [
        {
            "language_code": language,
            "is_available": any(is_available(survey_id, language) for survey_id in registries),
            "available_survey_count": sum(is_available(survey_id, language) for survey_id in registries),
            "defined_survey_count": sum(
                isinstance(registry, dict)
                and language in {str(code).upper() for code in registry.get("all_languages", [])}
                for registry in registries.values()
            ),
        }
        for language in languages
    ]
    question_labels: list[dict[str, Any]] = []
    option_labels: list[dict[str, Any]] = []
    for survey in entities.surveys:
        survey_id = str(survey["survey_id"])
        registry = registries[survey_id]
        base = registry.get("base_language") if isinstance(registry, dict) else None
        for language in languages:
            for field_dimension in active_fields:
                if str(field_dimension["survey_id"]) != survey_id:
                    continue
                native_question = str(field_dimension["question_external_id"])
                native_field = str(field_dimension.get("field_external_id"))
                base_question = base_questions.get((survey_id, native_question))
                question = questions.get((survey_id, native_question, language.casefold())) or questions.get((
                    survey_id,
                    native_question,
                    str(base or "").casefold(),
                ))
                translated_field = (
                    fields.get((survey_id, native_question, native_field, language.casefold())) or field_dimension
                )
                if question is None or base_question is None:
                    continue
                question = current_label(question, base_question, "question_text")
                translated_field = current_label(translated_field, field_dimension, "field_text")
                question_labels.append({
                    "question_field_label_id": entity_id(
                        "question-field-label", field_dimension["question_field_id"], language
                    ),
                    "survey_id": survey_id,
                    "language_code": language,
                    "question_field_id": field_dimension["question_field_id"],
                    "question_id": field_dimension["question_id"],
                    "question_external_id": native_question,
                    "question_text": question["question_text"],
                    "field_text": translated_field["field_text"],
                    "question_label_source_language": question.get("label_source_language") or base,
                    "field_label_source_language": translated_field.get("label_source_language") or base,
                })
            for option in active_options:
                if str(option["survey_id"]) != survey_id:
                    continue
                base_field = fields_by_id[str(option["question_field_id"])]
                native_question = str(option["question_external_id"])
                native_field = str(base_field.get("field_external_id"))
                native_option = str(option["answer_external_id"])
                translated_option = options.get((
                    survey_id,
                    native_question,
                    native_field,
                    native_option,
                    language.casefold(),
                ))
                translated_option = translated_option or option
                translated_option = current_label(translated_option, option, "answer_text")
                option_labels.append({
                    "answer_option_label_id": entity_id("answer-option-label", option["answer_option_id"], language),
                    "survey_id": survey_id,
                    "language_code": language,
                    "answer_option_id": option["answer_option_id"],
                    "question_field_id": option["question_field_id"],
                    "question_external_id": native_question,
                    "answer_external_id": native_option,
                    "answer_text": translated_option["answer_text"],
                    "label_source_language": translated_option.get("label_source_language") or base,
                })
    return display_languages, question_labels, option_labels


def build_semantic_model(entities: EntitySet) -> SemanticModel:
    comments = build_comments(entities)
    entities = replace(
        entities,
        comments=comments,
        _present_columns={
            **entities._present_columns,
            "comments": (
                set(COMMENT_COLUMNS)
                | set(entities._present_columns.get("comments", set()))
                | {key for row in comments for key in row}
            ),
        },
    )
    validate_entity_set(entities, strict=True)
    questions = {str(row["question_id"]): row for row in entities.questions}
    sections = {str(row["section_id"]): row for row in entities.sections}
    question_catalog = {str(row["question_catalog_id"]): row for row in entities.question_catalog}
    field_catalog = {str(row["question_field_catalog_id"]): row for row in entities.question_field_catalog}
    dimensions = []
    for field_row in entities.question_fields:
        if field_row.get("is_definition_only") or field_row.get("is_localized"):
            continue
        question = questions[str(field_row["question_id"])]
        section = sections.get(str(question.get("section_id") or ""), {})
        catalog = question_catalog.get(str(question["question_catalog_id"]), {})
        field_definition = field_catalog.get(str(field_row["question_field_catalog_id"]), {})
        dimensions.append({**catalog, **field_definition, **section, **question, **field_row})
    active_options = [
        dict(row)
        for row in entities.answer_options
        if not row.get("is_definition_only") and not row.get("is_localized")
    ]
    display_languages, question_labels, option_labels = _language_dimensions(entities, dimensions, active_options)
    fact_comments = [
        {
            **dict(row),
            **{
                translation_is_current_column(target): translation_is_current(row, target)
                for target in prepared_targets(row)
            },
        }
        for row in entities.comments
    ]
    return SemanticModel(
        survey_manifests=deepcopy(entities.survey_manifests),
        prepared_comment_targets=tuple(sorted(prepared_targets(entities._present_columns.get("comments", set())))),
        fact_responses=[dict(row) for row in entities.responses],
        fact_response_answers=[dict(row) for row in entities.response_answers],
        dim_surveys=[dict(row) for row in entities.surveys],
        dim_questions=dimensions,
        dim_answer_options=active_options,
        fact_comments=fact_comments,
        dim_display_languages=display_languages,
        dim_question_labels=question_labels,
        dim_answer_option_labels=option_labels,
    )
