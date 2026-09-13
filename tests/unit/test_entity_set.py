import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict

import pytest

from qualtrics._common.models.entities import EntitySet
from qualtrics._common.models.entity_set import merge_entity_sets, validate_entity_set


def _catalog_entities(name: str, row: Mapping[str, object]) -> EntitySet:
    if name == "question_catalog":
        return EntitySet(question_catalog=[dict(row)])
    return EntitySet(question_field_catalog=[dict(row)])


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


def test_validation_rejects_child_rows_when_parent_table_is_empty() -> None:
    entities = EntitySet(responses=[{"response_id": "R1", "survey_id": "SV1"}])
    with pytest.raises(ValueError, match="responses.*survey_id.*SV1"):
        validate_entity_set(entities)


def test_merge_rejects_catalog_payload_collision() -> None:
    first = EntitySet(question_catalog=[{"question_catalog_id": "same", "question_text": "One"}])
    second = EntitySet(question_catalog=[{"question_catalog_id": "same", "question_text": "Two"}])
    with pytest.raises(ValueError, match="catalog collision"):
        merge_entity_sets([first, second])


@pytest.mark.parametrize(
    "second_text", ["HOW WAS YOUR VISIT?", "  How   was your visit?  ", "How&nbsp;was your visit?"]
)
def test_merge_parsed_equivalent_catalogs_preserves_occurrences(catalog_survey_factory, second_text: str) -> None:
    first = catalog_survey_factory("SV_1", "How was your visit?")
    second = catalog_survey_factory("SV_2", second_text)
    snapshots = deepcopy([asdict(first), asdict(second)])

    combined = merge_entity_sets([first, second])
    validate_entity_set(combined, strict=True)

    assert combined.question_catalog == first.question_catalog
    assert combined.question_field_catalog == first.question_field_catalog
    assert combined.question_catalog[0]["question_catalog_id"] == (
        "628d7f30122a82eb8a13e4bd9a4a940d7f7bdf297c5946e2c70c7c4b3c070a00"
    )
    assert combined.question_field_catalog[0]["question_field_catalog_id"] == (
        "4ab1d139eb70de1dfae68fc4db0b976ae3dd473265516a7982339da00c889311"
    )
    for name in ("surveys", "questions", "question_fields", "responses", "response_answers", "comments"):
        assert len(getattr(combined, name)) == 2
    for name in ("questions", "question_fields", "answer_options", "response_answers", "comments"):
        assert getattr(combined, name) == getattr(first, name) + getattr(second, name)
    assert merge_entity_sets([first, second]) == combined
    reversed_result = merge_entity_sets([second, first])
    assert reversed_result.question_catalog == second.question_catalog
    assert reversed_result.question_field_catalog == second.question_field_catalog
    for name in ("questions", "question_fields", "response_answers", "comments"):
        assert getattr(reversed_result, name) == getattr(second, name) + getattr(first, name)
    assert [asdict(first), asdict(second)] == snapshots


@pytest.mark.parametrize(
    ("catalog", "content_key", "display_key", "content"),
    [
        (
            "question_catalog",
            "normalized_question_content",
            "question_text",
            {
                "text": "visit",
                "type": "text_entry",
                "role": "response",
                "answers": [],
                "structure": {"fields": [{"text": "visit", "value_type": "text", "role": "answer"}]},
            },
        ),
        (
            "question_field_catalog",
            "normalized_field_content",
            "field_text",
            {
                "text": "visit",
                "value_type": "text",
                "role": "answer",
            },
        ),
    ],
)
def test_merge_catalogs_compares_structured_content_independently(catalog, content_key, display_key, content) -> None:
    row = {f"{catalog}_id": "same", display_key: "Visit", content_key: json.dumps(content)}
    if catalog == "question_field_catalog":
        row["question_catalog_id"] = "parent"
    other = {**row, display_key: "VISIT", content_key: json.dumps(dict(reversed(list(content.items()))), indent=2)}
    first = _catalog_entities(catalog, row)
    second = _catalog_entities(catalog, other)
    assert getattr(merge_entity_sets([first, second]), catalog) == [row]
    assert getattr(merge_entity_sets([second, first]), catalog) == [other]


