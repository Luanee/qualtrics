from __future__ import annotations

import json

from .comment_translations import TRANSLATION_COLUMNS, translation_id
from .comments import COMMENT_COLUMNS, build_comments
from .entities import CORE_ENTITY_NAMES, EntitySet
from .response_merge import merge_response_columns
from .translation_columns import prepared_targets, target_from_column, translation_columns

PRIMARY_KEYS = {
    "surveys": "survey_id",
    "sections": "section_id",
    "question_catalog": "question_catalog_id",
    "question_field_catalog": "question_field_catalog_id",
    "questions": "question_id",
    "answer_options": "answer_option_id",
    "question_fields": "question_field_id",
    "responses": "response_id",
    "response_answers": "response_answer_id",
    "comments": "response_answer_id",
    "comment_translations": "comment_translation_id",
}

REQUIRED_COLUMNS = {
    "surveys": {"survey_id", "survey_name"},
    "sections": {"section_id", "survey_id", "section_external_id"},
    "question_catalog": {"question_catalog_id", "question_text", "canonical_question_type"},
    "question_field_catalog": {"question_field_catalog_id", "question_catalog_id", "field_text"},
    "questions": {"question_id", "question_external_id", "survey_id", "question_catalog_id"},
    "answer_options": {
        "answer_option_id",
        "answer_id",
        "answer_external_id",
        "answer_code",
        "answer_order",
        "question_id",
        "question_field_id",
        "field_id",
        "survey_id",
    },
    "question_fields": {"question_field_id", "question_id", "question_field_catalog_id", "answer_value_type"},
    "responses": {"response_id", "response_external_id", "survey_id"},
    "response_answers": {
        "response_answer_id",
        "response_id",
        "question_id",
        "question_field_id",
        "field_id",
        "question_catalog_id",
        "question_field_catalog_id",
        "answer_value_type",
        "answer_text",
        "survey_id",
        "answer_option_id",
        "answer_numeric",
        "answer_boolean",
        "is_selected",
    },
    "comments": set(COMMENT_COLUMNS),
    "comment_translations": set(TRANSLATION_COLUMNS),
}

NULLABLE_REQUIRED_COLUMNS = {
    "response_answers": {"answer_option_id", "answer_numeric", "answer_boolean", "is_selected"},
    "comments": {"raw_value", "user_language"},
    "comment_translations": {"source_language"},
}

RELATIONSHIPS = (
    ("sections", "survey_id", "surveys", "survey_id"),
    ("questions", "survey_id", "surveys", "survey_id"),
    ("questions", "section_id", "sections", "section_id"),
    ("questions", "question_catalog_id", "question_catalog", "question_catalog_id"),
    ("question_fields", "question_id", "questions", "question_id"),
    ("question_fields", "survey_id", "surveys", "survey_id"),
    ("question_fields", "question_field_catalog_id", "question_field_catalog", "question_field_catalog_id"),
    ("question_fields", "question_catalog_id", "question_catalog", "question_catalog_id"),
    ("answer_options", "question_id", "questions", "question_id"),
    ("answer_options", "question_field_id", "question_fields", "question_field_id"),
    ("answer_options", "field_id", "question_fields", "question_field_id"),
    ("answer_options", "survey_id", "surveys", "survey_id"),
    ("responses", "survey_id", "surveys", "survey_id"),
    ("response_answers", "response_id", "responses", "response_id"),
    ("response_answers", "survey_id", "surveys", "survey_id"),
    ("response_answers", "question_id", "questions", "question_id"),
    ("response_answers", "question_field_id", "question_fields", "question_field_id"),
    ("response_answers", "question_catalog_id", "question_catalog", "question_catalog_id"),
    ("response_answers", "question_field_catalog_id", "question_field_catalog", "question_field_catalog_id"),
    ("response_answers", "answer_option_id", "answer_options", "answer_option_id"),
    ("comments", "response_answer_id", "response_answers", "response_answer_id"),
    ("comments", "response_id", "responses", "response_id"),
    ("comments", "survey_id", "surveys", "survey_id"),
    ("comments", "question_id", "questions", "question_id"),
    ("comments", "question_field_id", "question_fields", "question_field_id"),
    ("comment_translations", "response_answer_id", "response_answers", "response_answer_id"),
    ("comment_translations", "survey_id", "surveys", "survey_id"),
)


