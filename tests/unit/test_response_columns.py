import csv
import json
from pathlib import Path

import pytest

from qualtrics import parse_survey


def export(
    folder: Path,
    columns: list[tuple[str, str]],
    values: list[str],
    *,
    questions: dict[str, dict[str, object]] | None = None,
    embedded: tuple[str, ...] = (),
    metadata: list[dict[str, object]] | None = None,
    api: bool = False,
) -> tuple[Path, Path]:
    source = folder / "responses.csv"
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows([
            [column for column, _ in columns],
            [column for column, _ in columns],
            [json.dumps(item) for item in (metadata or [{"ImportId": imported} for _, imported in columns])],
            values,
        ])
    definitions = {
        key: {"QuestionID": key, "QuestionType": "TE", "QuestionText": "A question", **value}
        for key, value in (questions or {}).items()
    }
    flow = [
        {
            "Type": "Branch",
            "Flow": [
                {
                    "Type": "EmbeddedData",
                    "EmbeddedData": [{"Field": field, "Value": "Do not fabricate this default"} for field in embedded],
                }
            ],
        }
    ]
    document = (
        {"SurveyID": "SV_TEST", "Questions": definitions, "Flow": flow}
        if api
        else {
            "SurveyEntry": {"SurveyID": "SV_TEST"},
            "SurveyElements": [
                *[{"Element": "SQ", "PrimaryAttribute": key, "Payload": value} for key, value in definitions.items()],
                {"Element": "FL", "Payload": {"Flow": flow}},
            ],
        }
    )
    definition = folder / "definition.qsf"
    definition.write_text(json.dumps(document))
    return source, definition


@pytest.mark.parametrize("shape", ["qsf", "api", "survey-flow"])
def test_embedded_and_unknown_columns_are_preserved_without_inventing_questions(tmp_path: Path, shape: str) -> None:
    paths = export(
        tmp_path,
        [
            ("ResponseId", "_recordId"),
            ("Region", "hash-region"),
            ("Country", "QID1"),
            ("Permissions", "hash-permissions"),
            ("CampaignQ123", "hash-campaign"),
            ("Blank", "Blank"),
        ],
        ["R_TEST", "North", "Example country", "001", "Control", ""],
        questions={"QID1": {"QuestionText": "Which country?"}},
        embedded=("Region", "Permissions", "NotExported"),
        api=shape != "qsf",
    )
    if shape == "survey-flow":
        document = json.loads(paths[1].read_text())
        document["SurveyFlow"] = {"Flow": document.pop("Flow"), "Type": "Root"}
        paths[1].write_text(json.dumps({"result": document}))
    entities = parse_survey(*paths)
    response = entities.responses[0]
    assert response["Region"] == "North"
    assert response["Permissions"] == "001"
    assert response["CampaignQ123"] == "Control"
    assert response["Blank"] is None
    assert "NotExported" not in response
    assert [(answer["question_external_id"], answer["answer_text"]) for answer in entities.response_answers] == [
        ("QID1", "Example country")
    ]
    dictionary = json.loads(entities.surveys[0]["source_columns_json"])
    assert [column["kind"] for column in dictionary] == [
        "system",
        "embedded",
        "question",
        "embedded",
        "unclassified",
        "unclassified",
    ]
    assert all(column["reason"] for column in dictionary)
    assert dictionary[2]["question_external_id"] == "QID1"


def test_system_import_ids_work_when_export_labels_are_renamed(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [
            ("My ID", "_recordId"),
            ("Start", "startDate"),
            ("End", "endDate"),
            ("Recorded", "recordedDate"),
            ("Channel", "distributionChannel"),
        ],
        ["R_TEST", "2026-01-01", "2026-01-02", "2026-01-03", "anonymous"],
    )
    response = parse_survey(*paths).responses[0]
    assert response["response_external_id"] == "R_TEST"
    assert response["started_at"] == "2026-01-01"
    assert response["ended_at"] == "2026-01-02"
    assert response["recorded_at"] == "2026-01-03"
    assert response["distribution_channel"] == "anonymous"


def test_duplicate_and_reserved_properties_have_lossless_storage_names(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [
            ("ResponseId", "_recordId"),
            ("Region", "hash-one"),
            ("Region", "hash-two"),
            ("region", "hash-three"),
            ("response_id", "custom-id"),
            ("status", "custom-status"),
            ("answer_numeric", "custom-number"),
        ],
        ["R_TEST", "One", "Two", "Three", "Other ID", "My status", "001"],
    )
    entities = parse_survey(*paths)
    dictionary = json.loads(entities.surveys[0]["source_columns_json"])
    response = entities.responses[0]
    property_columns = [column["storage_column"] for column in dictionary[1:]]
    assert len({name.casefold() for name in response}) == len(response)
    assert [response[name] for name in property_columns] == ["One", "Two", "Three", "Other ID", "My status", "001"]
    assert response["response_external_id"] == "R_TEST"
    assert response["status"] is None
    assert dictionary[1]["storage_column"] == "Region"
    assert dictionary[-1]["storage_column"] == "answer_numeric"


