"""Shared mechanics must retain the two exporters' deliberate type policies."""

import csv
import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from qualtrics import EntitySet, SemanticModel, write_entities, write_semantic_model
from qualtrics._common.serialization.io import ENTITY_COLUMNS
from qualtrics._common.serialization.semantic import SEMANTIC_COLUMNS


@pytest.mark.parametrize(
    ("writer", "collection"), [(write_entities, EntitySet()), (write_semantic_model, SemanticModel())]
)
def test_writers_reject_unknown_formats(
    tmp_path: Path, writer: Callable[..., None], collection: EntitySet | SemanticModel
) -> None:
    with pytest.raises(ValueError, match="Unsupported format: unknown"):
        writer(collection, tmp_path, "unknown")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
@pytest.mark.parametrize("empty", [False, True])
def test_exporters_keep_their_column_order_and_scalar_policies(tmp_path: Path, format: str, empty: bool) -> None:
    questions = [] if empty else [{"block_order": 2, "question_order_in_block": 3, "question_text": 'café, "A"\nB'}]
    responses = (
        []
        if empty
        else [
            {"response_id": "001", "is_finished": True, "custom": False, "answer_numeric": "002"},
            {"response_id": "002", "is_finished": "false", "custom": "false", "answer_numeric": None},
        ]
    )
    entities = EntitySet(questions=questions, responses=responses)
    model = SemanticModel(dim_questions=questions, fact_responses=responses)
    originals = deepcopy((entities, model))
    write_entities(entities, tmp_path / "entities", format)
    write_semantic_model(model, tmp_path / "semantic", format)
    assert (entities, model) == originals

    for folder, name, rows, columns in (
        ("entities", "questions", questions, ENTITY_COLUMNS["questions"]),
        ("entities", "responses", responses, ENTITY_COLUMNS["responses"]),
        ("semantic", "dim_questions", questions, SEMANTIC_COLUMNS["dim_questions"]),
        ("semantic", "fact_responses", responses, SEMANTIC_COLUMNS["fact_responses"]),
    ):
        path = tmp_path / folder / f"{name}.{format}"
        keys = list(dict.fromkeys([*columns, *(key for row in rows for key in row)]))
        if format == "json":
            assert path.read_text(encoding="utf-8") == json.dumps(rows, ensure_ascii=False, indent=2)
        elif format == "csv":
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                restored = list(reader)
                assert reader.fieldnames == keys
            assert restored == [
                {key: str(row[key]) if row.get(key) is not None else "" for key in keys} for row in rows
            ]
        else:
            import pyarrow.parquet as pq

            table = pq.read_table(path)
            assert table.schema.names == keys
            assert all(field.nullable for field in table.schema)
            assert table.num_rows == len(rows)
            if rows and name.endswith("questions"):
                expected_type = "int64" if folder == "entities" else "string"
                assert str(table.schema.field("block_order").type) == expected_type
                assert str(table.schema.field("question_order_in_block").type) == expected_type
                assert table.to_pylist()[0]["question_text"] == questions[0]["question_text"]
            if rows and name.endswith("responses"):
                assert str(table.schema.field("answer_numeric").type) == "string"
                assert [row["answer_numeric"] for row in table.to_pylist()] == ["002", None]
                # Entity normalization reconciles mixed bool/string columns;
                # semantic extra properties retain their original string case.
                assert [row["custom"] for row in table.to_pylist()] == (
                    ["False", "False"] if folder == "entities" else ["False", "false"]
                )


def test_semantic_column_discovery_avoids_repeated_linear_membership_scans(tmp_path: Path) -> None:
    comparisons = 0

    class ObservedName(str):
        __hash__ = str.__hash__

        def __eq__(self, other: object) -> bool:
            nonlocal comparisons
            comparisons += 1
            return super().__eq__(other)

    names = [ObservedName(f"property_{index}") for index in range(30)]
    rows: list[dict[str, Any]] = [{name: "001" for name in names} for _ in range(100)]
    model = SemanticModel(fact_responses=rows)
    write_semantic_model(model, tmp_path, "csv")
    assert comparisons < 10_000
    with (tmp_path / "fact_responses.csv").open(newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == [*SEMANTIC_COLUMNS["fact_responses"], *names]
        assert len(list(reader)) == 100
