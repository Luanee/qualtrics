import re
from pathlib import Path

import pytest

from qualtrics._common.models.entities import ENTITY_NAMES
from qualtrics._common.serialization.io import ENTITY_COLUMNS
from qualtrics._common.serialization.semantic import SEMANTIC_COLUMNS


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
        "dim_questions",
        "dim_answer_options",
    ):
        assert name in contract
    assert "Question Response Rate" in contract


@pytest.mark.parametrize(
    ("filename", "fixed_columns"),
    [("entity-model.dbml", ENTITY_COLUMNS), ("power-bi-model.dbml", SEMANTIC_COLUMNS)],
)
def test_dbml_covers_every_fixed_export_column(filename: str, fixed_columns: dict[str, tuple[str, ...]]) -> None:
    source = (Path(__file__).parents[2] / "docs" / filename).read_text(encoding="utf-8")
    # These files use plain table declarations; full DBML syntax is checked with
    # the official parser when changing the diagrams, without a test dependency.
    bodies = dict(re.findall(r"^Table (\w+)(?: \[[^\n]*\])? \{\n(.*?)^\}", source, re.MULTILINE | re.DOTALL))
    assert set(bodies) == set(fixed_columns)
    missing = {
        table: sorted(
            set(columns)
            - set(re.findall(r"^  (\w+) (?:varchar|text|integer|double|boolean)\b", bodies[table], re.MULTILINE))
        )
        for table, columns in fixed_columns.items()
    }
    assert not any(missing.values()), missing


def test_power_bi_dbml_has_only_the_four_recommended_relationships() -> None:
    source = (Path(__file__).parents[2] / "docs/power-bi-model.dbml").read_text(encoding="utf-8")
    references = re.findall(r"^Ref(?: \w+)?: (\w+\.\w+) (<|>|-|<>) (\w+\.\w+)$", source, re.MULTILINE)
    assert len(references) == len(re.findall(r"^Ref\b", source, re.MULTILINE)) == 4
    assert not re.search(r"\[[^\]]*\bref\s*:", source)
    assert set(references) == {
        ("dim_surveys.survey_id", "<", "fact_responses.survey_id"),
        ("fact_responses.response_id", "<", "fact_response_answers.response_id"),
        ("dim_questions.question_field_id", "<", "fact_response_answers.question_field_id"),
        ("dim_answer_options.answer_option_id", "<", "fact_response_answers.answer_option_id"),
    }
    primary_keys = re.findall(r"^  (\w+) varchar \[pk\]$", source, re.MULTILINE)
    assert sorted(primary_keys) == sorted([
        "survey_id",
        "response_id",
        "response_answer_id",
        "question_field_id",
        "answer_option_id",
    ])
