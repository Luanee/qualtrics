"""Optional prepared comment translations never replace source answers."""

from __future__ import annotations

import builtins
import csv
import hashlib
import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

import qualtrics
from qualtrics._common.models.comment_translations import source_text_hash
from qualtrics._common.models.entities import EntitySet
from qualtrics._common.models.entity_set import merge_entity_sets, validate_entity_set
from qualtrics._common.models.semantic import build_semantic_model
from qualtrics._common.serialization.io import load_entities, write_entities
from qualtrics._common.serialization.semantic import write_semantic_model
from qualtrics.cli.app import app
from qualtrics.cli.translations import _read_prepared


def _entities() -> EntitySet:
    return EntitySet(
        surveys=[{"survey_id": "s", "survey_name": "Survey"}],
        questions=[{"survey_id": "s", "question_id": "q", "question_type": "TE", "question_text": "Comment"}],
        question_fields=[{"survey_id": "s", "question_id": "q", "field_id": "f", "question_field_id": "f"}],
        responses=[{"survey_id": "s", "response_id": "r", "user_language": "DE"}],
        response_answers=[
            {
                "response_answer_id": "a",
                "survey_id": "s",
                "response_id": "r",
                "question_id": "q",
                "field_id": "f",
                "question_field_id": "f",
                "answer_text": " Grüße <tag> ",
            }
        ],
    )


def test_callback_prepares_only_requested_targets_and_preserves_source_answer() -> None:
    source = _entities()
    calls = []

    def translate(text: str, source_language: str | None, target_language: str) -> str:
        calls.append((text, source_language, target_language))
        return " Greetings "

    prepare = getattr(qualtrics, "prepare_comment_translations", lambda *_args, **_kwargs: None)
    prepared = prepare(source, ["EN", "DE"], translate)

    assert prepared is not None
    assert calls == [(" Grüße <tag> ", "DE", "EN")]
    assert source.comment_translations == []
    assert source.response_answers[0]["answer_text"] == " Grüße <tag> "
    assert prepared.comment_translations == [
        {
            "comment_translation_id": prepared.comment_translations[0]["comment_translation_id"],
            "response_answer_id": "a",
            "survey_id": "s",
            "source_language": "DE",
            "target_language": "EN",
            "source_text_hash": hashlib.sha256(" Grüße <tag> ".encode()).hexdigest(),
            "translated_text": " Greetings ",
        }
    ]


def _parsed(tmp_path: Path, survey_id: str = "SV_TRANSLATIONS") -> EntitySet:
    source = tmp_path / "comments.csv"
    definition = tmp_path / "definition.qsf"
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1"],
            ["Response", "Language", "Comment"],
            [json.dumps({"ImportId": value}) for value in ("responseId", "userLanguage", "QID1")],
            ["R1", "DE", " Grüße <tag> "],
        ])
    definition.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": survey_id, "SurveyName": "Comments", "SurveyLanguage": "DE"},
            "SurveyElements": [
                {
                    "Element": "SQ",
                    "PrimaryAttribute": "QID1",
                    "Payload": {
                        "QuestionID": "QID1",
                        "QuestionText": "Comment",
                        "QuestionType": "TE",
                        "Selector": "ML",
                    },
                }
            ],
        }),
        encoding="utf-8",
    )
    return qualtrics.parse_survey(source, definition, survey_id=survey_id)


def _prepared(tmp_path: Path, survey_id: str = "SV_TRANSLATIONS") -> EntitySet:
    return qualtrics.prepare_comment_translations(_parsed(tmp_path, survey_id), ["EN"], lambda *_args: " Greetings ")


def test_callback_refreshes_stale_rows_without_calling_for_current_targets() -> None:
    original = _entities()
    prepared = qualtrics.prepare_comment_translations(original, ["EN"], lambda *_args: "First")
    calls: list[tuple[str, str | None, str]] = []

    def translator(text: str, source_language: str | None, target_language: str) -> str:
        calls.append((text, source_language, target_language))
        return "Second"

    current = qualtrics.prepare_comment_translations(prepared, ["EN"], translator)
    assert calls == []
    assert current.comment_translations == prepared.comment_translations
    prepared.response_answers[0]["answer_text"] = "Revised"
    refreshed = qualtrics.prepare_comment_translations(prepared, ["EN"], translator)
    assert calls == [("Revised", "DE", "EN")]
    assert refreshed.comment_translations[0]["source_text_hash"] == source_text_hash("Revised")
    assert refreshed.comment_translations[0]["translated_text"] == "Second"


