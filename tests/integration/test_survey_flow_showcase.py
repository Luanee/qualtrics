import json


def test_flow_showcase_uses_production_parser_and_reproducible_routes(tmp_path):
    from scripts.survey_flow_showcase import build_showcase

    first = build_showcase(tmp_path / "first")
    second = build_showcase(tmp_path / "second")
    for key in ("survey", "responses", "flow"):
        assert first[key].read_bytes() == second[key].read_bytes()
    from qualtrics import parse_survey

    entities = parse_survey(first["responses"], first["survey"])
    definition = json.loads(entities.surveys[0]["flow_definition_json"])
    assert len(entities.responses) == 24
    assert definition["questions"]["QID1"]["choices"]["1"] == "Sales"
    assert definition["questions"]["QID1"]["choices"]["2"] == "Engineering"
    assert "Welcome to our fictional team survey" in definition["questions"]["QID_INTRO"]["text"]
    assert not any(question["question_external_id"] == "QID_INTRO" for question in entities.questions)

    def node_types(node):
        return {node["type"]} | {kind for child in node["children"] for kind in node_types(child)}

    assert node_types(definition["root"]) >= {"Branch", "BlockRandomizer", "EmbeddedData", "EndSurvey", "WebService"}
    report = first["report"].read_text()
    assert "id='survey-flow'" in report
    assert "Sales follow-up" in report
    assert "Engineering follow-up" in report
    assert "window.QualtricsFlowEngine" in report or "QualtricsFlowEngine" in report
