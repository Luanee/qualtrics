from __future__ import annotations

import json

import pytest

from qualtrics._common.parsers.flow import extract_flow_definition


def _questions() -> dict[str, object]:
    return {
        "QID1": {
            "QuestionID": "QID1",
            "QuestionText": "<b>Department</b>",
            "QuestionType": "MC",
            "Selector": "SAVR",
            "Choices": {"2": {"Display": "Engineering"}, "1": {"Display": "Sales"}},
            "ChoiceOrder": ["1", "2"],
            "DisplayLogic": {"0": {"Type": "BooleanExpression"}},
        },
        "QID_ONLY": {
            "QuestionID": "QID_ONLY",
            "QuestionText": "Definition <i>only</i>",
            "QuestionType": "TE",
            "Selector": "SL",
            "SkipLogic": [{"SkipTo": "ENDOFSURVEY"}],
        },
    }


def _blocks() -> dict[str, object]:
    return {
        "BL_1": {
            "ID": "BL_1",
            "Description": "Introduction",
            "Type": "Standard",
            "BlockElements": [
                {"Type": "Question", "QuestionID": "QID1"},
                {"Type": "Question", "QuestionID": "QID_ONLY", "SkipLogic": {"x": 1}},
            ],
            "Options": {
                "Looping": True,
                "RandomizeQuestions": "Advanced",
                "Unsafe": "discard",
            },
        }
    }


