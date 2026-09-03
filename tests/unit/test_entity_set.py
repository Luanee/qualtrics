import pytest

from qualtrics.models.entities import EntitySet
from qualtrics.models.entity_set import merge_entity_sets, validate_entity_set


def test_validation_rejects_duplicate_primary_ids() -> None:
    entities = EntitySet(surveys=[{"survey_id": "SV_1"}, {"survey_id": "SV_1"}])
    with pytest.raises(ValueError, match="surveys.*SV_1"):
        validate_entity_set(entities)


def test_validation_rejects_missing_parent_when_both_tables_are_present() -> None:
    entities = EntitySet(
        surveys=[{"survey_id": "SV_1"}],
        responses=[{"response_id": "response-1", "response_external_id": "R_1", "survey_id": "missing"}],
    )
    with pytest.raises(ValueError, match="responses.*survey_id.*missing"):
        validate_entity_set(entities)


def test_strict_validation_requires_all_entities() -> None:
    with pytest.raises(ValueError, match="strict entity contract"):
        validate_entity_set(EntitySet(surveys=[{"survey_id": "SV_1"}]), strict=True)


def test_strict_validation_names_missing_columns() -> None:
    entities = EntitySet(surveys=[{"survey_id": "SV_1"}])
    entities._present_entities = set(entities.__dataclass_fields__) - {"_present_entities"}
    with pytest.raises(ValueError, match="surveys.*survey_name"):
        validate_entity_set(entities, strict=True)


def test_merge_rejects_catalog_payload_collision() -> None:
    first = EntitySet(question_catalog=[{"question_catalog_id": "same", "question_text": "One"}])
    second = EntitySet(question_catalog=[{"question_catalog_id": "same", "question_text": "Two"}])
    with pytest.raises(ValueError, match="catalog collision"):
        merge_entity_sets([first, second])
