import sqlite3
from pathlib import Path

import pytest

from qualtrics._common.models.semantic import SemanticModel
from qualtrics._common.serialization.semantic import write_semantic_model


def test_sqlite_empty_model_has_all_tables_with_useful_types(tmp_path: Path) -> None:
    write_semantic_model(SemanticModel(), tmp_path, "sqlite")

    with sqlite3.connect(tmp_path / "semantic_model.sqlite") as connection:
        assert {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")} == {
            "fact_responses",
            "fact_response_answers",
            "dim_surveys",
            "dim_questions",
            "dim_answer_options",
        }
        schema = {row[1]: row[2] for row in connection.execute("PRAGMA table_info(fact_response_answers)")}
        assert schema["response_id"] == "TEXT"
        assert schema["answer_numeric"] == "REAL"
        assert schema["answer_boolean"] == "INTEGER"
        assert schema["is_selected"] == "INTEGER"
        assert connection.execute("SELECT count(*) FROM fact_response_answers").fetchone() == (0,)
        assert (
            dict((row[1], row[2]) for row in connection.execute("PRAGMA table_info(dim_questions)"))[
                "source_column_index"
            ]
            == "INTEGER"
        )


def test_sqlite_preserves_values_and_matches_parquet(tmp_path: Path) -> None:
    import pyarrow.parquet as pq

    model = SemanticModel(
        dim_surveys=[{"survey_id": "001", "survey_name": 'R&D "Survey"; DROP TABLE dim_surveys; --'}],
        fact_response_answers=[
            {
                "response_answer_id": "0003",
                "response_id": "0002",
                "survey_id": "001",
                "answer_text": "O'Brien\nこんにちは",
                "answer_numeric": 2.75,
                "answer_boolean": False,
                "is_selected": True,
                'extra "column"': "quoted value",
            },
            {"response_answer_id": "0004", "response_id": "0002", "survey_id": "001", "answer_numeric": None},
        ],
        dim_questions=[{"question_field_id": "0005", "source_column_index": 4, "is_text_field": False}],
    )
    write_semantic_model(model, tmp_path / "sqlite", "sqlite")
    write_semantic_model(model, tmp_path / "parquet", "parquet")

    with sqlite3.connect(tmp_path / "sqlite" / "semantic_model.sqlite") as connection:
        connection.row_factory = sqlite3.Row
        answers = [dict(row) for row in connection.execute("SELECT * FROM fact_response_answers")]
        assert answers == pq.read_table(tmp_path / "parquet" / "fact_response_answers.parquet").to_pylist()
        assert answers[0]["response_id"] == "0002"
        assert answers[0]["answer_numeric"] == 2.75
        assert answers[0]["answer_boolean"] == 0
        assert answers[0]["is_selected"] == 1
        assert answers[1]["answer_numeric"] is None
        assert answers[1]["answer_text"] is None
        assert answers[0]['extra "column"'] == "quoted value"
        assert (
            connection.execute("SELECT survey_name FROM dim_surveys").fetchone()[0]
            == model.dim_surveys[0]["survey_name"]
        )
        assert [dict(row) for row in connection.execute("SELECT * FROM dim_questions")] == pq.read_table(
            tmp_path / "parquet" / "dim_questions.parquet"
        ).to_pylist()


def test_sqlite_refuses_to_overwrite_existing_database(tmp_path: Path) -> None:
    database = tmp_path / "semantic_model.sqlite"
    database.write_bytes(b"existing export")

    with pytest.raises(ValueError, match="already exists"):
        write_semantic_model(SemanticModel(), tmp_path, "sqlite")

    assert database.read_bytes() == b"existing export"
    assert list(tmp_path.iterdir()) == [database]


def test_sqlite_failed_export_does_not_leave_partial_database(tmp_path: Path) -> None:
    model = SemanticModel(
        fact_responses=[{"response_id": "R_1"}],
        fact_response_answers=[{"answer_numeric": [1, 2, 3]}],
    )

    with pytest.raises(sqlite3.ProgrammingError, match="not supported"):
        write_semantic_model(model, tmp_path, "sqlite")

    assert list(tmp_path.iterdir()) == []
