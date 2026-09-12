from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest

from qualtrics import EntitySet, build_semantic_model, load_entities, parse_survey, write_entities, write_semantic_model
from qualtrics._common.models.semantic import SemanticModel

OPTION_COLUMNS = ("source_choice_id", "choice_value", "recode_value", "value", "variable_name")


@pytest.fixture
def provenance_entities(tmp_path: Path) -> EntitySet:
    source = tmp_path / "source.csv"
    definition = tmp_path / "definition.qsf"
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1", "QID2"],
            ["Response ID", "Choice", "Comment"],
            ["{}", '{"ImportId":"QID1"}', '{"ImportId":"QID2"}'],
            ["R1", "02", '  café, "literal"\nnext line  '],
            ["R2", "0", "unmatched"],
        ])
    definition.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_PROVENANCE", "SurveyName": "Provenance"},
            "SurveyElements": [
                {
                    "Element": "SQ",
                    "PrimaryAttribute": "QID1",
                    "Payload": {
                        "QuestionID": "QID1",
                        "QuestionText": "Choice",
                        "QuestionType": "MC",
                        "Selector": "SAVR",
                        "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}, "3": {"Display": "Maybe"}},
                        "RecodeValues": {"1": "02", "2": 0},
                        "VariableNaming": {"1": "Y"},
                    },
                },
                {
                    "Element": "SQ",
                    "PrimaryAttribute": "QID2",
                    "Payload": {
                        "QuestionID": "QID2",
                        "QuestionText": "Comment",
                        "QuestionType": "TE",
                        "Selector": "SL",
                    },
                },
            ],
        }),
        encoding="utf-8",
    )
    return parse_survey(source, definition)


@pytest.mark.parametrize("format", ["csv", "parquet"])
def test_empty_entity_exports_keep_queryable_provenance_columns(tmp_path: Path, format: str) -> None:
    if format == "parquet":
        pytest.importorskip("pyarrow")
    write_entities(EntitySet(), tmp_path, format)
    if format == "parquet":
        pq = pytest.importorskip("pyarrow.parquet")
        options = pq.read_table(tmp_path / "answer_options.parquet", columns=list(OPTION_COLUMNS))
        answers = pq.read_table(tmp_path / "response_answers.parquet", columns=["raw_value"])
        assert options.num_rows == answers.num_rows == 0
        assert all(str(field.type) == "string" for field in options.schema)
        assert str(answers.schema.field("raw_value").type) == "string"
    else:
        with (tmp_path / "answer_options.csv").open(newline="") as handle:
            assert set(OPTION_COLUMNS) <= set(next(csv.reader(handle)))
        with (tmp_path / "response_answers.csv").open(newline="") as handle:
            assert "raw_value" in next(csv.reader(handle))


@pytest.mark.parametrize("format", ["sqlite", "parquet", "csv"])
def test_empty_semantic_exports_keep_queryable_provenance_columns(tmp_path: Path, format: str) -> None:
    if format == "parquet":
        pytest.importorskip("pyarrow")
    write_semantic_model(SemanticModel(), tmp_path, format)
    if format == "sqlite":
        with sqlite3.connect(tmp_path / "semantic_model.sqlite") as connection:
            assert (
                connection.execute(
                    "SELECT source_choice_id, choice_value, recode_value, value FROM dim_answer_options"
                ).fetchall()
                == []
            )
            assert connection.execute("SELECT raw_value FROM fact_response_answers").fetchall() == []
    elif format == "parquet":
        pq = pytest.importorskip("pyarrow.parquet")
        assert pq.read_table(tmp_path / "dim_answer_options.parquet", columns=list(OPTION_COLUMNS)).num_rows == 0
        assert pq.read_table(tmp_path / "fact_response_answers.parquet", columns=["raw_value"]).num_rows == 0
    else:
        with (tmp_path / "dim_answer_options.csv").open(newline="") as handle:
            assert set(OPTION_COLUMNS) <= set(next(csv.reader(handle)))
        with (tmp_path / "fact_response_answers.csv").open(newline="") as handle:
            assert "raw_value" in next(csv.reader(handle))


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_provenance_round_trip_preserves_codes_labels_raw_text_and_links(
    provenance_entities: EntitySet,
    tmp_path: Path,
    format: str,
) -> None:
    if format == "parquet":
        pytest.importorskip("pyarrow")
    destination = tmp_path / format
    write_entities(provenance_entities, destination, format)
    loaded = load_entities(destination)
    options = {row["source_choice_id"]: row for row in loaded.answer_options}
    assert options["1"]["variable_name"] == "Y"
    assert options["2"]["variable_name"] is None
    assert [
        (options[key]["choice_value"], options[key]["recode_value"], options[key]["value"]) for key in ("1", "2", "3")
    ] == [
        ("Yes", "02", "02"),
        ("No", "0", "0"),
        ("Maybe", None, "Maybe"),
    ]
    answers = {(row["response_external_id"], row["question_external_id"]): row for row in loaded.response_answers}
    assert answers["R1", "QID1"]["raw_value"] == "02"
    assert answers["R1", "QID1"]["answer_option_id"] == options["1"]["answer_option_id"]
    assert answers["R2", "QID1"]["raw_value"] == "0"
    assert answers["R2", "QID1"]["answer_option_id"] == options["2"]["answer_option_id"]
    assert answers["R1", "QID2"]["raw_value"] == '  café, "literal"\nnext line  '
    assert answers["R1", "QID2"]["answer_option_id"] is None
    model = build_semantic_model(loaded)
    assert model.fact_response_answers == loaded.response_answers
    assert model.dim_answer_options == loaded.answer_options