def validate_entity_set(entities: EntitySet, *, strict: bool = False) -> None:
    if strict:
        missing = [name for name in CORE_ENTITY_NAMES if name not in entities._present_entities]
        if missing:
            raise ValueError(f"Incomplete strict entity contract: {', '.join(missing)}")
        if not entities.surveys:
            raise ValueError("Incomplete strict entity contract: surveys must contain one or more rows")
        for name, columns in entities._present_columns.items():
            missing_columns = REQUIRED_COLUMNS[name] - columns
            if missing_columns:
                raise ValueError(f"{name} schema is missing required columns: {', '.join(sorted(missing_columns))}")
    for name, key in PRIMARY_KEYS.items():
        rows = getattr(entities, name)
        seen: set[str] = set()
        for row in rows:
            if strict:
                missing_columns = REQUIRED_COLUMNS[name] - row.keys()
                if missing_columns:
                    raise ValueError(f"{name} row is missing required columns: {', '.join(sorted(missing_columns))}")
                null_columns = {
                    column
                    for column in REQUIRED_COLUMNS[name] - NULLABLE_REQUIRED_COLUMNS.get(name, set())
                    if row.get(column) is None
                }
                if null_columns:
                    raise ValueError(f"{name} row has null required columns: {', '.join(sorted(null_columns))}")
            value = str(row.get(key) or "")
            if not value:
                raise ValueError(f"{name} row is missing {key}")
            if value in seen:
                raise ValueError(f"{name} contains duplicate {key} {value}")
            seen.add(value)
    for child, foreign_key, parent, parent_key in RELATIONSHIPS:
        child_rows = getattr(entities, child)
        parent_rows = getattr(entities, parent)
        if not child_rows:
            continue
        parent_ids = {str(row[parent_key]) for row in parent_rows}
        for row in child_rows:
            value = row.get(foreign_key)
            if value is not None and str(value) not in parent_ids:
                raise ValueError(f"{child} {foreign_key} {value} has no parent in {parent}.{parent_key}")
    if strict:
        base_questions = {
            (str(row["survey_id"]), str(row["question_external_id"])): row
            for row in entities.questions
            if not row.get("is_localized")
        }
        base_fields = {
            (str(row["survey_id"]), str(row.get("question_external_id")), str(row.get("field_external_id"))): row
            for row in entities.question_fields
            if not row.get("is_localized")
        }
        all_questions = {str(row["question_id"]): row for row in entities.questions}
        for name in ("questions", "question_fields", "answer_options"):
            for row in getattr(entities, name):
                if not row.get("is_localized"):
                    continue
                survey_id = str(row["survey_id"])
                language_code = row.get("language_code")
                registry = entities.survey_manifests.get(survey_id, {}).get("languages", {})
                if (
                    not isinstance(language_code, str)
                    or not language_code
                    or not isinstance(registry, dict)
                    or language_code
                    not in (set(registry.get("all_languages", [])) | set(registry.get("prepared_languages", [])))
                    or language_code == registry.get("base_language")
                ):
                    raise ValueError(f"{name} localized row has invalid language_code")
                base_question = base_questions.get((survey_id, str(row["question_external_id"])))
                catalog_id = (
                    all_questions[str(row["question_id"])]["question_catalog_id"]
                    if name == "answer_options"
                    else row["question_catalog_id"]
                )
                if base_question is None or str(catalog_id) != str(base_question["question_catalog_id"]):
                    raise ValueError(f"{name} localized row must retain the base question catalog")
                if name == "question_fields":
                    base_field = base_fields.get((
                        survey_id,
                        str(row["question_external_id"]),
                        str(row["field_external_id"]),
                    ))
                    if (
                        base_field is None
                        or row["question_field_catalog_id"] != base_field["question_field_catalog_id"]
                    ):
                        raise ValueError("Localized question field must retain the base field catalog")
        localized_question_ids = {str(row["question_id"]) for row in entities.questions if row.get("is_localized")}
        if any(str(row["question_id"]) in localized_question_ids for row in entities.response_answers):
            raise ValueError("Response answers must link to base questions")
        fields = {str(row["question_field_id"]): row for row in entities.question_fields}
        responses = {str(row["response_id"]): row for row in entities.responses}
        options = {str(row["answer_option_id"]): row for row in entities.answer_options}
        for option in entities.answer_options:
            required_values = (
                "answer_option_id",
                "answer_id",
                "answer_external_id",
                "answer_code",
                "answer_text",
                "answer_order",
                "question_id",
                "question_field_id",
                "field_id",
                "survey_id",
            )
            missing_values = [column for column in required_values if option.get(column) is None]
            if missing_values:
                raise ValueError(f"answer_options row has null required columns: {', '.join(missing_values)}")
            question_field_id = str(option["question_field_id"])
            if str(option["field_id"]) != question_field_id:
                raise ValueError("answer_options field_id must equal question_field_id")
            field = fields[question_field_id]
            if str(option["question_id"]) != str(field["question_id"]) or str(option["survey_id"]) != str(
                field["survey_id"]
            ):
                raise ValueError("answer_options question and survey must match the referenced question field")
        for answer in entities.response_answers:
            question_field_id = str(answer["question_field_id"])
            field = fields[question_field_id]
            if str(answer["field_id"]) != question_field_id:
                raise ValueError("response_answers field_id must equal question_field_id")
            lineage = (
                ("question_id", "question_id"),
                ("survey_id", "survey_id"),
                ("question_catalog_id", "question_catalog_id"),
                ("question_field_catalog_id", "question_field_catalog_id"),
            )
            if any(str(answer[answer_key]) != str(field[field_key]) for answer_key, field_key in lineage):
                raise ValueError("response_answers lineage must match the referenced question field")
            response = responses[str(answer["response_id"])]
            if str(answer["survey_id"]) != str(response["survey_id"]):
                raise ValueError("response_answers survey must match the referenced response")
            option_id = answer.get("answer_option_id")
            if option_id is None:
                continue
            option = options[str(option_id)]
            if str(option["question_field_id"]) != str(answer["question_field_id"]):
                raise ValueError("response_answers option must belong to the referenced question field")
    if entities.comment_translations or "comment_translations" in entities._present_entities:
        columns = entities._present_columns.get("comment_translations")
        if columns is not None and columns != set(TRANSLATION_COLUMNS):
            raise ValueError("comment_translations schema must contain exactly the fixed translation columns")
        comments = {str(row["response_answer_id"]): row for row in build_comments(entities)}
        for row in entities.comment_translations:
            answer_id = str(row.get("response_answer_id") or "")
            target = row.get("target_language")
            digest = row.get("source_text_hash")
            translated = row.get("translated_text")
            if answer_id not in comments:
                raise ValueError("comment_translations must reference a written answer")
            if not isinstance(target, str) or not target.strip() or target != target.strip():
                raise ValueError("comment_translations target_language must be a nonblank code")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ValueError("comment_translations source_text_hash must be a SHA-256 hex digest")
            if not isinstance(translated, str) or not translated.strip():
                raise ValueError("comment_translations translated_text must be nonblank")
            if row.get("comment_translation_id") != translation_id(answer_id, target):
                raise ValueError("comment_translations ID must derive from answer and target language")
            if str(row.get("survey_id")) != str(comments[answer_id]["survey_id"]):
                raise ValueError("comment_translations survey must match the written answer")
    if entities.comments or "comments" in entities._present_entities:
        columns = entities._present_columns.get("comments")
        if columns is not None:
            if not set(COMMENT_COLUMNS) <= columns:
                raise ValueError("comments schema is missing fixed comment columns")
            targets = prepared_targets(columns)
            allowed = set(COMMENT_COLUMNS) | {column for target in targets for column in translation_columns(target)}
            if columns != allowed:
                raise ValueError("comments schema has incomplete or unknown translation columns")
        for row in entities.comments:
            for key in row:
                if key not in COMMENT_COLUMNS and target_from_column(key) is None:
                    raise ValueError("comments contains an unknown column")
        expected = {row["response_answer_id"]: row for row in build_comments(entities)}
        supplied = {row["response_answer_id"]: row for row in entities.comments}
        if supplied != expected:
            raise ValueError("comments must match the projection of response_answers and responses")