def test_technical_question_values_are_response_properties(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [
            ("ResponseId", "_recordId"),
            ("Browser", "QID1_BROWSER"),
            ("Time_First Click", "QID2_FIRST_CLICK"),
            ("NPS", "QID3"),
            ("NPS_NPS_GROUP", "QID3_NPS_GROUP"),
        ],
        ["R_TEST", "SyntheticBrowser", "1.25", "9", "Promoter"],
        questions={
            "QID1": {"QuestionType": "Meta", "Selector": "Browser"},
            "QID2": {"QuestionType": "Timing"},
            "QID3": {"QuestionType": "NPS"},
        },
    )
    entities = parse_survey(*paths)
    assert entities.responses[0]["Time_First Click"] == "1.25"
    assert entities.responses[0]["browser"] == "SyntheticBrowser"
    assert [answer["answer_text"] for answer in entities.response_answers] == ["9", "Promoter"]
    dictionary = json.loads(entities.surveys[0]["source_columns_json"])
    assert [column["kind"] for column in dictionary] == ["system", "metadata", "timing", "question", "derived"]
    assert dictionary[-1]["question_external_id"] == "QID3"


def test_explicit_question_evidence_wins_over_system_or_embedded_names(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [("ResponseId", "_recordId"), ("Country", "QID1"), ("Status", "status")],
        ["R_TEST", "Example country", "Answer to status question"],
        questions={"QID1": {}, "QID2": {}},
        embedded=("Country",),
        metadata=[{"ImportId": "_recordId"}, {"ImportId": "QID1"}, {"ImportId": "status", "questionId": "QID2"}],
    )
    entities = parse_survey(*paths)
    assert [(answer["question_external_id"], answer["answer_text"]) for answer in entities.response_answers] == [
        ("QID1", "Example country"),
        ("QID2", "Answer to status question"),
    ]
    assert entities.responses[0]["status"] is None


def test_definition_export_tags_resolve_questions_without_import_headers(tmp_path: Path) -> None:
    source, definition = export(
        tmp_path,
        [("ResponseId", "_recordId"), ("Country", "Country")],
        ["R_TEST", "Example country"],
        questions={"QID1": {"DataExportTag": "Country"}},
    )
    rows = list(csv.reader(source.open(newline="")))
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows([*rows[:2], rows[3]])
    entities = parse_survey(source, definition)
    assert entities.response_answers[0]["question_external_id"] == "QID1"
    assert entities.response_answers[0]["answer_text"] == "Example country"


def test_duplicate_question_export_labels_do_not_overwrite_answers(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [("ResponseId", "_recordId"), ("Answer", "QID1"), ("Answer", "QID2")],
        ["R_TEST", "First answer", "Second answer"],
        questions={"QID1": {}, "QID2": {}},
    )
    entities = parse_survey(*paths)
    assert [(answer["question_external_id"], answer["answer_text"]) for answer in entities.response_answers] == [
        ("QID1", "First answer"),
        ("QID2", "Second answer"),
    ]
    assert len({field["field_id"] for field in entities.question_fields}) == 2


def test_system_import_evidence_wins_over_a_question_export_tag(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [("ResponseId", "_recordId"), ("Status", "status"), ("Status", "QID1")],
        ["R_TEST", "0", "Prompted answer"],
        questions={"QID1": {"DataExportTag": "Status"}},
    )
    entities = parse_survey(*paths)
    assert entities.responses[0]["status"] == "0"
    assert [answer["answer_text"] for answer in entities.response_answers] == ["Prompted answer"]


def test_declared_embedded_field_takes_priority_over_a_question_export_tag(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [("ResponseId", "_recordId"), ("Country", "hash-country")],
        ["R_TEST", "Example country"],
        questions={"QID1": {"DataExportTag": "Country"}},
        embedded=("Country",),
    )
    entities = parse_survey(*paths)
    assert entities.responses[0]["Country"] == "Example country"
    assert entities.response_answers == []
    descriptor = json.loads(entities.surveys[0]["source_columns_json"])[1]
    assert descriptor["kind"] == "embedded"


def test_quality_and_geolocation_properties_have_explicit_evidence(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [
            ("ResponseId", "_recordId"),
            ("LocationLatitude", "locationLatitude"),
            ("Q_RecaptchaScore", "Q_RecaptchaScore"),
        ],
        ["R_TEST", "00.5", "0.9"],
    )
    entities = parse_survey(*paths)
    dictionary = json.loads(entities.surveys[0]["source_columns_json"])
    assert [item["kind"] for item in dictionary] == ["system", "system", "quality"]
    assert entities.responses[0][dictionary[1]["storage_column"]] == "00.5"