@pytest.mark.parametrize("targets", [[""], [" EN"], ["EN "]])
def test_callback_rejects_invalid_target_languages(targets: list[str]) -> None:
    with pytest.raises(ValueError, match="Target languages"):
        qualtrics.prepare_comment_translations(_entities(), targets, lambda *_args: "Translated")


def test_callback_handles_unknown_response_language_and_rejects_empty_output() -> None:
    entities = _entities()
    entities.responses[0]["user_language"] = None
    calls = []

    def translate(text: str, source: str | None, target: str) -> str:
        calls.append((text, source, target))
        return " "

    with pytest.raises(ValueError, match="Translator returned no text"):
        qualtrics.prepare_comment_translations(entities, ["EN"], translate)
    assert calls == [(" Grüße <tag> ", None, "EN")]
    assert entities.comment_translations == []


def test_callback_rejects_non_string_target_language() -> None:
    with pytest.raises(ValueError, match="Target languages"):
        qualtrics.prepare_comment_translations(_entities(), cast(Iterable[str], [42]), lambda *_args: "Translated")


@pytest.mark.parametrize(
    "change, message",
    [
        ({"response_answer_id": "unknown"}, "Unknown written"),
        ({"target_language": ""}, "target_language"),
        ({"translated_text": " "}, "nonblank"),
        ({"source_text_hash": "0" * 64}, "source hash"),
        ({"extra": "value"}, "exactly"),
    ],
)
def test_python_import_rejects_invalid_prepared_rows(change: dict[str, str], message: str) -> None:
    record = {
        "response_answer_id": "a",
        "target_language": "EN",
        "source_text_hash": source_text_hash(" Grüße <tag> "),
        "translated_text": "Greetings",
    }
    record.update(change)
    with pytest.raises(ValueError, match=message):
        qualtrics.import_comment_translations(_entities(), [record])


def test_python_import_rejects_duplicate_answer_and_target() -> None:
    record = {
        "response_answer_id": "a",
        "target_language": "EN",
        "source_text_hash": source_text_hash(" Grüße <tag> "),
        "translated_text": "Greetings",
    }
    with pytest.raises(ValueError, match="Duplicate translation"):
        qualtrics.import_comment_translations(_entities(), [record, dict(record)])


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_optional_translations_roundtrip_and_survive_merge(tmp_path: Path, format: str) -> None:
    first = _prepared(tmp_path)
    folder = tmp_path / format
    write_entities(first, folder, format)
    loaded = load_entities(folder)
    assert loaded.comments[0]["translated_text__EN"] == " Greetings "
    assert loaded.comments[0]["translation_source_hash__EN"] == source_text_hash(" Grüße <tag> ")
    assert loaded.comments[0]["translation_source_language__EN"] == "DE"
    validate_entity_set(loaded, strict=True)

    second = _parsed(tmp_path, "SV_SECOND")
    merged = merge_entity_sets([loaded, second])
    assert len(merged.comments) == 2
    assert merged.comments[0]["translated_text__EN"] == " Greetings "
    assert merged.comments[1]["translated_text__EN"] is None


def test_translation_validation_rejects_wrong_lineage_and_duplicate_target(tmp_path: Path) -> None:
    entities = _prepared(tmp_path)
    entities.comment_translations[0]["survey_id"] = "other"
    with pytest.raises(ValueError, match="comment_translations"):
        validate_entity_set(entities, strict=True)
    entities = _prepared(tmp_path)
    entities.comment_translations.append(dict(entities.comment_translations[0]))
    with pytest.raises(ValueError, match="comment_translations"):
        validate_entity_set(entities, strict=True)


