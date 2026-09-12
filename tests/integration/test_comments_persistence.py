import copy
import csv
import json
import sqlite3
from pathlib import Path

import pytest

from qualtrics import parse_survey
from qualtrics._common.models.entities import EntitySet
from qualtrics._common.models.entity_set import merge_entity_sets, validate_entity_set
from qualtrics._common.models.semantic import SemanticModel, build_semantic_model
from qualtrics._common.serialization.io import load_entities, write_entities
from qualtrics._common.serialization.semantic import write_semantic_model

COMMENT_COLUMNS = (
    "response_answer_id",
    "response_id",
    "survey_id",
    "question_id",
    "question_field_id",
    "answer_text",
    "raw_value",
    "user_language",
)
CORE_NAMES = (
    "surveys",
    "sections",
    "question_catalog",
    "question_field_catalog",
    "questions",
    "answer_options",
    "question_fields",
    "responses",
    "response_answers",
)


@pytest.fixture
def comment_entities(tmp_path: Path) -> EntitySet:
    source = tmp_path / "comments.csv"
    definition = tmp_path / "comments.qsf"
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1", "QID2", "QID3"],
            ["Response", "Language", "Identifier", "Feedback", "Choice"],
            [json.dumps({"ImportId": name}) for name in ["responseId", "userLanguage", "QID1", "QID2", "QID3"]],
            ["R1", "pt-BR", "00123", " Same <tag>\ntext ", "1"],
            ["R2", "", "00123", " Same <tag>\ntext ", "1"],
            ["R3", "EN", " \t", "", "2"],
        ])
    definition.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_COMMENTS", "SurveyName": "Comments", "SurveyLanguage": "DE"},
            "SurveyElements": [
                {"Element": "SQ", "PrimaryAttribute": qid, "Payload": payload}
                for qid, payload in {
                    "QID1": {
                        "QuestionID": "QID1",
                        "QuestionText": "Identifier",
                        "QuestionType": "TE",
                        "Selector": "SL",
                    },
                    "QID2": {"QuestionID": "QID2", "QuestionText": "Feedback", "QuestionType": "TE", "Selector": "ML"},
                    "QID3": {
                        "QuestionID": "QID3",
                        "QuestionText": "Choice",
                        "QuestionType": "MC",
                        "Selector": "SAVR",
                        "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                    },
                }.items()
            ],
        }),
        encoding="utf-8",
    )
    entities = parse_survey(source, definition)
    for answer in entities.response_answers:
        answer["user_language"] = "STALE_ANSWER_LANGUAGE"
        if (answer["response_external_id"], answer["question_external_id"]) == ("R2", "QID1"):
            answer.pop("raw_value")
    return entities


def _expected_comments(entities: EntitySet) -> list[dict[str, object]]:
    rows = []
    for answer in entities.response_answers:
        if answer["question_external_id"] not in {"QID1", "QID2"} or answer["response_external_id"] == "R3":
            continue
        rows.append({
            **{column: answer[column] for column in COMMENT_COLUMNS[:5]},
            "answer_text": "00123" if answer["question_external_id"] == "QID1" else " Same <tag>\ntext ",
            "raw_value": None
            if (answer["response_external_id"], answer["question_external_id"]) == ("R2", "QID1")
            else answer["raw_value"],
            "user_language": "pt-BR" if answer["response_external_id"] == "R1" else None,
        })
    assert len(rows) == 4
    return rows


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_entity_roundtrip_rebuilds_comments_without_changing_core_rows(
    tmp_path: Path,
    comment_entities: EntitySet,
    format: str,
) -> None:
    entities = comment_entities
    entities.comments = [{"answer_text": "stale cache"}]
    original = {name: copy.deepcopy(getattr(entities, name)) for name in CORE_NAMES}
    expected = _expected_comments(entities)

    write_entities(entities, tmp_path / format, format)

    assert (tmp_path / format / f"comments.{format}").is_file()
    loaded = load_entities(tmp_path / format)
    assert loaded.comments == expected
    assert len({row["response_answer_id"] for row in loaded.comments}) == 4
    assert {name: getattr(entities, name) for name in CORE_NAMES} == original


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_legacy_nine_table_folder_reconstructs_comments(
    tmp_path: Path,
    comment_entities: EntitySet,
    format: str,
) -> None:
    entities = comment_entities
    for field in entities.question_fields:
        field.pop("is_comment_field", None)
    write_entities(entities, tmp_path / format, format)
    (tmp_path / format / f"comments.{format}").unlink(missing_ok=True)

    loaded = load_entities(tmp_path / format)

    assert getattr(loaded, "comments", None) == _expected_comments(entities)
    validate_entity_set(loaded, strict=True)


