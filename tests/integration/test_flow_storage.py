from __future__ import annotations

import csv
import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from qualtrics import load_entities, parse_survey, write_entities
from qualtrics._common.models.entities import EntitySet
from qualtrics._common.models.entity_set import merge_entity_sets
from qualtrics._common.models.semantic import build_semantic_model
from qualtrics._common.serialization.semantic import write_semantic_model


def _survey_files(tmp_path: Path, *, include_flow: bool = True) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "flow.csv"
    qsf_path = tmp_path / "flow.qsf"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1"],
            ["Response ID", "Exported question"],
            ["{}", json.dumps({"ImportId": "QID1"})],
            ["R_1", "Sales"],
        ])
    elements: list[dict[str, object]] = [
        {
            "Element": "SQ",
            "PrimaryAttribute": "QID1",
            "Payload": {
                "QuestionID": "QID1",
                "QuestionText": "Department",
                "QuestionType": "MC",
                "Selector": "SAVR",
                "Choices": {"1": {"Display": "Sales"}},
            },
        },
        {
            "Element": "SQ",
            "PrimaryAttribute": "QID2",
            "Payload": {"QuestionID": "QID2", "QuestionText": "Definition only", "QuestionType": "TE"},
        },
        {
            "Element": "BL",
            "Payload": {
                "BL_1": {
                    "ID": "BL_1",
                    "Description": "Questions",
                    "Type": "Standard",
                    "BlockElements": [
                        {"Type": "Question", "QuestionID": "QID1"},
                        {"Type": "Question", "QuestionID": "QID2"},
                    ],
                }
            },
        },
    ]
    if include_flow:
        elements.append({
            "Element": "FL",
            "Payload": {"Type": "Root", "FlowID": "FL_1", "Flow": [{"Type": "Block", "ID": "BL_1"}]},
        })
    qsf_path.write_text(
        json.dumps({"SurveyEntry": {"SurveyID": "SV_FLOW", "SurveyName": "Flow"}, "SurveyElements": elements}),
        encoding="utf-8",
    )
    return csv_path, qsf_path


def test_parse_stores_optional_flow_as_json_scalar_and_keeps_definition_only_question(tmp_path: Path) -> None:
    entities = parse_survey(*_survey_files(tmp_path))
    scalar = entities.surveys[0]["flow_definition_json"]
    definition = json.loads(scalar)

    assert isinstance(scalar, str)
    assert definition["questions"]["QID2"]["text"] == "Definition only"
    assert {question["question_external_id"] for question in entities.questions} == {"QID1"}


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_flow_scalar_round_trips_entity_formats(tmp_path: Path, format: str) -> None:
    entities = parse_survey(*_survey_files(tmp_path / "input"))
    destination = tmp_path / format
    write_entities(entities, destination, format)

    loaded = load_entities(destination)
    assert loaded.surveys[0]["flow_definition_json"] == entities.surveys[0]["flow_definition_json"]


def test_flow_scalar_reaches_semantic_sqlite(tmp_path: Path) -> None:
    entities = parse_survey(*_survey_files(tmp_path / "input"))
    destination = tmp_path / "semantic"
    destination.mkdir()
    write_semantic_model(build_semantic_model(entities), destination, "sqlite")

    with sqlite3.connect(destination / "semantic_model.sqlite") as connection:
        value = connection.execute("SELECT flow_definition_json FROM dim_surveys").fetchone()[0]
    assert value == entities.surveys[0]["flow_definition_json"]


def test_legacy_absent_flow_remains_absent_when_combined_with_flow_survey(tmp_path: Path) -> None:
    with_flow = parse_survey(*_survey_files(tmp_path / "new"))
    legacy_csv, legacy_qsf = _survey_files(tmp_path / "legacy", include_flow=False)
    legacy = parse_survey(legacy_csv, legacy_qsf, survey_id="SV_LEGACY")

    combined = merge_entity_sets([with_flow, legacy])
    surveys = {row["survey_id"]: row for row in combined.surveys}
    assert "flow_definition_json" in surveys["SV_FLOW"]
    assert "flow_definition_json" not in surveys["SV_LEGACY"]


