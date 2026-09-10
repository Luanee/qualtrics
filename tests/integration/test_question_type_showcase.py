import csv
import json
from collections import defaultdict
from html.parser import HTMLParser

import pytest
from scripts.question_type_showcase import build_showcase

from qualtrics import parse_survey
from qualtrics._common.analytics import analyze_entities
from qualtrics._common.models.entity_set import validate_entity_set
from qualtrics.ui.question_presentation import render_question_analysis

FAMILIES = {
    "multiple_choice_single",
    "multiple_choice_multiple",
    "text_entry",
    "form_field",
    "calendar",
    "descriptive_text",
    "matrix",
    "slider",
    "rank_order",
    "side_by_side",
    "nps",
    "timing",
    "graphic_slider",
    "constant_sum",
    "file_upload",
    "pick_group_rank",
    "drill_down",
    "signature",
    "heat_map",
    "hot_spot",
    "metadata",
    "captcha",
    "highlight",
    "screen_capture",
    "video_response",
    "unmoderated_user_testing",
    "location_selector",
    "arcgis_map",
    "solicit_reviews",
    "tree_testing",
    "number_scale",
    "org_hierarchy",
}


@pytest.fixture(scope="module")
def showcase(tmp_path_factory):
    paths = build_showcase(tmp_path_factory.mktemp("question-types"))
    coverage = json.loads(paths["coverage"].read_text())
    return paths, coverage, parse_survey(paths["responses"], paths["survey"])


def test_showcase_is_reproducible_and_has_aligned_export_headers(showcase, tmp_path):
    paths, coverage, _ = showcase
    again = build_showcase(tmp_path / "different-folder")
    assert paths.keys() == {"survey", "responses", "coverage", "report"}
    for key, path in paths.items():
        assert path.read_bytes() == again[key].read_bytes(), key
    with paths["responses"].open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == coverage["response_count"] + 3 == 103
    assert len({len(row) for row in rows}) == 1
    assert len(rows[0]) == len(set(rows[0]))
    imports = [json.loads(item)["ImportId"] for item in rows[2]]
    assert len(imports) == len(set(imports))


def test_definition_has_consistent_question_block_flow_and_choice_references(showcase):
    paths, coverage, _ = showcase
    document = json.loads(paths["survey"].read_text())
    elements = document["SurveyElements"]
    questions = [item["Payload"] for item in elements if item["Element"] == "SQ"]
    qids = {question["QuestionID"] for question in questions}
    assert len(qids) == len(questions) == coverage["case_count"]
    assert len({question["DataExportTag"] for question in questions}) == len(questions)
    assert qids == {case["question_id"] for case in coverage["cases"]}
    blocks = next(item["Payload"] for item in elements if item["Element"] == "BL")
    block_questions = [entry["QuestionID"] for block in blocks.values() for entry in block["BlockElements"]]
    assert set(block_questions) == qids
    assert len(block_questions) == len(qids)
    flow = next(item["Payload"] for item in elements if item["Element"] == "FL")
    assert {entry["ID"] for entry in flow["Flow"]} == set(blocks)
    for question in questions:
        for values, order in (("Choices", "ChoiceOrder"), ("Answers", "AnswerOrder")):
            if values in question:
                assert set(question[values]) == set(question[order])
                assert len(question[values]) == len(question[order])
        if "RecodeValues" in question:
            assert set(question["RecodeValues"]) <= set(question.get("Choices", {})) | set(question.get("Answers", {}))


def test_manifest_matches_actual_parser_coverage_and_technical_exclusions(showcase):
    _, coverage, entities = showcase
    validate_entity_set(entities, strict=True)
    assert coverage["family_count"] == len(FAMILIES) == 32
    assert {case["canonical_type"] for case in coverage["cases"]} == FAMILIES
    questions = {question["question_external_id"]: question for question in entities.questions}
    fields = defaultdict(list)
    for field in entities.question_fields:
        fields[field["question_external_id"]].append(field)
    analysis = analyze_entities(entities)
    for case in coverage["cases"]:
        qid = case["question_id"]
        assert case["field_count"] == len(fields[qid])
        assert case["source_url"].startswith("https://www.qualtrics.com/")
        if case["canonical_type"] in {"descriptive_text", "captcha"}:
            assert qid not in questions
            assert case["presentation"] == "Definition only"
            assert case["field_count"] == 0
        else:
            question = questions[qid]
            assert question["canonical_question_type"] == case["canonical_type"]
            key = question["survey_id"], question["question_id"]
            assert (key in analysis.response_questions) == (question["question_role"] == "response")
    assert len(entities.responses) == 100
    assert all(response["browser"] for response in entities.responses)
    metadata_qids = {
        question["question_id"] for question in entities.questions if question["question_role"] == "metadata"
    }
    assert not any(answer["question_id"] in metadata_qids for answer in entities.response_answers)