def _root() -> dict[str, object]:
    return {
        "Type": "Root",
        "FlowID": "FL_1",
        "UnsafeRootOption": "discard",
        "Flow": [
            {"Type": "Block", "ID": "BL_1", "FlowID": "FL_2", "Description": "First"},
            {
                "Type": "Branch",
                "FlowID": "FL_3",
                "BranchLogic": {"0": {"0": {"QuestionID": "QID1", "Operator": "Selected"}}},
                "Flow": [
                    {
                        "Type": "Randomizer",
                        "FlowID": "FL_4",
                        "SubSet": 1,
                        "EvenPresentation": True,
                        "Flow": [
                            {"Type": "Block", "ID": "BL_1", "FlowID": "FL_5"},
                            {
                                "Type": "EmbeddedData",
                                "FlowID": "FL_6",
                                "EmbeddedData": [
                                    {
                                        "Field": "segment",
                                        "Value": "sales",
                                        "Type": "Custom",
                                        "Description": "Segment",
                                        "Secret": "discard",
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            {"Type": "WebService", "FlowID": "FL_7", "URL": "https://secret.invalid", "Headers": {"x": "y"}},
        ],
    }


def _qsf() -> dict[str, object]:
    return {
        "SurveyElements": [
            *(
                {"Element": "SQ", "PrimaryAttribute": qid, "Payload": question}
                for qid, question in _questions().items()
            ),
            {"Element": "BL", "Payload": _blocks()},
            {"Element": "FL", "PrimaryAttribute": "FL_1", "Payload": _root()},
        ]
    }


def test_qsf_extracts_ordered_safe_flow_with_distinct_occurrences() -> None:
    definition = extract_flow_definition(_qsf())

    assert definition is not None
    assert definition["schema_version"] == 1
    assert definition["source_format"] == "qsf"
    assert definition["root"] == {
        "node_id": "0",
        "external_id": "FL_1",
        "type": "Root",
        "config": {},
        "children": [
            {
                "node_id": "0.0",
                "external_id": "FL_2",
                "type": "Block",
                "config": {"ID": "BL_1", "Description": "First"},
                "children": [],
            },
            {
                "node_id": "0.1",
                "external_id": "FL_3",
                "type": "Branch",
                "config": {"BranchLogic": {"0": {"0": {"QuestionID": "QID1", "Operator": "Selected"}}}},
                "children": [
                    {
                        "node_id": "0.1.0",
                        "external_id": "FL_4",
                        "type": "Randomizer",
                        "config": {"SubSet": 1, "EvenPresentation": True},
                        "children": [
                            {
                                "node_id": "0.1.0.0",
                                "external_id": "FL_5",
                                "type": "Block",
                                "config": {"ID": "BL_1"},
                                "children": [],
                            },
                            {
                                "node_id": "0.1.0.1",
                                "external_id": "FL_6",
                                "type": "EmbeddedData",
                                "config": {
                                    "EmbeddedData": [
                                        {
                                            "Field": "segment",
                                            "Value": "sales",
                                            "Type": "Custom",
                                            "Description": "Segment",
                                        }
                                    ]
                                },
                                "children": [],
                            },
                        ],
                    }
                ],
            },
            {
                "node_id": "0.2",
                "external_id": "FL_7",
                "type": "WebService",
                "config": {},
                "children": [],
            },
        ],
    }
    assert definition["blocks"] == {
        "BL_1": {
            "name": "Introduction",
            "type": "Standard",
            "elements": [
                {"type": "question", "question_external_id": "QID1", "order": 1},
                {"type": "question", "question_external_id": "QID_ONLY", "order": 2},
            ],
            "options": {"Looping": True, "RandomizeQuestions": "Advanced", "skip_logic": True},
        }
    }
    assert definition["questions"] == {
        "QID1": {
            "text": "Department",
            "type": "MC",
            "selector": "SAVR",
            "choices": {"2": "Engineering", "1": "Sales"},
            "choice_order": ["1", "2"],
            "display_logic": True,
            "skip_logic": False,
        },
        "QID_ONLY": {
            "text": "Definition only",
            "type": "TE",
            "selector": "SL",
            "choices": {},
            "choice_order": [],
            "display_logic": False,
            "skip_logic": True,
        },
    }
    serialized = json.dumps(definition)
    assert "Unsafe" not in serialized
    assert "https://secret.invalid" not in serialized
    assert "Secret" not in serialized


def test_qsf_direct_api_and_survey_definition_wrappers_converge() -> None:
    qsf = extract_flow_definition(_qsf())
    direct = extract_flow_definition({"Flow": _root(), "Blocks": list(_blocks().values()), "Questions": _questions()})
    wrapped = extract_flow_definition({
        "SurveyDefinition": {"Flow": _root(), "Blocks": _blocks(), "Questions": _questions()}
    })
    result_wrapped = extract_flow_definition({
        "result": {"SurveyDefinition": {"Flow": _root(), "Blocks": _blocks(), "Questions": _questions()}}
    })

    assert qsf is not None
    assert direct is not None
    assert wrapped is not None
    assert result_wrapped is not None
    assert qsf["source_format"] == "qsf"
    assert direct["source_format"] == "survey_definition"
    assert wrapped["source_format"] == "survey_definition"
    assert result_wrapped["source_format"] == "survey_definition"
    assert {key: value for key, value in direct.items() if key != "source_format"} == {
        key: value for key, value in qsf.items() if key != "source_format"
    }
    assert wrapped == result_wrapped


def test_raw_flow_uses_flow_provenance() -> None:
    definition = extract_flow_definition({"result": _root()})

    assert definition is not None
    assert definition["source_format"] == "flow"


def test_absent_flow_is_unavailable_but_explicit_empty_flow_is_preserved() -> None:
    assert extract_flow_definition({"Blocks": _blocks(), "Questions": _questions()}) is None
    empty = extract_flow_definition({"Flow": [], "Blocks": _blocks(), "Questions": _questions()})
    assert empty is not None
    assert empty["root"] == {"node_id": "0", "external_id": None, "type": "Root", "config": {}, "children": []}


def test_direct_api_standard_container_is_normalized_to_root_scope() -> None:
    definition = extract_flow_definition({
        "result": {
            "Type": "Standard",
            "FlowID": "FL_API_ROOT",
            "Flow": [{"Type": "BlockRandomizer", "FlowID": "FL_CHILD", "SubSet": 1, "Flow": []}],
        }
    })

    assert definition is not None
    assert definition["root"]["type"] == "Root"
    assert definition["root"]["external_id"] == "FL_API_ROOT"
    assert definition["root"]["children"][0]["type"] == "BlockRandomizer"
    assert definition["root"]["children"][0]["node_id"] == "0.0"


def test_top_level_branch_is_preserved_as_a_child_of_root_scope() -> None:
    logic = {"LogicType": "Quota", "QuotaID": "QO_1"}
    definition = extract_flow_definition({
        "Type": "Branch",
        "FlowID": "FL_BRANCH",
        "BranchLogic": logic,
        "Flow": [{"Type": "EndSurvey", "FlowID": "FL_END"}],
    })

    assert definition is not None
    branch = definition["root"]["children"][0]
    assert branch["type"] == "Branch"
    assert branch["config"]["BranchLogic"] == logic
    assert branch["children"][0]["type"] == "EndSurvey"


@pytest.mark.parametrize("invalid", [{"Flow": "bad"}, {"Flow": {"Type": "Root", "Flow": {}}}])
def test_invalid_flow_shapes_raise_a_clear_error(invalid: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="flow"):
        extract_flow_definition(invalid)
