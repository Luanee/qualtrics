"""Choice metadata and original answer cells remain distinct representations."""

import csv
import json
from pathlib import Path

import pytest

from qualtrics import parse_survey


def _survey(
    folder: Path,
    values: list[str],
    question: dict[str, object] | None = None,
    *,
    import_id: str = "QID1",
) -> tuple[Path, Path | None]:
    source = folder / "responses.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1"],
            ["Response ID", "Question"],
            [json.dumps({"ImportId": "_recordId"}), json.dumps({"ImportId": import_id})],
            *[[f"R{index}", value] for index, value in enumerate(values, 1)],
        ])
    if question is None:
        return source, None
    definition = folder / "definition.qsf"
    definition.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_PROVENANCE", "SurveyName": "Provenance"},
            "SurveyElements": [
                {
                    "Element": "SQ",
                    "PrimaryAttribute": "QID1",
                    "Payload": {
                        "QuestionID": "QID1",
                        "QuestionType": "MC",
                        "Selector": "SAVR",
                        "QuestionText": "Question",
                        "Choices": {"1": {"Display": "Yes"}, "2": {"Display": "No"}},
                        **question,
                    },
                }
            ],
        })
    )
    return source, definition


def test_choice_recodes_labels_and_custom_tags_link_without_replacing_raw_values(tmp_path: Path) -> None:
    entities = parse_survey(
        *_survey(
            tmp_path,
            ["2", "Yes", "YES_TAG"],
            {"RecodeValues": {"1": "2", "2": "3"}, "ChoiceDataExportTags": {"1": "YES_TAG"}},
        )
    )
    yes = next(option for option in entities.answer_options if option["answer_id"] == "1")

    assert yes["source_choice_id"] == "1"
    assert yes["choice_value"] == "Yes"
    assert yes["recode_value"] == "2"
    assert yes["value"] == "2"
    assert (yes["answer_external_id"], yes["answer_code"], yes["answer_text"], yes["answer_export_tag"]) == (
        "1",
        "2",
        "Yes",
        "YES_TAG",
    )
    assert [answer["raw_value"] for answer in entities.response_answers] == ["2", "Yes", "YES_TAG"]
    assert [answer["answer_text"] for answer in entities.response_answers] == ["2", "Yes", "YES_TAG"]
    assert {answer["answer_option_id"] for answer in entities.response_answers} == {yes["answer_option_id"]}


@pytest.mark.parametrize(
    ("recode", "display", "expected_recode", "expected_value", "expected_code"),
    [
        (None, "<b>Yes</b>", None, "Yes", "1"),
        (0, "Yes", "0", "0", "0"),
        ("02", "Yes", "02", "02", "02"),
        (None, None, None, "", "1"),
    ],
)
def test_choice_value_fallback_distinguishes_missing_recodes_from_zero_and_empty_labels(
    tmp_path: Path,
    recode: object,
    display: object,
    expected_recode: str | None,
    expected_value: str,
    expected_code: str,
) -> None:
    question: dict[str, object] = {"Choices": {"1": {"Display": display}}}
    if recode is not None:
        question["RecodeValues"] = {"1": recode}
    option = parse_survey(*_survey(tmp_path, [expected_code], question)).answer_options[0]

    assert option["source_choice_id"] == "1"
    assert option["choice_value"] == ("Yes" if display is not None else "")
    assert option["recode_value"] == expected_recode
    assert option["value"] == expected_value
    assert option["answer_code"] == expected_code


def test_matrix_source_choice_is_scale_answer_not_statement_id(tmp_path: Path) -> None:
    entities = parse_survey(
        *_survey(
            tmp_path,
            ["0", "Low", "LOW_TAG"],
            {
                "QuestionType": "Matrix",
                "Selector": "Likert",
                "SubSelector": "SingleAnswer",
                "Choices": {"99": {"Display": "Delivery"}},
                "Answers": {"4": {"Display": "Low"}, "8": {"Display": "High"}},
                "RecodeValues": {"4": 0},
                "AnswerDataExportTags": {"4": "LOW_TAG"},
            },
            import_id="QID1_99",
        )
    )
    low = next(option for option in entities.answer_options if option["answer_id"] == "4")

    assert entities.question_fields[0]["choice_external_id"] == "99"
    assert low["source_choice_id"] == "4"
    assert low["choice_value"] == "Low"
    assert low["recode_value"] == "0"
    assert low["value"] == "0"
    assert {answer["answer_option_id"] for answer in entities.response_answers} == {low["answer_option_id"]}


