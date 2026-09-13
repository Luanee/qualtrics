import pytest

from qualtrics._common.models.identity import entity_id, semantic_id


def test_entity_id_is_domain_scoped_and_length_delimited() -> None:
    assert entity_id("question", "ab", "c") != entity_id("question", "a", "bc")
    assert entity_id("question", "SV_1", "QID1") != entity_id("response", "SV_1", "QID1")
    assert entity_id("question", "SV_1", "QID1") == entity_id("question", "SV_1", "QID1")


def test_semantic_id_canonicalizes_mapping_order_and_text() -> None:
    first = {"text": "  Hello&nbsp; WORLD ", "choices": ["B", "a"]}
    second = {"choices": ["B", "a"], "text": "Hello world"}
    assert semantic_id("question", first) == semantic_id("question", second)


def test_semantic_id_preserves_list_multiplicity() -> None:
    assert semantic_id("question", ["same"]) != semantic_id("question", ["same", "same"])


@pytest.mark.parametrize(
    "change",
    [
        {"type": "matrix"},
        {"role": "metadata"},
        {"answers": ["Bad"]},
        {"structure": {"fields": [{"text": "visit", "role": "answer", "value_type": "number"}]}},
    ],
)
def test_question_catalog_identity_includes_complete_definition(change: dict) -> None:
    content = {
        "text": "visit",
        "type": "text_entry",
        "role": "response",
        "answers": ["Good"],
        "structure": {"fields": [{"text": "visit", "role": "answer", "value_type": "text"}]},
    }
    assert semantic_id("question", content) != semantic_id("question", {**content, **change})


@pytest.mark.parametrize("change", [{"question": "other"}, {"role": "metadata"}, {"value_type": "number"}])
def test_field_catalog_identity_includes_parent_and_type(change: dict) -> None:
    content = {"question": "parent", "text": "visit", "role": "answer", "value_type": "text"}
    assert semantic_id("question-field", content) != semantic_id("question-field", {**content, **change})