@pytest.mark.parametrize(
    "field, bad_value, expected",
    [
        ("target_language", "", "target_language"),
        ("source_text_hash", "invalid", "source_text_hash"),
        ("translated_text", " ", "translated_text"),
        ("comment_translation_id", "wrong-id", "ID must derive"),
        ("survey_id", "other", "survey must match"),
    ],
)
def test_translation_validation_checks_each_sidecar_field(
    tmp_path: Path, field: str, bad_value: str, expected: str
) -> None:
    entities = _prepared(tmp_path)
    if field == "survey_id":
        entities.surveys.append({"survey_id": "other", "survey_name": "Other"})
    entities.comment_translations[0][field] = bad_value
    with pytest.raises(ValueError, match=expected):
        validate_entity_set(entities, strict=False)


def test_translation_validation_rejects_non_comment_and_extra_schema_column(tmp_path: Path) -> None:
    entities = _prepared(tmp_path)
    entities._present_columns["comment_translations"] = {"unexpected"}
    with pytest.raises(ValueError, match="schema must contain exactly"):
        validate_entity_set(entities, strict=False)
    entities._present_columns.pop("comment_translations")
    entities.question_fields[0]["is_comment_field"] = False
    entities.comments = []
    entities._present_entities.discard("comments")
    with pytest.raises(ValueError, match="must reference a written answer"):
        validate_entity_set(entities, strict=False)


@pytest.mark.parametrize("format", ["json", "csv", "parquet", "sqlite"])
def test_semantic_export_keeps_current_and_stale_translations_visible(tmp_path: Path, format: str) -> None:
    entities = _prepared(tmp_path)
    model = build_semantic_model(entities)
    assert model.fact_comment_translations[0]["is_current"] is True
    entities.response_answers[0]["answer_text"] = "Changed"
    stale = build_semantic_model(entities)
    assert stale.fact_comment_translations[0]["is_current"] is False
    write_semantic_model(stale, tmp_path / format, format)
    if format == "json":
        rows = json.loads((tmp_path / format / "fact_comment_translations.json").read_text())
    elif format == "csv":
        with (tmp_path / format / "fact_comment_translations.csv").open(newline="") as handle:
            rows = list(csv.DictReader(handle))
    elif format == "parquet":
        import pyarrow.parquet as pq

        rows = pq.read_table(tmp_path / format / "fact_comment_translations.parquet").to_pylist()
    else:
        with sqlite3.connect(tmp_path / format / "semantic_model.sqlite") as connection:
            rows = [
                dict(zip(("translated_text", "is_current"), row, strict=True))
                for row in connection.execute("SELECT translated_text, is_current FROM fact_comment_translations")
            ]
    assert rows[0]["translated_text"] == " Greetings "
    assert str(rows[0]["is_current"]).lower() in {"false", "0"}


def test_semantic_writer_rechecks_hash_after_model_answer_changes(tmp_path: Path) -> None:
    model = build_semantic_model(_prepared(tmp_path))
    model.fact_response_answers[0]["answer_text"] = "Changed after model build"
    assert model.fact_comment_translations[0]["is_current"] is True
    write_semantic_model(model, tmp_path / "out", "json")
    rows = json.loads((tmp_path / "out" / "fact_comment_translations.json").read_text())
    assert rows[0]["is_current"] is False