def _catalog_comparison_row(name: str, row: dict[str, object]) -> dict[str, object]:
    """Ignore representative labels only when canonical identity evidence is present."""
    if name == "question_catalog":
        content_key, display_key = "normalized_question_content", "question_text"
    else:
        content_key, display_key = "normalized_field_content", "field_text"
        # Field identity includes its parent; missing parents cannot prove equivalence.
        if not row.get("question_catalog_id"):
            return row
    stored_content = row.get(content_key)
    if not isinstance(stored_content, str):
        return row
    try:
        content = json.loads(stored_content)
    except ValueError:
        return row
    if not isinstance(content, dict) or not content:
        return row
    # Stored content is already canonical: normalizing again can change HTML entities.
    # Serialize its structure to retain JSON scalar type distinctions.
    # Other metadata (including field parents and question types) stays strict.
    return {
        **{key: value for key, value in row.items() if key != display_key},
        content_key: json.dumps(content, ensure_ascii=False, sort_keys=True),
    }


def merge_entity_sets(entity_sets: list[EntitySet]) -> EntitySet:
    """Combine surveys, retaining the first label for equivalent canonical catalogs."""
    result = EntitySet()
    if entity_sets:
        result._present_entities = set.intersection(*(item._present_entities for item in entity_sets))
        result._present_columns = {
            name: set.intersection(
                *(item._present_columns[name] for item in entity_sets if name in item._present_columns)
            )
            for name in CORE_ENTITY_NAMES
            if all(name in item._present_columns for item in entity_sets)
        }
    survey_ids = [str(survey["survey_id"]) for item in entity_sets for survey in item.surveys]
    duplicates = {survey_id for survey_id in survey_ids if survey_ids.count(survey_id) > 1}
    if duplicates:
        raise ValueError(f"Duplicate survey_id values: {', '.join(sorted(duplicates))}")
    for name in CORE_ENTITY_NAMES:
        rows = [row for item in entity_sets for row in getattr(item, name)]
        if name in {"question_catalog", "question_field_catalog"}:
            id_key = f"{name}_id"
            unique: dict[str, dict[str, object]] = {}
            for row in rows:
                identifier = str(row[id_key])
                if identifier in unique:
                    if _catalog_comparison_row(name, unique[identifier]) != _catalog_comparison_row(name, row):
                        raise ValueError(f"{name} catalog collision for {identifier}")
                else:
                    unique[identifier] = row
            rows = list(unique.values())
        setattr(result, name, rows)
    result.surveys, result.responses, response_columns, result.survey_manifests = merge_response_columns(entity_sets)
    if response_columns:
        result._present_columns["responses"] = response_columns
    result.comment_translations = [dict(row) for item in entity_sets for row in item.comment_translations]
    result.comments = build_comments(result)
    result._present_columns["comments"] = set(COMMENT_COLUMNS) | {key for row in result.comments for key in row}
    if result.comment_translations:
        result._present_entities.add("comment_translations")
        result._present_columns["comment_translations"] = set(TRANSLATION_COLUMNS)
    return result