def test_compound_answers_preserve_domains_and_logical_constraints(showcase):
    paths, coverage, entities = showcase
    with paths["responses"].open(newline="") as handle:
        rows = list(csv.reader(handle))
    records = [dict(zip(rows[0], row, strict=True)) for row in rows[3:]]
    assert {record["Finished"] for record in records} == {"True", "False"}
    assert any("\n" in value for record in records for value in record.values())
    assert any("ü" in value for record in records for value in record.values())
    for record in records:
        ranks = [record[f"rank_order_{index}"] for index in range(1, 4)]
        if any(ranks):
            assert sorted(map(int, ranks)) == [1, 2, 3]
        for prefix, count in (("constant_sum", 3), ("matrix_sum", 2)):
            values = [record[f"{prefix}_{index}"] for index in range(1, count + 1)]
            if any(values):
                assert sum(map(int, values)) == 100
        if record["nps"]:
            assert 0 <= int(record["nps"]) <= 10
        if record["number_scale"]:
            assert 1 <= int(record["number_scale"]) <= 7
        assert bool(record["single_other_4_TEXT"]) == (record["single_other"] == "4")
    case_qids = {case["case_id"]: case["question_id"] for case in coverage["cases"]}
    option_lookup = {option["answer_option_id"]: option for option in entities.answer_options}
    for answer in entities.response_answers:
        if answer.get("answer_option_id"):
            option = option_lookup[answer["answer_option_id"]]
            assert answer["question_field_id"] == option["question_field_id"]
    text_qid = case_qids["text_single"]
    text_answers = [answer for answer in entities.response_answers if answer["question_external_id"] == text_qid]
    assert any(answer["answer_text"].startswith("00") for answer in text_answers)
    assert all(answer["answer_numeric"] is None for answer in text_answers)
    assert analyze_entities(entities).unused_options


def test_split_selection_and_side_by_side_columns_keep_their_export_lineage(showcase):
    paths, coverage, entities = showcase
    cases = {case["case_id"]: case for case in coverage["cases"]}
    by_qid = {case["question_id"]: case for case in coverage["cases"]}
    fields = {field["question_field_id"]: field for field in entities.question_fields}
    for answer in entities.response_answers:
        case = by_qid[answer["question_external_id"]]
        field = fields[answer["question_field_id"]]
        if case["canonical_type"] == "multiple_choice_multiple" or case["case_id"] == "matrix_multiple":
            assert answer["answer_text"] == "1"
            assert answer["is_selected"] is True
            assert answer["answer_option_id"]
            assert field["choice_external_id"]
    sbs_fields = [
        field for field in fields.values() if field["question_external_id"] == cases["side_by_side"]["question_id"]
    ]
    assert {field["field_external_id"] for field in sbs_fields} == {
        f"side_by_side#{column}_{row}" for column in range(1, 4) for row in range(1, 3)
    }
    assert sorted(field["answer_value_type"] for field in sbs_fields) == [
        "categorical",
        "categorical",
        "numeric",
        "numeric",
        "text",
        "text",
    ]
    with paths["responses"].open(newline="") as handle:
        rows = list(csv.reader(handle))
    imports = {column: json.loads(info) for column, info in zip(rows[0], rows[2], strict=True)}
    for field in entities.question_fields:
        source = imports[field["field_external_id"]]
        assert field["import_external_id"] == source["ImportId"]
        if "choiceId" in source:
            assert field["choice_external_id"] == source["choiceId"]


def test_declared_presentations_are_rendered_from_actual_parsed_answers(showcase):
    paths, coverage, entities = showcase
    questions = {question["question_external_id"]: question for question in entities.questions}
    required_markup = {
        "Choice distribution": "option-analysis",
        "Matrix table": "matrix-analysis",
        "Numeric summaries": "numeric-summary",
        "Written answers": "text-analysis",
        "Generic value frequencies": "distribution-row",
        "Mixed fields": "numeric-summary",
    }
    for case in coverage["cases"]:
        if case["presentation"] not in required_markup:
            continue
        question = questions[case["question_id"]]
        qid = question["question_id"]
        fields = [field for field in entities.question_fields if field["question_id"] == qid]
        answers = [answer for answer in entities.response_answers if answer["question_id"] == qid]
        options = [option for option in entities.answer_options if option["question_id"] == qid]
        body, _, _ = render_question_analysis(
            question, fields, answers, options, {}, len({answer["response_id"] for answer in answers})
        )
        assert required_markup[case["presentation"]] in body, case["case_id"]

    class DashboardReader(HTMLParser):
        dashboard = None
        active = False

        def handle_starttag(self, tag, attrs):
            self.active = tag == "script" and dict(attrs).get("id") == "dashboard-data"

        def handle_data(self, data):
            if self.active:
                self.dashboard = json.loads(data)

        def handle_endtag(self, tag):
            if tag == "script":
                self.active = False

    document = DashboardReader()
    document.feed(paths["report"].read_text())
    assert document.dashboard is not None
    assert document.dashboard["surveys"][0]["responses"] == 100
    assert {item["kind"] for item in document.dashboard["spotlights"]} == {"nps", "numeric", "categorical"}
