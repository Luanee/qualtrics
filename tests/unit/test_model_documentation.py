from pathlib import Path

from qualtrics.models.entities import ENTITY_NAMES


def test_entity_documentation_names_every_normalized_entity_and_semantic_table() -> None:
    root = Path(__file__).parents[2]
    contract = (root / "docs/entity-model.md").read_text(encoding="utf-8")
    dbml = (root / "docs/entity-model.dbml").read_text(encoding="utf-8")
    for name in ENTITY_NAMES:
        assert name in contract
        assert f"Table {name}" in dbml
    for name in (
        "fact_responses",
        "fact_response_answers",
        "dim_surveys",
        "dim_question_fields",
        "dim_answer_options",
    ):
        assert name in contract
    assert "Question Response Rate" in contract