def test_split_selection_keeps_its_raw_marker_and_choice_relationship(tmp_path: Path) -> None:
    entities = parse_survey(
        *_survey(
            tmp_path,
            ["Selected"],
            {"Selector": "MAVR", "RecodeValues": {"1": "02"}},
            import_id="QID1_1",
        )
    )
    answer = entities.response_answers[0]
    option = entities.answer_options[0]

    assert answer["raw_value"] == "Selected"
    assert answer["answer_text"] == "Selected"
    assert option["value"] == "02"
    assert answer["answer_option_id"] == option["answer_option_id"]


def test_duplicate_recodes_remain_unresolved_with_provenance_preserved(tmp_path: Path) -> None:
    entities = parse_survey(*_survey(tmp_path, ["02"], {"RecodeValues": {"1": "02", "2": "02"}}))

    assert [
        (option["source_choice_id"], option["recode_value"], option["value"]) for option in entities.answer_options
    ] == [
        ("1", "02", "02"),
        ("2", "02", "02"),
    ]
    assert entities.response_answers[0]["answer_option_id"] is None
    assert entities.response_answers[0]["raw_value"] == "02"


def test_no_definition_retains_every_nonempty_raw_cell_exactly(tmp_path: Path) -> None:
    values = ["  001,\nA&B\t  ", "0", "   ", ""]
    entities = parse_survey(*_survey(tmp_path, values))

    assert [answer["raw_value"] for answer in entities.response_answers] == values[:3]
    assert [answer["answer_text"] for answer in entities.response_answers] == values[:3]
    assert all(answer["answer_option_id"] is None for answer in entities.response_answers)
    assert not entities.answer_options


def test_variable_naming_labels_are_preserved_and_resolve_to_the_original_choice(tmp_path: Path) -> None:
    variable_name = "  CUSTOM & yes  "
    entities = parse_survey(
        *_survey(
            tmp_path,
            ["2", "Yes", variable_name],
            {
                "RecodeValues": {"1": "2", "2": "3"},
                "VariableNaming": {"1": variable_name},
                "ChoiceDataExportTags": True,
            },
        )
    )
    yes = next(option for option in entities.answer_options if option["source_choice_id"] == "1")
    no = next(option for option in entities.answer_options if option["source_choice_id"] == "2")

    assert yes["variable_name"] == variable_name
    assert no["variable_name"] is None
    assert yes["choice_value"] == "Yes"
    assert yes["recode_value"] == "2"
    assert yes["value"] == "2"
    assert yes["answer_export_tag"] is None
    assert [answer["raw_value"] for answer in entities.response_answers] == ["2", "Yes", variable_name]
    assert {answer["answer_option_id"] for answer in entities.response_answers} == {yes["answer_option_id"]}


def test_explicit_recode_retains_priority_over_a_conflicting_variable_name(tmp_path: Path) -> None:
    entities = parse_survey(
        *_survey(
            tmp_path,
            ["2"],
            {"RecodeValues": {"1": "2"}, "VariableNaming": {"2": "2"}},
        )
    )
    yes = next(option for option in entities.answer_options if option["source_choice_id"] == "1")

    assert yes["variable_name"] is None
    assert entities.response_answers[0]["answer_option_id"] == yes["answer_option_id"]


def test_matrix_statement_variable_names_are_not_assigned_to_scale_answers(tmp_path: Path) -> None:
    entities = parse_survey(
        *_survey(
            tmp_path,
            ["DeliveryAlias"],
            {
                "QuestionType": "Matrix",
                "Selector": "Likert",
                "SubSelector": "SingleAnswer",
                "Choices": {"4": {"Display": "Delivery"}},
                "Answers": {"4": {"Display": "Low"}, "8": {"Display": "High"}},
                "VariableNaming": {"4": "DeliveryAlias"},
            },
            import_id="QID1_4",
        )
    )

    assert all(option["variable_name"] is None for option in entities.answer_options)
    assert entities.response_answers[0]["answer_option_id"] is None
