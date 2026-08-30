from __future__ import annotations

from .entities import ENTITY_NAMES, EntitySet


def merge_entity_sets(entity_sets: list[EntitySet]) -> EntitySet:
    """Combine surveys while de-duplicating the two canonical catalogs."""
    result = EntitySet()
    survey_ids = [str(survey["survey_id"]) for item in entity_sets for survey in item.surveys]
    duplicates = {survey_id for survey_id in survey_ids if survey_ids.count(survey_id) > 1}
    if duplicates:
        raise ValueError(f"Duplicate survey_id values: {', '.join(sorted(duplicates))}")
    for name in ENTITY_NAMES:
        rows = [row for item in entity_sets for row in getattr(item, name)]
        if name in {"question_catalog", "question_field_catalog"}:
            id_key = f"{name}_id"
            rows = list({str(row[id_key]): row for row in rows}.values())
        setattr(result, name, rows)
    return result