def test_semantic_sqlite_and_parquet_preserve_provenance(
    provenance_entities: EntitySet,
    tmp_path: Path,
) -> None:
    pq = pytest.importorskip("pyarrow.parquet")
    model = build_semantic_model(provenance_entities)
    write_semantic_model(model, tmp_path / "sqlite", "sqlite")
    write_semantic_model(model, tmp_path / "parquet", "parquet")
    with sqlite3.connect(tmp_path / "sqlite" / "semantic_model.sqlite") as connection:
        assert connection.execute(
            "SELECT source_choice_id, recode_value, value FROM dim_answer_options ORDER BY source_choice_id"
        ).fetchall() == [
            ("1", "02", "02"),
            ("2", "0", "0"),
            ("3", None, "Maybe"),
        ]
        connection.row_factory = sqlite3.Row
        for name in ("dim_answer_options", "fact_response_answers"):
            rows = [dict(row) for row in connection.execute(f"SELECT * FROM {name}")]
            assert rows == pq.read_table(tmp_path / "parquet" / f"{name}.parquet").to_pylist()


def test_missing_display_and_recode_survive_csv_load_and_semantic_export(
    provenance_entities: EntitySet,
    tmp_path: Path,
) -> None:
    definition_path = tmp_path / "definition.qsf"
    definition = json.loads(definition_path.read_text())
    question = definition["SurveyElements"][0]["Payload"]
    question["Choices"]["1"] = {}
    question["RecodeValues"].pop("1")
    question["VariableNaming"].pop("1")
    definition_path.write_text(json.dumps(definition))
    source_path = tmp_path / "source.csv"
    with source_path.open(newline="") as handle:
        source_rows = list(csv.reader(handle))
    source_rows[3][1] = "1"
    with source_path.open("w", newline="") as handle:
        csv.writer(handle).writerows(source_rows)
    entities = parse_survey(source_path, definition_path)
    empty_option = next(option for option in entities.answer_options if option["source_choice_id"] == "1")
    assert (empty_option["answer_text"], empty_option["choice_value"], empty_option["value"]) == ("", "", "")

    write_entities(entities, tmp_path / "empty-label", "csv")
    loaded = load_entities(tmp_path / "empty-label")
    restored = next(option for option in loaded.answer_options if option["source_choice_id"] == "1")
    assert (restored["answer_text"], restored["choice_value"], restored["value"]) == ("", "", "")
    assert restored["recode_value"] is None
    assert restored["variable_name"] is None
    answer = next(
        row
        for row in loaded.response_answers
        if row["response_external_id"] == "R1" and row["question_external_id"] == "QID1"
    )
    assert answer["answer_option_id"] == restored["answer_option_id"]
    model = build_semantic_model(loaded)
    write_semantic_model(model, tmp_path / "empty-label-sqlite", "sqlite")
    with sqlite3.connect(tmp_path / "empty-label-sqlite" / "semantic_model.sqlite") as connection:
        assert connection.execute(
            "SELECT answer_text, choice_value, value FROM dim_answer_options WHERE source_choice_id = '1'"
        ).fetchone() == ("", "", "")


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_legacy_exports_do_not_invent_explicit_recodes(
    provenance_entities: EntitySet,
    tmp_path: Path,
    format: str,
) -> None:
    if format == "parquet":
        pytest.importorskip("pyarrow")
    for row in provenance_entities.answer_options:
        for key in OPTION_COLUMNS:
            row.pop(key, None)
    for row in provenance_entities.response_answers:
        row.pop("raw_value", None)
    destination = tmp_path / "legacy"
    write_entities(provenance_entities, destination, format)
    loaded = load_entities(destination)
    assert all(row.get(key) is None for row in loaded.answer_options for key in OPTION_COLUMNS)
    assert [row["answer_code"] for row in loaded.answer_options] == ["02", "0", "3"]
    assert [row["answer_text"] for row in loaded.response_answers] == [
        "02",
        '  café, "literal"\nnext line  ',
        "0",
        "unmatched",
    ]
    assert len(build_semantic_model(loaded).fact_response_answers) == 4