@pytest.mark.parametrize("input_format", ["csv", "parquet"])
def test_cli_imports_prepared_translations_without_modifying_raw_answers(tmp_path: Path, input_format: str) -> None:
    original = _parsed(tmp_path)
    source_folder = tmp_path / "source_entities"
    write_entities(original, source_folder)
    answer_id = (
        original.comments[0]["response_answer_id"]
        if original.comments
        else original.response_answers[0]["response_answer_id"]
    )
    record = {
        "response_answer_id": answer_id,
        "target_language": "EN",
        "source_text_hash": source_text_hash(" Grüße <tag> "),
        "translated_text": " Greetings ",
    }
    input_file = tmp_path / f"prepared.{input_format}"
    if input_format == "csv":
        with input_file.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(record))
            writer.writeheader()
            writer.writerow(record)
    else:
        import pyarrow as pa
        import pyarrow.parquet as pq

        pq.write_table(pa.Table.from_pylist([record]), input_file)
    output = tmp_path / "translated_entities"
    result = CliRunner().invoke(
        app, ["translations", "import", str(source_folder), str(input_file), "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert (output / "comment_translations.parquet").exists()
    imported = load_entities(output)
    assert imported.response_answers == original.response_answers
    assert imported.comment_translations[0]["translated_text"] == " Greetings "
    assert imported.comment_translations[0]["source_language"] == "DE"


def test_cli_rejects_translation_with_wrong_source_hash(tmp_path: Path) -> None:
    original = _parsed(tmp_path)
    source_folder = tmp_path / "source_entities"
    write_entities(original, source_folder)
    input_file = tmp_path / "prepared.csv"
    with input_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["response_answer_id", "target_language", "source_text_hash", "translated_text"]
        )
        writer.writeheader()
        writer.writerow({
            "response_answer_id": original.response_answers[0]["response_answer_id"],
            "target_language": "EN",
            "source_text_hash": "0" * 64,
            "translated_text": "Bad",
        })
    result = CliRunner().invoke(
        app, ["translations", "import", str(source_folder), str(input_file), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code != 0
    assert "hash" in result.output.lower()


@pytest.mark.parametrize(
    "payload, suffix, expected",
    [
        ("wrong,header\nvalue,value\n", ".csv", "must have columns"),
        (
            "response_answer_id,target_language,source_text_hash,translated_text\na,EN,hash,text,extra\n",
            ".csv",
            "extra values",
        ),
        ("anything", ".txt", "CSV or Parquet"),
    ],
)
def test_cli_rejects_malformed_translation_file(tmp_path: Path, payload: str, suffix: str, expected: str) -> None:
    folder = tmp_path / "entities"
    write_entities(_parsed(tmp_path), folder)
    source = tmp_path / f"prepared{suffix}"
    source.write_text(payload, encoding="utf-8")
    output = tmp_path / "out"
    result = CliRunner().invoke(app, ["translations", "import", str(folder), str(source), "-o", str(output)])
    assert result.exit_code != 0
    assert expected in result.output
    assert not output.exists()


def test_cli_rejects_occupied_output_and_unsupported_format(tmp_path: Path) -> None:
    folder = tmp_path / "entities"
    write_entities(_parsed(tmp_path), folder)
    source = tmp_path / "prepared.csv"
    source.write_text("response_answer_id,target_language,source_text_hash,translated_text\n", encoding="utf-8")
    occupied = CliRunner().invoke(app, ["translations", "import", str(folder), str(source), "-o", str(folder)])
    assert occupied.exit_code != 0
    assert "already contains entity files" in occupied.output
    invalid = CliRunner().invoke(
        app, ["translations", "import", str(folder), str(source), "-o", str(tmp_path / "out"), "--format", "sqlite"]
    )
    assert invalid.exit_code != 0
    assert "format must be" in invalid.output


@pytest.mark.parametrize(
    "corruption, expected",
    [
        ("object", "JSON list"),
        ("extra_column", "schema must contain exactly"),
        ("duplicate_format", "Multiple formats"),
    ],
)
def test_load_rejects_malformed_optional_translation_sidecar(tmp_path: Path, corruption: str, expected: str) -> None:
    folder = tmp_path / "entities"
    write_entities(_prepared(tmp_path), folder)
    path = folder / "comment_translations.json"
    if corruption == "object":
        path.write_text("{}", encoding="utf-8")
    elif corruption == "extra_column":
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows[0]["unexpected"] = "value"
        path.write_text(json.dumps(rows), encoding="utf-8")
    else:
        (folder / "comment_translations.csv").write_text("comment_translation_id\n", encoding="utf-8")
    with pytest.raises(ValueError, match=expected):
        load_entities(folder)


def test_cli_rejects_wrong_parquet_input_schema(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    folder = tmp_path / "entities"
    write_entities(_parsed(tmp_path), folder)
    source = tmp_path / "prepared.parquet"
    pq.write_table(pa.Table.from_pylist([{"wrong": "column"}]), source)
    result = CliRunner().invoke(
        app, ["translations", "import", str(folder), str(source), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code != 0
    assert "Translation Parquet must have columns" in result.output


def test_parquet_import_reports_missing_pyarrow(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def missing_pyarrow(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] | None = (),
        level: int = 0,
    ):
        if name == "pyarrow.parquet":
            raise ImportError("PyArrow not installed")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", missing_pyarrow)
    with pytest.raises(RuntimeError, match="PyArrow is required"):
        _read_prepared(Path("unused.parquet"))
