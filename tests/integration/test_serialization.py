import csv
import json
from pathlib import Path

import pytest

from qualtrics import parse_survey
from qualtrics._common.models.entities import ENTITY_NAMES, EntitySet
from qualtrics._common.models.semantic import build_semantic_model
from qualtrics._common.serialization.io import load_entities, write_entities


def test_csv_round_trip_preserves_analytical_answer_types(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*survey_files)
    answer = entities.response_answers[0]
    answer["answer_numeric"] = 12.5
    answer["answer_boolean"] = True
    answer["is_selected"] = False
    write_entities(entities, tmp_path, "csv")
    loaded = load_entities(tmp_path)
    restored = loaded.response_answers[0]
    assert restored["answer_numeric"] == 12.5
    assert restored["answer_boolean"] is True
    assert restored["is_selected"] is False


def _wide_survey(tmp_path: Path) -> EntitySet:
    source = tmp_path / "wide-survey.csv"
    count = 500
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "Region", *(f"Q{index}" for index in range(count))],
            ["Response ID", "Region", *(f'Question {index} — café, "quoted" feedback' for index in range(count))],
            ["{}", "{}", *(json.dumps({"ImportId": f"QID{index}"}) for index in range(count))],
            ["R_1", "North", *("answer" for _ in range(count))],
        ])
    return parse_survey(source)


def test_wide_survey_manifest_round_trips_all_formats_and_supports_semantic_model(tmp_path: Path) -> None:
    entities = _wide_survey(tmp_path)
    survey_id = entities.surveys[0]["survey_id"]
    manifest = entities.survey_manifests[survey_id]
    assert len(json.dumps(manifest, ensure_ascii=False)) > 131_072
    assert "source_columns_json" not in entities.surveys[0]
    assert len(entities.question_fields) == 500
    assert len(entities.response_answers) == 500
    assert {row["answer_text"] for row in entities.response_answers} == {"answer"}
    for format in ("csv", "json", "parquet"):
        write_entities(entities, tmp_path / format, format)
        payload = json.loads((tmp_path / format / "manifest.json").read_text())
        assert payload == {"schema_version": 1, "surveys": {survey_id: manifest}}

    json_loaded = load_entities(tmp_path / "json")
    assert json_loaded.survey_manifests[survey_id] == manifest
    for format in ("csv", "parquet"):
        loaded = load_entities(tmp_path / format)
        assert loaded.survey_manifests[survey_id] == manifest
        assert "source_columns_json" not in loaded.surveys[0]
        for name in ENTITY_NAMES:
            assert len(getattr(loaded, name)) == len(getattr(json_loaded, name)), name
        assert loaded.surveys[0]["survey_id"] == json_loaded.surveys[0]["survey_id"]
        assert [row["question_field_id"] for row in loaded.question_fields] == [
            row["question_field_id"] for row in json_loaded.question_fields
        ]
        assert loaded.responses[0]["Region"] == "North"
        assert loaded.response_answers == json_loaded.response_answers
        assert len(loaded.response_answers) == 500
        assert {row["answer_text"] for row in loaded.response_answers} == {"answer"}
        model = build_semantic_model(loaded)
        assert len(model.dim_questions) == 500
        assert model.fact_responses[0]["Region"] == "North"

    explicit_tables = load_entities(**{name: tmp_path / "csv" / f"{name}.csv" for name in ENTITY_NAMES})
    assert explicit_tables.survey_manifests == {}
    assert "source_columns_json" not in explicit_tables.surveys[0]
    assert explicit_tables.responses[0]["Region"] == "North"


@pytest.mark.parametrize("initial_limit", [131_072, 400_000])
def test_csv_reader_limit_handles_platform_overflow_without_lowering_existing_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, initial_limit: int
) -> None:
    entities = _wide_survey(tmp_path)
    survey_id = entities.surveys[0]["survey_id"]
    manifest = entities.survey_manifests[survey_id]
    manifest_size = len(json.dumps(manifest, ensure_ascii=False))
    assert 131_072 < manifest_size < 250_000
    write_entities(entities, tmp_path / "csv", "csv")
    real_field_size_limit = csv.field_size_limit
    previous_limit = real_field_size_limit()

    def platform_field_size_limit(new_limit: int | None = None) -> int:
        if new_limit is None:
            return real_field_size_limit()
        if new_limit > 300_000:
            raise OverflowError("platform CSV field limit")
        return real_field_size_limit(new_limit)

    try:
        real_field_size_limit(initial_limit)
        monkeypatch.setattr(csv, "field_size_limit", platform_field_size_limit)
        loaded = load_entities(tmp_path / "csv")
        assert loaded.survey_manifests[survey_id] == manifest
        assert real_field_size_limit() >= max(initial_limit, manifest_size)
    finally:
        real_field_size_limit(previous_limit)