@pytest.mark.parametrize("corruption", ["language", "lineage", "text", "raw", "missing", "duplicate", "extra_column"])
def test_load_rejects_explicit_comments_that_disagree_with_core_tables(
    tmp_path: Path,
    comment_entities: EntitySet,
    corruption: str,
) -> None:
    write_entities(comment_entities, tmp_path / "entities")
    rows = _expected_comments(comment_entities)
    if corruption == "language":
        rows[0]["user_language"] = "STALE_ANSWER_LANGUAGE"
    elif corruption == "lineage":
        rows[0]["question_field_id"] = "missing-field"
    elif corruption == "text":
        rows[0]["answer_text"] = "changed"
    elif corruption == "raw":
        rows[0]["raw_value"] = "changed"
    elif corruption == "missing":
        rows.pop()
    elif corruption == "duplicate":
        rows.append(dict(rows[0]))
    else:
        rows[0]["unknown"] = "value"
    (tmp_path / "entities/comments.json").write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(ValueError, match="comments"):
        load_entities(tmp_path / "entities")


def test_load_accepts_reordered_comments_and_restores_answer_order(tmp_path: Path, comment_entities: EntitySet) -> None:
    write_entities(comment_entities, tmp_path / "entities")
    expected = _expected_comments(comment_entities)
    (tmp_path / "entities/comments.json").write_text(json.dumps(list(reversed(expected))), encoding="utf-8")
    loaded = load_entities(tmp_path / "entities")
    assert getattr(loaded, "comments", None) == expected


def test_merge_rebuilds_comments_from_each_survey_without_text_deduplication(
    tmp_path: Path,
    comment_entities: EntitySet,
) -> None:
    entities = comment_entities
    entities.comments = [{"answer_text": "stale cache"}]
    second = parse_survey(tmp_path / "comments.csv", tmp_path / "comments.qsf", survey_id="SV_SECOND")
    for answer in second.response_answers:
        if (answer["response_external_id"], answer["question_external_id"]) == ("R2", "QID1"):
            answer.pop("raw_value")
    original = copy.deepcopy([entities, second])

    merged = merge_entity_sets([entities, second])

    assert getattr(merged, "comments", None) == _expected_comments(entities) + _expected_comments(second)
    assert len({row["response_answer_id"] for row in merged.comments}) == 8
    assert [entities, second] == original
    assert merge_entity_sets([merged]).comments == merged.comments


def test_semantic_build_reconstructs_default_comments_on_manual_legacy_entities(comment_entities: EntitySet) -> None:
    values = {name: copy.deepcopy(getattr(comment_entities, name)) for name in CORE_NAMES}
    entities = EntitySet(**values)
    entities._present_entities = set(CORE_NAMES)
    validate_entity_set(entities, strict=True)

    model = build_semantic_model(entities)

    assert getattr(model, "fact_comments", None) == _expected_comments(entities)
    assert model.fact_response_answers == entities.response_answers
    assert model.fact_responses == entities.responses


@pytest.mark.parametrize("format", ["json", "csv", "parquet", "sqlite"])
def test_semantic_writes_rebuild_comments_and_preserve_text_types(
    tmp_path: Path,
    comment_entities: EntitySet,
    format: str,
) -> None:
    model = build_semantic_model(comment_entities)
    model.fact_comments = [{"answer_text": "stale cache"}]
    write_semantic_model(model, tmp_path / format, format)
    rows, columns = _read_comments(tmp_path / format, "fact_comments", format)
    assert columns == list(COMMENT_COLUMNS)
    assert rows == _expected_comments(comment_entities)