def test_explicit_flow_file_is_used_with_definition_metadata(tmp_path: Path) -> None:
    csv_path, qsf_path = _survey_files(tmp_path / "input", include_flow=False)
    flow_path = tmp_path / "flow.json"
    flow_path.write_text(json.dumps({"result": {"Flow": [{"Type": "Block", "ID": "BL_1"}]}}), encoding="utf-8")

    entities = parse_survey(csv_path, qsf_path, flow_path=flow_path)
    definition = json.loads(entities.surveys[0]["flow_definition_json"])
    assert definition["root"]["children"][0]["config"]["ID"] == "BL_1"
    assert definition["blocks"]["BL_1"]["name"] == "Questions"
    assert definition["questions"]["QID2"]["text"] == "Definition only"


def test_standalone_flow_definition_keeps_its_own_metadata(tmp_path: Path) -> None:
    csv_path, _ = _survey_files(tmp_path / "definition", include_flow=False)
    standalone_csv = tmp_path / "responses.csv"
    standalone_csv.write_bytes(csv_path.read_bytes())
    flow_path = tmp_path / "standalone.json"
    flow_path.write_text(
        json.dumps({
            "Flow": [{"Type": "Block", "ID": "BL_API"}],
            "Blocks": [
                {
                    "ID": "BL_API",
                    "Description": "API questions",
                    "Type": "Standard",
                    "BlockElements": [{"Type": "Question", "QuestionID": "QID_API"}],
                }
            ],
            "Questions": {"QID_API": {"QuestionID": "QID_API", "QuestionText": "API label", "QuestionType": "TE"}},
        }),
        encoding="utf-8",
    )

    entities = parse_survey(standalone_csv, flow_path=flow_path)
    definition = json.loads(entities.surveys[0]["flow_definition_json"])
    assert definition["blocks"]["BL_API"]["name"] == "API questions"
    assert definition["questions"]["QID_API"]["text"] == "API label"


@pytest.mark.parametrize(
    "wrap",
    [
        lambda definition: {"SurveyDefinition": definition},
        lambda definition: {"result": {"SurveyDefinition": definition}},
    ],
)
def test_separate_wrapped_definition_supplies_metadata_for_raw_flow(
    tmp_path: Path, wrap: Callable[[dict[str, object]], dict[str, object]]
) -> None:
    csv_path, qsf_path = _survey_files(tmp_path / "input", include_flow=False)
    definition = json.loads(qsf_path.read_text(encoding="utf-8"))
    elements = definition.pop("SurveyElements")
    questions = {
        str(element["PrimaryAttribute"]): element["Payload"] for element in elements if element["Element"] == "SQ"
    }
    blocks = next(element["Payload"] for element in elements if element["Element"] == "BL")
    wrapped = wrap({"SurveyEntry": definition["SurveyEntry"], "Blocks": blocks, "Questions": questions})
    qsf_path.write_text(json.dumps(wrapped), encoding="utf-8")
    flow_path = tmp_path / "raw-flow.json"
    flow_path.write_text(json.dumps({"Flow": [{"Type": "Block", "ID": "BL_1"}]}), encoding="utf-8")

    entities = parse_survey(csv_path, qsf_path, flow_path=flow_path)
    flow = json.loads(entities.surveys[0]["flow_definition_json"])
    assert flow["blocks"]["BL_1"]["name"] == "Questions"
    assert flow["questions"]["QID2"]["text"] == "Definition only"