@pytest.mark.parametrize(
    ("catalog", "content_key", "content", "change"),
    [
        (
            "question_catalog",
            "normalized_question_content",
            {
                "text": "visit",
                "type": "text_entry",
                "role": "response",
                "answers": ["Good"],
                "structure": {"fields": [{"text": "visit", "role": "answer", "value_type": "text"}]},
            },
            change,
        )
        for change in [
            {"type": "matrix"},
            {"role": "metadata"},
            {"answers": ["Bad"]},
            {"structure": {"fields": []}},
        ]
    ]
    + [
        (
            "question_field_catalog",
            "normalized_field_content",
            {
                "text": "visit",
                "role": "answer",
                "value_type": "text",
            },
            change,
        )
        for change in [{"role": "metadata"}, {"value_type": "number"}]
    ],
)
def test_merge_rejects_incompatible_canonical_payloads(catalog, content_key, content, change) -> None:
    row = {f"{catalog}_id": "same", content_key: json.dumps(content)}
    if catalog == "question_field_catalog":
        row["question_catalog_id"] = "parent"
    second = {**row, content_key: json.dumps({**content, **change})}
    with pytest.raises(ValueError, match=f"{catalog} catalog collision for same"):
        merge_entity_sets([_catalog_entities(catalog, row), _catalog_entities(catalog, second)])


@pytest.mark.parametrize(
    ("catalog", "content_key", "metadata_key", "value", "other_value"),
    [
        ("question_catalog", "normalized_question_content", "canonical_question_type", "text_entry", "matrix"),
        ("question_field_catalog", "normalized_field_content", "question_catalog_id", "parent", "other-parent"),
    ],
)
def test_merge_rejects_contradictory_catalog_metadata(catalog, content_key, metadata_key, value, other_value) -> None:
    row = {f"{catalog}_id": "same", content_key: '{"text": "visit"}', metadata_key: value}
    second = {**row, metadata_key: other_value}
    with pytest.raises(ValueError, match=f"{catalog} catalog collision for same"):
        merge_entity_sets([_catalog_entities(catalog, row), _catalog_entities(catalog, second)])


@pytest.mark.parametrize(
    "catalog, content_key, display_key",
    [
        ("question_catalog", "normalized_question_content", "question_text"),
        ("question_field_catalog", "normalized_field_content", "field_text"),
    ],
)
@pytest.mark.parametrize("content", [None, "", "not JSON", "null", "[]", "{}"])
def test_merge_legacy_catalogs_requires_equal_rows(catalog, content_key, display_key, content) -> None:
    row = {f"{catalog}_id": "same", display_key: "One", content_key: content}
    if catalog == "question_field_catalog":
        row["question_catalog_id"] = "parent"
    entities = _catalog_entities(catalog, row)
    assert getattr(merge_entity_sets([entities, deepcopy(entities)]), catalog) == [row]
    second = _catalog_entities(catalog, {**row, display_key: "ONE"})
    with pytest.raises(ValueError, match="catalog collision"):
        merge_entity_sets([entities, second])
    with pytest.raises(ValueError, match="catalog collision"):
        merge_entity_sets([entities, _catalog_entities(catalog, {**row, content_key: '{"text": "one"}'})])


def test_merge_equivalent_questions_preserves_survey_option_recodes(catalog_survey_factory) -> None:
    first = catalog_survey_factory(
        "SV_1",
        "Rate your visit",
        question={
            "QuestionType": "MC",
            "Selector": "SAVR",
            "Choices": {"1": {"Display": "Good"}},
            "RecodeValues": {"1": "02"},
        },
        answer="02",
    )
    second = catalog_survey_factory(
        "SV_2",
        "RATE YOUR VISIT",
        question={
            "QuestionType": "MC",
            "Selector": "SAVR",
            "Choices": {"1": {"Display": "GOOD"}},
            "RecodeValues": {"1": "07"},
        },
        answer="07",
    )
    snapshots = deepcopy([asdict(first), asdict(second)])
    combined = merge_entity_sets([first, second])
    validate_entity_set(combined, strict=True)
    assert len(combined.question_catalog) == len(combined.question_field_catalog) == 1
    assert [option["recode_value"] for option in combined.answer_options] == ["02", "07"]
    for name in ("questions", "question_fields", "answer_options", "response_answers", "comments"):
        assert getattr(combined, name) == getattr(first, name) + getattr(second, name)
    assert [asdict(first), asdict(second)] == snapshots


@pytest.mark.parametrize("value", [1, 1.0])
def test_merge_preserves_canonical_json_value_types(value: object) -> None:
    row = {"question_catalog_id": "same", "normalized_question_content": '{"flag": true}'}
    second = {**row, "normalized_question_content": json.dumps({"flag": value})}
    with pytest.raises(ValueError, match="catalog collision"):
        merge_entity_sets([EntitySet(question_catalog=[row]), EntitySet(question_catalog=[second])])


def test_merge_field_catalog_without_parent_keeps_conservative_collision_check() -> None:
    row = {"question_field_catalog_id": "same", "field_text": "Visit", "normalized_field_content": '{"text":"visit"}'}
    with pytest.raises(ValueError, match="catalog collision"):
        merge_entity_sets([
            EntitySet(question_field_catalog=[row]),
            EntitySet(question_field_catalog=[{**row, "field_text": "VISIT"}]),
        ])