def _read_comments(folder: Path, table: str, format: str) -> tuple[list[dict[str, object]], list[str]]:
    if format == "sqlite":
        with sqlite3.connect(folder / "semantic_model.sqlite") as connection:
            connection.row_factory = sqlite3.Row
            schema = connection.execute(f"PRAGMA table_info({table})").fetchall()
            assert {row[2] for row in schema} == {"TEXT"}
            return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")], [row[1] for row in schema]
    path = folder / f"{table}.{format}"
    assert path.is_file()
    if format == "json":
        rows = json.loads(path.read_text(encoding="utf-8"))
        return rows, list(rows[0]) if rows else list(COMMENT_COLUMNS)
    if format == "csv":
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [{key: value or None for key, value in row.items()} for row in reader], list(reader.fieldnames or [])
    import pyarrow as pa
    import pyarrow.parquet as pq

    table_data = pq.read_table(path)
    assert all(field.type == pa.string() for field in table_data.schema)
    return table_data.to_pylist(), table_data.schema.names


@pytest.mark.parametrize("format", ["json", "csv", "parquet", "sqlite"])
def test_empty_comment_exports_keep_fixed_schema(tmp_path: Path, format: str) -> None:
    write_semantic_model(SemanticModel(), tmp_path / "semantic", format)
    rows, columns = _read_comments(tmp_path / "semantic", "fact_comments", format)
    assert rows == []
    assert columns == list(COMMENT_COLUMNS)
    if format != "sqlite":
        write_entities(EntitySet(), tmp_path / "entities", format)
        rows, columns = _read_comments(tmp_path / "entities", "comments", format)
        assert rows == []
        assert columns == list(COMMENT_COLUMNS)


@pytest.mark.parametrize("format", ["csv", "parquet"])
def test_comment_eligibility_boolean_survives_roundtrip(
    tmp_path: Path, comment_entities: EntitySet, format: str
) -> None:
    for field in comment_entities.question_fields:
        field["is_comment_field"] = {"QID1": False, "QID2": True, "QID3": None}[field["question_external_id"]]
    write_entities(comment_entities, tmp_path / "entities", format)
    loaded = load_entities(tmp_path / "entities")
    assert {field["question_external_id"]: field["is_comment_field"] for field in loaded.question_fields} == {
        "QID1": False,
        "QID2": True,
        "QID3": None,
    }
    model = build_semantic_model(loaded)
    assert len(model.fact_comments) == 2
    assert all(row["answer_text"] == " Same <tag>\ntext " for row in model.fact_comments)


def test_semantic_writer_does_not_borrow_text_type_from_a_sibling_field(tmp_path: Path) -> None:
    model = SemanticModel(
        fact_responses=[{"response_id": "response", "survey_id": "survey", "user_language": "EN"}],
        dim_questions=[
            {
                "survey_id": "survey",
                "question_id": "question",
                "question_field_id": "choice",
                "question_type": "MC",
                "selector": "SAVR",
            },
            {
                "survey_id": "survey",
                "question_id": "question",
                "question_field_id": "other",
                "question_type": "MC",
                "selector": "SAVR",
                "answer_value_type": "text",
            },
        ],
        fact_response_answers=[
            {
                "response_answer_id": "choice-answer",
                "response_id": "response",
                "survey_id": "survey",
                "question_id": "question",
                "question_field_id": "choice",
                "answer_text": "Yes",
            },
            {
                "response_answer_id": "other-answer",
                "response_id": "response",
                "survey_id": "survey",
                "question_id": "question",
                "question_field_id": "other",
                "answer_text": "Explanation",
            },
        ],
    )
    write_semantic_model(model, tmp_path, "json")
    rows = json.loads((tmp_path / "fact_comments.json").read_text(encoding="utf-8"))
    assert [(row["response_answer_id"], row["answer_text"]) for row in rows] == [("other-answer", "Explanation")]
