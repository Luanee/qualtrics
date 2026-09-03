from qualtrics.models.identity import entity_id, semantic_id


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
