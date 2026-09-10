import json
from html.parser import HTMLParser

from qualtrics._common.models import EntitySet
from qualtrics.ui.flow import render_flow


class Markup(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def definition():
    return {
        "schema_version": 1,
        "root": {
            "node_id": "0",
            "type": "Root",
            "external_id": "FL_ROOT",
            "config": {},
            "children": [
                {"node_id": "0.0", "type": "Block", "external_id": "FL_1", "config": {"ID": "BL_1"}, "children": []},
                {
                    "node_id": "0.1",
                    "type": "Branch",
                    "external_id": "FL_2",
                    "config": {"Description": "For Sales"},
                    "children": [
                        {"node_id": "0.1.0", "type": "Block", "config": {"ID": "BL_1"}, "children": []},
                    ],
                },
                {
                    "node_id": "0.2",
                    "type": "WebService",
                    "config": {"Headers": {"Authorization": "PRIVATE_TOKEN"}},
                    "children": [],
                },
            ],
        },
        "blocks": {
            "BL_1": {
                "name": "Introduction",
                "elements": [
                    {"type": "question", "question_external_id": "QID1", "order": 1},
                    {"type": "question", "question_external_id": "QID2", "order": 2},
                ],
                "options": {},
            }
        },
        "questions": {
            "QID1": {"text": "Department", "type": "MC", "selector": "SAVR", "choices": {"1": "Sales"}},
            "QID2": {"text": "Definition-only question", "type": "TE", "choices": {}},
        },
    }


def render(data=None, targets=None):
    return render_flow(
        EntitySet(
            surveys=[
                {
                    "survey_id": "s",
                    "survey_name": "Team survey",
                    "flow_definition_json": json.dumps(data or definition()),
                }
            ]
        ),
        targets or {},
    )


def payload(source):
    return json.loads(source.split("id='flow-data' type='application/json'>", 1)[1].split("</script>", 1)[0])


def test_map_preserves_occurrences_definition_only_labels_and_question_links():
    source = render(targets={("s", "QID1"): "question-detail-1"})
    elements = Markup(source).elements
    cards = [attrs for tag, attrs in elements if tag == "details" and "flow-node" in attrs.get("class", "").split()]
    assert len(cards) == 5
    assert len({card["id"] for card in cards}) == 5
    assert {card["data-flow-node"] for card in cards} == {"0", "0.0", "0.1", "0.1.0", "0.2"}
    assert "Definition-only question" in source
    assert sum(attrs.get("href") == "#question-detail-1" for _, attrs in elements) == 2
    assert "Web service" in source
    assert "explicit assumption" in source
    assert "For Sales" in source
    assert "FL_1" in source
    assert "PRIVATE_TOKEN" not in source


def test_flow_data_and_markup_escape_script_terminators_and_attribute_content():
    data = definition()
    data["blocks"]["BL_1"]["name"] = "</script><script>alert('x')</script>"
    data["questions"]["QID1"]["text"] = "<img src=x onerror=alert(1)>"
    source = render(data, {("s", "QID1"): "question' onclick='bad"})
    assert "<img" not in source
    assert "<script>alert" not in source
    assert "onerror" in payload(source)["surveys"][0]["definition"]["questions"]["QID1"]["text"]
    assert not any("onclick" in attrs for _, attrs in Markup(source).elements)


def test_missing_invalid_and_empty_flow_have_distinct_readable_states():
    source = render_flow(
        EntitySet(
            surveys=[
                {"survey_id": "legacy", "survey_name": "Old survey"},
                {"survey_id": "broken", "flow_definition_json": "{invalid"},
                {
                    "survey_id": "empty",
                    "flow_definition_json": json.dumps({
                        "schema_version": 1,
                        "root": {"type": "Root", "node_id": "0", "children": []},
                    }),
                },
            ]
        ),
        {},
    )
    assert "No flow definition" in source
    assert "could not be read" in source
    assert "contains no steps" in source
    assert [survey["id"] for survey in payload(source)["surveys"]] == ["empty"]


def test_branch_and_randomizer_settings_are_readable_without_javascript():
    data = definition()
    data["root"]["children"][1]["config"]["BranchLogic"] = {
        "Type": "If",
        "0": {
            "Type": "BooleanExpression",
            "0": {
                "LogicType": "Question",
                "QuestionID": "QID1",
                "ChoiceLocator": "q://QID1/SelectableChoice/1",
                "Operator": "Selected",
            },
        },
    }
    data["root"]["children"].append({
        "node_id": "0.3",
        "type": "BlockRandomizer",
        "config": {"SubSet": 2, "EvenPresentation": True},
        "children": [],
    })
    source = render(data).split("<script id='flow-data'", 1)[0]
    assert "Department" in source and "Sales" in source
    assert "Select 2" in source
    assert "Even presentation" in source


def test_offline_condition_description_keeps_qualtrics_conjunctions():
    data = definition()
    first = {
        "LogicType": "Question",
        "QuestionID": "QID1",
        "ChoiceLocator": "q://QID1/SelectableChoice/1",
        "Operator": "Selected",
    }
    second = {
        "LogicType": "EmbeddedField",
        "LeftOperand": "score",
        "Operator": "GreaterThanOrEqual",
        "RightOperand": "0",
        "Conjuction": "And",
    }
    data["root"]["children"][1]["config"]["BranchLogic"] = {"Type": "If", "0": first, "1": second}
    source = render(data).split("<script id='flow-data'", 1)[0]
    assert "(Department: Sales is selected) and (score is at least 0)" in source
