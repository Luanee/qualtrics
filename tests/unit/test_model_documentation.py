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
        "fact_comments",
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


def test_power_bi_dbml_has_only_the_six_recommended_relationships() -> None:
    source = (Path(__file__).parents[2] / "docs/power-bi-model.dbml").read_text(encoding="utf-8")
    references = re.findall(r"^Ref(?: \w+)?: (\w+\.\w+) (<|>|-|<>) (\w+\.\w+)$", source, re.MULTILINE)
    assert len(references) == len(re.findall(r"^Ref\b", source, re.MULTILINE)) == 6
    assert not re.search(r"\[[^\]]*\bref\s*:", source)
    assert set(references) == {
        ("dim_surveys.survey_id", "<", "fact_responses.survey_id"),
        ("fact_responses.response_id", "<", "fact_response_answers.response_id"),
        ("dim_questions.question_field_id", "<", "fact_response_answers.question_field_id"),
        ("dim_answer_options.answer_option_id", "<", "fact_response_answers.answer_option_id"),
        ("fact_responses.response_id", "<", "fact_comments.response_id"),
        ("dim_questions.question_field_id", "<", "fact_comments.question_field_id"),
    }
    primary_keys = re.findall(r"^  (\w+) varchar \[pk\]$", source, re.MULTILINE)
    assert sorted(primary_keys) == sorted([
        "survey_id",
        "response_id",
        "response_answer_id",
        "response_answer_id",
        "question_field_id",
        "answer_option_id",
    ])


@pytest.mark.parametrize(
    ("filename", "table", "field_table"),
    [("entity-model.dbml", "comments", "question_fields"), ("power-bi-model.dbml", "fact_comments", "dim_questions")],
)
def test_dbml_comment_projection_preserves_answer_grain_and_nullable_metadata(
    filename: str, table: str, field_table: str
) -> None:
    source = (Path(__file__).parents[2] / "docs" / filename).read_text(encoding="utf-8")
    bodies = dict(re.findall(r"^Table (\w+)(?: \[[^\n]*\])? \{\n(.*?)^\}", source, re.MULTILINE | re.DOTALL))
    assert table in bodies
    body = bodies[table]
    assert re.findall(r"^  (\w+) (?:varchar|text)\b", body, re.MULTILINE) == [
        "response_answer_id",
        "response_id",
        "survey_id",
        "question_id",
        "question_field_id",
        "answer_text",
        "raw_value",
        "user_language",
    ]
    assert re.search(r"^  response_answer_id varchar \[pk(?:, [^\]]+)?\]$", body, re.MULTILINE)
    for column in ("raw_value", "user_language"):
        declaration = next(line for line in body.splitlines() if line.startswith(f"  {column} "))
        assert "not null" not in declaration
    eligibility = next(line for line in bodies[field_table].splitlines() if line.startswith("  is_comment_field "))
    assert "is_comment_field boolean" in eligibility
    assert "not null" not in eligibility
    if table == "comments":
        assert "ref: - response_answers.response_answer_id" in body
        assert "ref: > responses.response_id" in body
        assert "ref: > question_fields.question_field_id" in body
