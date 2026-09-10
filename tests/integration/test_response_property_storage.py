import copy
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


def _properties(survey_id: str, properties: list[tuple[str, str, str]]) -> EntitySet:
    columns = [
        {
            "source_column": source,
            "source_column_index": index,
            "source_import_id": source,
            "label": source,
            "kind": "embedded",
            "reason": "Declared in survey flow",
            "storage_table": "responses",
            "storage_column": storage,
        }
        for index, (source, storage, _) in enumerate(properties)
    ]
    return EntitySet(
        surveys=[{"survey_id": survey_id, "survey_name": survey_id, "source_columns_json": json.dumps(columns)}],
        responses=[
            {
                "response_id": f"response-{survey_id}",
                "response_external_id": "R_1",
                "survey_id": survey_id,
                **{storage: value for _, storage, value in properties},
            }
        ],
    )


def test_merge_response_property_union_has_nulls_and_does_not_mutate_inputs() -> None:
    first = _properties("SV_A", [("Region", "Region", "North")])
    second = _properties("SV_B", [("Country", "Country", "DE")])
    original = copy.deepcopy([first, second])

    merged = merge_entity_sets([first, second])

    assert merged.responses[0]["Country"] is None
    assert merged.responses[1]["Region"] is None
    assert set(merged.responses[0]) == set(merged.responses[1])
    merged.responses[0]["Region"] = "Changed"
    assert [first, second] == original

    assert merge_entity_sets([merged]).responses == merged.responses


def test_merge_preserves_source_identity_when_storage_names_collide() -> None:
    first = _properties("SV_A", [("status", "property_status", "001"), ("Region", "Region", "North")])
    second = _properties("SV_B", [("property_status", "property_status", "002"), ("region", "region", "South")])
    original = copy.deepcopy([first, second])

    merged = merge_entity_sets([first, second])
    reverse = merge_entity_sets([second, first])
    mappings = {}
    for survey, response in zip(merged.surveys, merged.responses, strict=True):
        columns = json.loads(survey["source_columns_json"])
        mappings[survey["survey_id"]] = {column["source_column"]: column["storage_column"] for column in columns}
        assert len({key.casefold() for key in response}) == len(response)
    assert mappings["SV_A"]["status"] != mappings["SV_B"]["property_status"]
    assert mappings["SV_A"]["Region"].casefold() != mappings["SV_B"]["region"].casefold()
    assert merged.responses[0][mappings["SV_A"]["status"]] == "001"
    assert merged.responses[1][mappings["SV_B"]["property_status"]] == "002"
    assert merged.responses[0][mappings["SV_B"]["property_status"]] is None
    assert sorted(merged.responses, key=lambda row: row["survey_id"]) == sorted(
        reverse.responses, key=lambda row: row["survey_id"]
    )
    assert [first, second] == original
    assert merge_entity_sets([merged]).responses == merged.responses


def test_empty_source_name_is_distinct_from_literal_property_name() -> None:
    first = _properties("SV_A", [("", "property", "first")])
    second = _properties("SV_B", [("property", "property", "second")])
    merged = merge_entity_sets([first, second])
    keys = [json.loads(survey["source_columns_json"])[0]["storage_column"] for survey in merged.surveys]
    assert keys[0] != keys[1]
    assert merged.responses[0][keys[0]] == "first"
    assert merged.responses[0][keys[1]] is None
    assert merged.responses[1][keys[1]] == "second"


def test_merge_empty_survey_preserves_required_schema_and_property_dictionary(
    tmp_path: Path, survey_files: tuple[Path, Path]
) -> None:
    entities = parse_survey(*survey_files)
    entities.responses.clear()
    entities.response_answers.clear()
    columns = json.loads(entities.surveys[0]["source_columns_json"])
    columns.extend(json.loads(_properties("SV_A", [("Region", "Region", "North")]).surveys[0]["source_columns_json"]))
    entities.surveys[0]["source_columns_json"] = json.dumps(columns)
    entities._present_columns["responses"] = {"response_id", "response_external_id", "survey_id", "LegacyEmpty"}
    validate_entity_set(entities, strict=True)

    merged = merge_entity_sets([entities])

    validate_entity_set(merged, strict=True)
    assert merged.responses == []
    assert {"Region", "LegacyEmpty"} <= merged._present_columns["responses"]
    for format in ("csv", "parquet"):
        write_entities(merged, tmp_path / format, format)
        loaded = load_entities(tmp_path / format)
        assert {"Region", "LegacyEmpty"} <= loaded._present_columns["responses"]


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_properties_and_source_dictionary_survive_entity_round_trip(
    tmp_path: Path, survey_files: tuple[Path, Path], format: str
) -> None:
    entities = parse_survey(*survey_files)
    manifest = _properties("SV_A", [("Region", "Region", "North")]).surveys[0]["source_columns_json"]
    entities.surveys[0]["source_columns_json"] = manifest
    entities.responses[0].update({"Region": "North", "Country": "001", "Permissions": "false"})
    entities.responses[1].update({"Region": None, "Country": "002", "Permissions": "0"})
    write_entities(entities, tmp_path / format, format)

    loaded = load_entities(tmp_path / format)

    assert loaded.surveys[0]["source_columns_json"] == manifest
    for before, after in zip(entities.responses, loaded.responses, strict=True):
        for key in ("Region", "Country", "Permissions"):
            assert after[key] == before[key]
    assert len(loaded.__dataclass_fields__) == len(entities.__dataclass_fields__)
    model = build_semantic_model(loaded)
    assert model.fact_responses[0]["Country"] == "001"


@pytest.mark.parametrize("format", ["sqlite", "parquet"])
def test_empty_semantic_response_table_retains_declared_properties(tmp_path: Path, format: str) -> None:
    entities = _properties("SV_EMPTY", [("Region", "Region", "North")])
    model = SemanticModel(dim_surveys=entities.surveys)
    write_semantic_model(model, tmp_path, format)
    if format == "sqlite":
        with sqlite3.connect(tmp_path / "semantic_model.sqlite") as connection:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(fact_responses)")}
    else:
        import pyarrow.parquet as pq

        columns = set(pq.read_schema(tmp_path / "fact_responses.parquet").names)
    assert "Region" in columns


@pytest.mark.parametrize("format", ["sqlite", "parquet"])
def test_dynamic_response_properties_do_not_inherit_answer_types(tmp_path: Path, format: str) -> None:
    values = {"answer_numeric": "001", "is_selected": "false", "source_column_index": "002"}
    model = SemanticModel(fact_responses=[{"response_id": "R_1", **values}])
    write_semantic_model(model, tmp_path, format)
    if format == "sqlite":
        with sqlite3.connect(tmp_path / "semantic_model.sqlite") as connection:
            connection.row_factory = sqlite3.Row
            restored = dict(connection.execute("SELECT * FROM fact_responses").fetchone())
    else:
        import pyarrow.parquet as pq

        restored = pq.read_table(tmp_path / "fact_responses.parquet").to_pylist()[0]
    assert {key: restored[key] for key in values} == values