def _lineage_files(
    folder: Path,
    *,
    source: str,
    container: str,
    wrapper: str | None = None,
    flow_mode: str = "embedded",
) -> tuple[Path, Path, Path | None]:
    folder.mkdir(parents=True, exist_ok=True)
    csv_path = folder / "responses.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1", "QID2"],
            ["Response ID", "First answer", "Second answer"],
            ["{}", '{"ImportId":"QID1"}', '{"ImportId":"QID2"}'],
            ["R_1", "Alpha", "Beta"],
        ])
    questions = {
        qid: {"QuestionID": qid, "QuestionText": label, "QuestionType": "TE"}
        for qid, label in (("QID1", "First answer"), ("QID2", "Second answer"))
    }
    blocks = {
        "BL_FIRST": {
            "ID": "BL_FIRST",
            "Description": "First block",
            "Type": "Standard",
            "BlockElements": [
                {"Type": "PageBreak"},
                {"Type": "Question", "QuestionID": "QID1"},
            ],
        },
        "BL_TRASH": {
            "ID": "BL_TRASH",
            "Description": "Trash",
            "Type": "Trash",
            "BlockElements": [],
        },
        "BL_SECOND": {
            "ID": "BL_SECOND",
            "Description": "Second block",
            "Type": "Standard",
            "BlockElements": [{"Type": "Question", "QuestionID": "QID2"}],
        },
    }
    block_payload: object = blocks if container == "dict" else list(blocks.values())
    flow = {
        "Type": "Root",
        "Flow": [
            {"Type": "Block", "ID": "BL_FIRST"},
            {"Type": "Block", "ID": "BL_SECOND"},
            {"Type": "Block", "ID": "BL_FIRST"},
        ],
    }
    entry = {"SurveyID": "SV_LINEAGE", "SurveyName": "Lineage"}
    if source == "qsf":
        elements: list[dict[str, object]] = [
            {"Element": "SQ", "PrimaryAttribute": qid, "Payload": question} for qid, question in questions.items()
        ]
        elements.append({"Element": "BL", "Payload": block_payload})
        if flow_mode == "embedded":
            elements.append({"Element": "FL", "Payload": flow})
        definition: dict[str, object] = {"SurveyEntry": entry, "SurveyElements": elements}
    else:
        definition = {"SurveyEntry": entry, "Questions": questions, "Blocks": block_payload}
        if flow_mode == "embedded":
            definition["Flow"] = flow
    if wrapper is not None:
        definition = {wrapper: definition}
    definition_path = folder / "definition.json"
    definition_path.write_text(json.dumps(definition), encoding="utf-8")
    flow_path = None
    if flow_mode == "separate":
        flow_path = folder / "flow.json"
        flow_path.write_text(json.dumps({"result": {"Flow": flow}}), encoding="utf-8")
    return csv_path, definition_path, flow_path


def _assert_lineage(entities: EntitySet, *, has_flow: bool) -> None:
    assert [(row["section_external_id"], row["section_name"], row["section_order"]) for row in entities.sections] == [
        ("BL_FIRST", "First block", 1),
        ("BL_SECOND", "Second block", 3),
    ]
    sections = {row["section_external_id"]: row for row in entities.sections}
    questions = {row["question_external_id"]: row for row in entities.questions}
    assert len(questions) == 2
    for qid, block_id, block_order, question_order in (
        ("QID1", "BL_FIRST", 1, 2),
        ("QID2", "BL_SECOND", 3, 1),
    ):
        question = questions[qid]
        assert question["section_external_id"] == block_id
        assert question["section_id"] == sections[block_id]["section_id"]
        assert question["section_id"] != block_id
        assert question["block_id"] == block_id
        assert question["block_order"] == block_order
        assert question["question_order_in_block"] == question_order
    dimension = {row["question_external_id"]: row for row in build_semantic_model(entities).dim_questions}
    assert len(dimension) == 2
    for qid, block_id in (("QID1", "BL_FIRST"), ("QID2", "BL_SECOND")):
        assert dimension[qid]["section_id"] == sections[block_id]["section_id"]
        assert dimension[qid]["section_name"] == sections[block_id]["section_name"]
        assert dimension[qid]["block_order"] == questions[qid]["block_order"]
    if has_flow:
        flow = json.loads(entities.surveys[0]["flow_definition_json"])
        assert [node["config"]["ID"] for node in flow["root"]["children"]] == ["BL_FIRST", "BL_SECOND", "BL_FIRST"]
        assert set(sections) <= set(flow["blocks"])
    else:
        assert "flow_definition_json" not in entities.surveys[0]