def test_duplicate_fields_avoid_colliding_with_real_suffixed_names(tmp_path: Path) -> None:
    paths = export(
        tmp_path,
        [("ResponseId", "_recordId"), ("Answer", "QID1_1"), ("Answer", "QID1_2"), ("Answer__2", "QID1_3")],
        ["R_TEST", "One", "Two", "Three"],
        questions={"QID1": {}},
    )
    entities = parse_survey(*paths)
    assert len({row["field_id"] for row in entities.question_fields}) == 3
    assert [row["answer_text"] for row in entities.response_answers] == ["One", "Two", "Three"]


@pytest.mark.parametrize("value", [None, "", "{", "null", '{"key":"value"}', "[1,null]"])
def test_read_source_columns_tolerates_absent_or_invalid_metadata(value: object) -> None:
    from qualtrics._common.models.response_columns import read_source_columns

    assert read_source_columns({"source_columns_json": value}) == []


def test_explicit_flow_override_retains_original_embedded_field_declarations(tmp_path: Path) -> None:
    source, definition = export(
        tmp_path,
        [("ResponseId", "_recordId"), ("Region", "hash-region"), ("Cohort", "hash-cohort")],
        ["R_TEST", "North", "Test"],
        embedded=("Region",),
        api=True,
    )
    document = json.loads(definition.read_text())
    document["SurveyFlow"] = {"Type": "Root", "Flow": document.pop("Flow")}
    definition.write_text(json.dumps(document))
    flow = tmp_path / "flow.json"
    flow.write_text(
        json.dumps({"Type": "Root", "Flow": [{"Type": "EmbeddedData", "EmbeddedData": [{"Field": "Cohort"}]}]})
    )
    entities = parse_survey(source, definition, flow_path=flow)
    dictionary = json.loads(entities.surveys[0]["source_columns_json"])
    assert [column["kind"] for column in dictionary] == ["system", "embedded", "embedded"]
    report_flow = json.loads(entities.surveys[0]["flow_definition_json"])
    assert report_flow["root"]["children"][0]["config"]["EmbeddedData"] == [{"Field": "Cohort"}]


def test_quality_evidence_takes_priority_over_embedded_declarations_and_ambiguous_tags(tmp_path: Path) -> None:
    source, definition = export(
        tmp_path,
        [
            ("ResponseId", "_recordId"),
            ("Q_RelevantIDFraudScore", "Q_RelevantIDFraudScore"),
            ("Country", "hash-country"),
        ],
        ["R_TEST", "001", "Example country"],
        embedded=("Q_RelevantIDFraudScore", "Country"),
        questions={"QID1": {"DataExportTag": "Country"}, "QID2": {"DataExportTag": "Country"}},
    )
    entities = parse_survey(source, definition)
    assert [row["kind"] for row in json.loads(entities.surveys[0]["source_columns_json"])] == [
        "system",
        "quality",
        "embedded",
    ]


@pytest.mark.parametrize("kind", ["choice", "matrix", "text"])
def test_export_tag_fallback_interprets_only_the_field_suffix(tmp_path: Path, kind: str) -> None:
    source_column = {"choice": "Rating_1_2", "matrix": "Rating_1_2_2", "text": "Rating_1_2_TEXT"}[kind]
    question: dict[str, object] = {
        "DataExportTag": "Rating_1",
        "QuestionType": "MC",
        "Selector": "MAVR",
        "Choices": {"1": {"Display": "One"}, "2": {"Display": "Two"}},
    }
    if kind == "matrix":
        question.update({
            "QuestionType": "Matrix",
            "Selector": "Likert",
            "SubSelector": "MultipleAnswer",
            "Answers": {"1": {"Display": "Scale one"}, "2": {"Display": "Scale two"}},
        })
    source, definition = export(
        tmp_path,
        [("ResponseId", "_recordId"), (source_column, "")],
        ["R_TEST", "Selected"],
        questions={"QID1": question},
    )
    with source.open(newline="") as handle:
        rows = list(csv.reader(handle))
    with source.open("w", newline="") as handle:
        csv.writer(handle).writerows([*rows[:2], rows[3]])
    entities = parse_survey(source, definition)
    field = entities.question_fields[0]
    answer = entities.response_answers[0]
    assert field["choice_external_id"] == "2"
    assert field["import_external_id"] is None
    assert field["field_external_id"] == source_column
    if kind == "text":
        assert field["is_text_field"] is True
        assert field["answer_value_type"] == "text"
        assert answer["answer_option_id"] is None
    else:
        assert entities.answer_options[0]["answer_external_id"] == "2"
        assert answer["answer_option_id"] == entities.answer_options[0]["answer_option_id"]
