from __future__ import annotations

from .entities import ENTITY_NAMES, EntitySet

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
}

REQUIRED_COLUMNS = {
    "surveys": {"survey_id", "survey_name"},
    "sections": {"section_id", "survey_id", "section_external_id"},
    "question_catalog": {"question_catalog_id", "question_text", "canonical_question_type"},
    "question_field_catalog": {"question_field_catalog_id", "question_catalog_id", "field_text"},
    "questions": {"question_id", "question_external_id", "survey_id", "question_catalog_id"},
    "answer_options": {"answer_option_id", "question_id", "answer_option_catalog_id"},
    "question_fields": {"question_field_id", "question_id", "question_field_catalog_id", "answer_value_type"},
    "responses": {"response_id", "response_external_id", "survey_id"},
    "response_answers": {
        "response_answer_id",
        "response_id",
        "question_id",
        "question_field_id",
        "question_catalog_id",
        "question_field_catalog_id",
        "answer_value_type",
        "answer_text",
    },
}

RELATIONSHIPS = (
    ("sections", "survey_id", "surveys", "survey_id"),
    ("questions", "survey_id", "surveys", "survey_id"),
    ("questions", "section_id", "sections", "section_id"),
    ("questions", "question_catalog_id", "question_catalog", "question_catalog_id"),
    ("question_fields", "question_id", "questions", "question_id"),
    ("question_fields", "question_field_catalog_id", "question_field_catalog", "question_field_catalog_id"),
    ("question_fields", "question_catalog_id", "question_catalog", "question_catalog_id"),
    ("answer_options", "question_id", "questions", "question_id"),
    ("answer_options", "answer_option_catalog_id", "answer_options", "answer_option_catalog_id"),
    ("responses", "survey_id", "surveys", "survey_id"),
    ("response_answers", "response_id", "responses", "response_id"),
    ("response_answers", "question_id", "questions", "question_id"),
    ("response_answers", "question_field_id", "question_fields", "question_field_id"),
    ("response_answers", "question_catalog_id", "question_catalog", "question_catalog_id"),
    ("response_answers", "question_field_catalog_id", "question_field_catalog", "question_field_catalog_id"),
    ("response_answers", "answer_option_id", "answer_options", "answer_option_id"),
    ("response_answers", "answer_option_catalog_id", "answer_options", "answer_option_catalog_id"),
)


def validate_entity_set(entities: EntitySet, *, strict: bool = False) -> None:
    if strict:
        missing = [name for name in ENTITY_NAMES if name not in entities._present_entities]
        if missing:
            raise ValueError(f"Incomplete strict entity contract: {', '.join(missing)}")
    for name, key in PRIMARY_KEYS.items():
        rows = getattr(entities, name)
        seen: set[str] = set()
        for row in rows:
            if strict:
                missing_columns = REQUIRED_COLUMNS[name] - row.keys()
                if missing_columns:
                    raise ValueError(f"{name} row is missing required columns: {', '.join(sorted(missing_columns))}")
            value = str(row.get(key) or "")
            if not value:
                raise ValueError(f"{name} row is missing {key}")
            if value in seen:
                raise ValueError(f"{name} contains duplicate {key} {value}")
            seen.add(value)
    for child, foreign_key, parent, parent_key in RELATIONSHIPS:
        child_rows = getattr(entities, child)
        parent_rows = getattr(entities, parent)
        if not child_rows or not parent_rows:
            continue
        parent_ids = {str(row[parent_key]) for row in parent_rows}
        for row in child_rows:
            value = row.get(foreign_key)
            if value is not None and str(value) not in parent_ids:
                raise ValueError(f"{child} {foreign_key} {value} has no parent in {parent}.{parent_key}")


def merge_entity_sets(entity_sets: list[EntitySet]) -> EntitySet:
    """Combine surveys while de-duplicating the two canonical catalogs."""
    result = EntitySet()
    if entity_sets:
        result._present_entities = set.intersection(*(item._present_entities for item in entity_sets))
    survey_ids = [str(survey["survey_id"]) for item in entity_sets for survey in item.surveys]
    duplicates = {survey_id for survey_id in survey_ids if survey_ids.count(survey_id) > 1}
    if duplicates:
        raise ValueError(f"Duplicate survey_id values: {', '.join(sorted(duplicates))}")
    for name in ENTITY_NAMES:
        rows = [row for item in entity_sets for row in getattr(item, name)]
        if name in {"question_catalog", "question_field_catalog"}:
            id_key = f"{name}_id"
            unique: dict[str, dict[str, object]] = {}
            for row in rows:
                identifier = str(row[id_key])
                if identifier in unique and unique[identifier] != row:
                    raise ValueError(f"{name} catalog collision for {identifier}")
                unique[identifier] = row
            rows = list(unique.values())
        setattr(result, name, rows)
    return result