@pytest.mark.parametrize(
    "source,wrappers",
    [
        ("qsf", [None]),
        ("direct", [None, "result", "SurveyDefinition", "survey_definition", "payload"]),
    ],
)
@pytest.mark.parametrize("flow_mode", ["embedded", "separate", "absent"])
def test_dictionary_and_list_blocks_keep_entity_semantic_and_flow_lineage(
    tmp_path: Path, source: str, wrappers: list[str | None], flow_mode: str
) -> None:
    for wrapper in wrappers:
        parsed = {}
        for container in ("dict", "list"):
            paths = _lineage_files(
                tmp_path / source / str(wrapper) / flow_mode / container,
                source=source,
                container=container,
                wrapper=wrapper,
                flow_mode=flow_mode,
            )
            entities = parse_survey(paths[0], paths[1], flow_path=paths[2])
            _assert_lineage(entities, has_flow=flow_mode != "absent")
            parsed[container] = entities
        assert parsed["dict"].sections == parsed["list"].sections
        assert parsed["dict"].questions == parsed["list"].questions
        assert build_semantic_model(parsed["dict"]).dim_questions == build_semantic_model(parsed["list"]).dim_questions


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
@pytest.mark.parametrize("container", ["dict", "list"])
def test_block_lineage_survives_public_entity_storage(tmp_path: Path, format: str, container: str) -> None:
    csv_path, definition_path, flow_path = _lineage_files(
        tmp_path / "input", source="direct", container=container, flow_mode="separate"
    )
    entities = parse_survey(csv_path, definition_path, flow_path=flow_path)
    destination = tmp_path / format
    write_entities(entities, destination, format)
    loaded = load_entities(destination)
    _assert_lineage(loaded, has_flow=True)


@pytest.mark.parametrize("flow_mode", ["absent", "separate"])
def test_block_ids_use_explicit_value_then_dictionary_key_and_never_list_position(
    tmp_path: Path, flow_mode: str
) -> None:
    csv_path, definition_path, flow_path = _lineage_files(
        tmp_path / "input", source="direct", container="dict", flow_mode=flow_mode
    )
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    blocks = definition["Blocks"]
    blocks["BL_FIRST"].pop("ID")
    blocks["NOT_THE_ID"] = blocks.pop("BL_SECOND")
    definition_path.write_text(json.dumps(definition), encoding="utf-8")
    entities = parse_survey(csv_path, definition_path, flow_path=flow_path)
    assert [section["section_external_id"] for section in entities.sections] == ["BL_FIRST", "BL_SECOND"]
    assert [question["section_external_id"] for question in entities.questions] == ["BL_FIRST", "BL_SECOND"]
    if flow_path:
        flow = json.loads(entities.surveys[0]["flow_definition_json"])
        assert set(flow["blocks"]) == {"BL_FIRST", "BL_TRASH", "BL_SECOND"}

    definition["Blocks"] = [{"Type": "Standard", "Description": "No ID", "BlockElements": []}, *blocks.values()]
    definition_path.write_text(json.dumps(definition), encoding="utf-8")
    list_entities = parse_survey(csv_path, definition_path, flow_path=flow_path)
    assert [section["section_external_id"] for section in list_entities.sections] == ["BL_SECOND"]
    assert list_entities.sections[0]["section_order"] == 4
    assert all(section["section_external_id"] not in {"0", "1", "section-1"} for section in list_entities.sections)
    if flow_path:
        flow = json.loads(list_entities.surveys[0]["flow_definition_json"])
        assert set(flow["blocks"]) == {"BL_TRASH", "BL_SECOND"}


def test_direct_blocks_keep_existing_precedence_over_qsf_blocks(tmp_path: Path) -> None:
    csv_path, definition_path, _ = _lineage_files(tmp_path / "input", source="qsf", container="dict")
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    direct = dict(next(element["Payload"] for element in definition["SurveyElements"] if element["Element"] == "BL"))
    direct["BL_FIRST"] = {**direct["BL_FIRST"], "Description": "Direct first"}
    definition["Blocks"] = direct
    definition_path.write_text(json.dumps(definition), encoding="utf-8")

    entities = parse_survey(csv_path, definition_path)
    assert entities.sections[0]["section_name"] == "Direct first"
    assert (
        next(row for row in entities.questions if row["question_external_id"] == "QID1")["block_name"] == "Direct first"
    )


