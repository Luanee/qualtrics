import json
from pathlib import Path

import pytest

from qualtrics import parse_survey
from qualtrics._common.models.entity_set import merge_entity_sets
from qualtrics._common.models.semantic import build_semantic_model
from qualtrics._common.serialization.io import load_entities, write_entities
from qualtrics._common.serialization.semantic import write_semantic_model


def test_parse_keeps_source_dictionary_out_of_survey_row(survey_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*survey_files)

    assert "source_columns_json" not in entities.surveys[0]
    assert "flow_definition_json" not in entities.surveys[0]
    columns = entities.survey_manifests["SV_SAMPLE"]["source_columns_json"]
    assert isinstance(columns, list)
    assert columns[0]["source_column"] == "ResponseId"
    assert columns[0]["storage_column"] == "response_external_id"


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_entity_export_writes_one_manifest_for_all_surveys(
    tmp_path: Path, survey_files: tuple[Path, Path], format: str
) -> None:
    first = parse_survey(*survey_files)
    second = parse_survey(*survey_files, survey_id="SV_SECOND")
    combined = merge_entity_sets([first, second])

    folder = tmp_path / format
    write_entities(combined, folder, format)

    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert set(manifest["surveys"]) == {"SV_SAMPLE", "SV_SECOND"}
    assert all(isinstance(value["source_columns_json"], list) for value in manifest["surveys"].values())
    loaded = load_entities(folder)
    assert loaded.survey_manifests == combined.survey_manifests
    assert all("source_columns_json" not in row for row in loaded.surveys)


@pytest.mark.parametrize("format", ["json", "csv", "parquet", "sqlite"])
def test_semantic_export_keeps_manifest_out_of_dim_surveys(
    tmp_path: Path, survey_files: tuple[Path, Path], format: str
) -> None:
    model = build_semantic_model(parse_survey(*survey_files))

    folder = tmp_path / format
    write_semantic_model(model, folder, format)

    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert list(manifest["surveys"]) == ["SV_SAMPLE"]
    assert "source_columns_json" not in model.dim_surveys[0]


def test_combined_semantic_manifest_preserves_each_survey(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    combined = merge_entity_sets([
        parse_survey(*survey_files),
        parse_survey(*survey_files, survey_id="SV_SECOND"),
    ])
    folder = tmp_path / "semantic"

    write_semantic_model(build_semantic_model(combined), folder, "parquet")

    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["surveys"]) == {"SV_SAMPLE", "SV_SECOND"}
    assert manifest["surveys"] == combined.survey_manifests


@pytest.mark.parametrize("bad", [{"schema_version": 2, "surveys": {}}, {"schema_version": 1, "surveys": {}}])
def test_entity_loader_rejects_invalid_manifest(
    tmp_path: Path, survey_files: tuple[Path, Path], bad: dict[str, object]
) -> None:
    folder = tmp_path / "entities"
    write_entities(parse_survey(*survey_files), folder, "json")
    (folder / "manifest.json").write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(ValueError, match="[Mm]anifest"):
        load_entities(folder)
