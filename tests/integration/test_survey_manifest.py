import json
from pathlib import Path

import pytest

from qualtrics import parse_survey
from qualtrics._common.models.entities import EntitySet
from qualtrics._common.models.entity_set import merge_entity_sets
from qualtrics._common.models.semantic import SemanticModel, build_semantic_model
from qualtrics._common.serialization.io import load_entities, write_entities
from qualtrics._common.serialization.semantic import write_semantic_model


def test_manifest_field_does_not_change_positional_entity_or_semantic_constructors() -> None:
    survey = {"survey_id": "SV_SAMPLE", "survey_name": "Sample"}
    assert EntitySet(set(), {}, [survey]).surveys == [survey]
    assert SemanticModel([{"response_id": "R_1"}]).fact_responses == [{"response_id": "R_1"}]


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


def test_merge_and_semantic_model_do_not_alias_input_flow(survey_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*survey_files)
    entities.survey_manifests["SV_SAMPLE"]["flow_definition_json"] = {"root": {"children": ["original"]}}

    combined = merge_entity_sets([entities])
    combined.survey_manifests["SV_SAMPLE"]["flow_definition_json"]["root"]["children"].append("merged")
    assert entities.survey_manifests["SV_SAMPLE"]["flow_definition_json"]["root"]["children"] == ["original"]

    model = build_semantic_model(combined)
    model.survey_manifests["SV_SAMPLE"]["flow_definition_json"]["root"]["children"].append("semantic")
    assert combined.survey_manifests["SV_SAMPLE"]["flow_definition_json"]["root"]["children"] == [
        "original",
        "merged",
    ]


@pytest.mark.parametrize("bad", [{"schema_version": 2, "surveys": {}}, {"schema_version": 1, "surveys": {}}])
def test_entity_loader_rejects_invalid_manifest(
    tmp_path: Path, survey_files: tuple[Path, Path], bad: dict[str, object]
) -> None:
    folder = tmp_path / "entities"
    write_entities(parse_survey(*survey_files), folder, "json")
    (folder / "manifest.json").write_text(json.dumps(bad), encoding="utf-8")

    with pytest.raises(ValueError, match="[Mm]anifest"):
        load_entities(folder)


def test_explicit_entity_paths_can_name_a_manifest_outside_the_table_folder(
    tmp_path: Path, survey_files: tuple[Path, Path]
) -> None:
    entities = parse_survey(*survey_files)
    folder = tmp_path / "entities"
    write_entities(entities, folder, "json")
    separate_manifest = tmp_path / "metadata.json"
    separate_manifest.write_text((folder / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")

    loaded = load_entities(surveys=folder / "surveys.json", manifest=separate_manifest)

    assert loaded.survey_manifests == entities.survey_manifests


def test_invalid_manifest_fails_before_entity_or_sqlite_output(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*survey_files)
    entities.survey_manifests["SV_SAMPLE"]["source_columns_json"] = "not a list"
    entity_folder = tmp_path / "entities"

    with pytest.raises(ValueError, match="source_columns_json"):
        write_entities(entities, entity_folder, "json")
    assert not entity_folder.exists() or not list(entity_folder.iterdir())

    model = build_semantic_model(entities)
    semantic_folder = tmp_path / "semantic"
    with pytest.raises(ValueError, match="source_columns_json"):
        write_semantic_model(model, semantic_folder, "sqlite")
    assert not semantic_folder.exists() or not list(semantic_folder.iterdir())