@pytest.mark.parametrize("qsf_container,direct_container", [("dict", "list"), ("list", "dict")])
@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_equivalent_mixed_source_blocks_keep_one_native_section_and_original_order(
    tmp_path: Path, qsf_container: str, direct_container: str, format: str
) -> None:
    csv_path, definition_path, _ = _lineage_files(
        tmp_path / "input", source="qsf", container=qsf_container, flow_mode="embedded"
    )
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    block_element = next(element for element in definition["SurveyElements"] if element["Element"] == "BL")
    blocks = list(block_element["Payload"].values()) if qsf_container == "dict" else block_element["Payload"]
    if qsf_container == "dict":
        block_element["Payload"] = {str(index): block for index, block in enumerate(blocks)}
    if direct_container == "dict":
        definition["Blocks"] = {str(index): block for index, block in enumerate(blocks)}
    else:
        definition["Blocks"] = blocks
    baseline_definition = tmp_path / "baseline.json"
    baseline_definition.write_text(
        json.dumps({key: value for key, value in definition.items() if key != "Blocks"}), encoding="utf-8"
    )
    baseline = parse_survey(csv_path, baseline_definition)
    definition_path.write_text(json.dumps(definition), encoding="utf-8")

    entities = parse_survey(csv_path, definition_path)
    _assert_lineage(entities, has_flow=True)
    assert entities.sections == baseline.sections
    assert entities.questions == baseline.questions
    assert len({section["section_id"] for section in entities.sections}) == 2
    assert build_semantic_model(entities).dim_questions == build_semantic_model(baseline).dim_questions

    destination = tmp_path / format
    write_entities(entities, destination, format)
    loaded = load_entities(destination)
    _assert_lineage(loaded, has_flow=True)


@pytest.mark.parametrize("qsf_container,direct_container", [("dict", "list"), ("list", "dict")])
def test_direct_mixed_source_block_metadata_wins_at_original_position(
    tmp_path: Path, qsf_container: str, direct_container: str
) -> None:
    csv_path, definition_path, _ = _lineage_files(
        tmp_path / "input", source="qsf", container=qsf_container, flow_mode="embedded"
    )
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    block_element = next(element for element in definition["SurveyElements"] if element["Element"] == "BL")
    blocks = list(block_element["Payload"].values()) if qsf_container == "dict" else block_element["Payload"]
    if qsf_container == "dict":
        block_element["Payload"] = {str(index): block for index, block in enumerate(blocks)}
    direct_blocks = [
        {**block, "Description": "Direct first"} if block["ID"] == "BL_FIRST" else block for block in blocks
    ]
    definition["Blocks"] = (
        {str(index): block for index, block in enumerate(direct_blocks)}
        if direct_container == "dict"
        else direct_blocks
    )
    definition_path.write_text(json.dumps(definition), encoding="utf-8")

    entities = parse_survey(csv_path, definition_path)
    assert [(row["section_external_id"], row["section_name"], row["section_order"]) for row in entities.sections] == [
        ("BL_FIRST", "Direct first", 1),
        ("BL_SECOND", "Second block", 3),
    ]
    first_question = next(row for row in entities.questions if row["question_external_id"] == "QID1")
    assert first_question["block_name"] == "Direct first"
    assert first_question["block_order"] == 1


def test_fictional_feedback_qsf_list_blocks_keep_dictionary_lineage(tmp_path: Path) -> None:
    source = Path("docs/assets/examples/feedback.csv")
    original = Path("docs/assets/examples/feedback.qsf")
    document = json.loads(original.read_text(encoding="utf-8"))
    baseline = parse_survey(source, original)
    block_element = next(element for element in document["SurveyElements"] if element["Element"] == "BL")
    block_element["Payload"] = list(block_element["Payload"].values())
    list_path = tmp_path / "list-blocks.qsf"
    list_path.write_text(json.dumps(document), encoding="utf-8")

    parsed = parse_survey(source, list_path)
    assert parsed.sections == baseline.sections
    assert parsed.questions == baseline.questions
    assert build_semantic_model(parsed).dim_questions == build_semantic_model(baseline).dim_questions
