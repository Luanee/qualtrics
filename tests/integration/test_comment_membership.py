import csv
import json
from pathlib import Path

import pytest

from qualtrics import parse_survey, render_report


def _parse(tmp_path: Path, definition: dict, fields: list[tuple[str, str, str]], values: list[str]):
    source = tmp_path / "comments.csv"
    qsf = tmp_path / "comments.qsf"
    with source.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", *(field[0] for field in fields)],
            ["Response ID", "Language", *(field[1] for field in fields)],
            ["{}", "{}", *(json.dumps({"ImportId": field[2]}) for field in fields)],
            ["R1", "DE", *values],
        ])
    qsf.write_text(
        json.dumps({
            "SurveyEntry": {"SurveyID": "SV_COMMENTS", "SurveyName": "Comments"},
            "Questions": {"QID1": {"QuestionID": "QID1", "QuestionText": "Question", **definition}},
        }),
        encoding="utf-8",
    )
    return parse_survey(source, qsf)


def test_numeric_validation_excludes_comments_without_retyping_original_answers(tmp_path):
    entities = _parse(
        tmp_path,
        {"QuestionType": "TE", "Selector": "SL", "Validation": {"Settings": {"ContentType": "ValidNumber"}}},
        [("QID1_TEXT", "Question", "QID1_TEXT")],
        [" 0012 "],
    )

    assert entities.question_fields[0].get("is_comment_field") is False
    assert entities.question_fields[0]["answer_value_type"] == "text"
    assert entities.response_answers[0]["answer_text"] == " 0012 "
    assert entities.response_answers[0]["raw_value"] == " 0012 "
    assert entities.response_answers[0]["answer_numeric"] is None
    assert entities.comments == []


@pytest.mark.parametrize("looped", [False, True])
@pytest.mark.parametrize(("question_type", "selector"), [("TE", "FORM"), ("MC", "MAVR"), ("Matrix", "TE")])
def test_choice_validation_uses_field_suffix_without_changing_loop_identities(
    tmp_path, looped, question_type, selector
):
    definition = {
        "QuestionType": question_type,
        "Selector": selector,
        "Choices": {"1": {"Display": "Name", "TextEntry": True}, "2": {"Display": "Count", "TextEntry": True}},
    }
    names = ["2_QID1_1", "1_QID1_2"] if looped else ["QID1_1", "QID1_2"]
    if question_type == "MC":
        names = [name + "_TEXT" for name in names]
    fields = [(name, label, name) for name, label in zip(names, ["Name", "Count"], strict=True)]
    baseline = _parse(tmp_path, definition, fields, ["Taylor", "12"])
    if question_type == "MC":
        validation = {
            "Choices": {
                "1": definition["Choices"]["1"],
                "2": {
                    **definition["Choices"]["2"],
                    "TextEntryValidation": {"Settings": {"ContentType": "ValidNumber"}},
                },
            }
        }
    else:
        validation = {"Validation": {"Settings": {"SubValidation": {"2": {"ContentType": "ValidNumber"}}}}}
    validated = _parse(
        tmp_path,
        {**definition, **validation},
        fields,
        ["Taylor", "12"],
    )

    assert [row["answer_text"] for row in validated.comments] == ["Taylor"]
    assert [row["is_comment_field"] for row in validated.question_fields] == [True, False]
    assert [row["choice_external_id"] for row in validated.question_fields] == (["2", "1"] if looped else ["1", "2"])
    catalog_keys = {"question_catalog_id", "question_field_catalog_id"} if question_type == "MC" else set()
    assert [
        {key: value for key, value in row.items() if key not in catalog_keys} for row in validated.response_answers
    ] == [{key: value for key, value in row.items() if key not in catalog_keys} for row in baseline.response_answers]
    if question_type != "MC":
        # Existing MC identity includes choice-validation metadata, while form
        # and matrix SubValidation is outside its identity contract.
        assert validated.question_catalog == baseline.question_catalog
        assert validated.question_field_catalog == baseline.question_field_catalog
    assert [
        {key: value for key, value in row.items() if key not in catalog_keys | {"is_comment_field"}}
        for row in validated.question_fields
    ] == [
        {key: value for key, value in row.items() if key not in catalog_keys | {"is_comment_field"}}
        for row in baseline.question_fields
    ]


def test_csv_only_explicit_text_suffix_remains_a_comment(tmp_path):
    source = tmp_path / "csv-only.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1_TEXT", "QID2"],
            ["Response ID", "Explanation", "Unknown"],
            ["{}", json.dumps({"ImportId": "QID1_TEXT"}), json.dumps({"ImportId": "QID2"})],
            ["R1", "CSV explanation", "Unknown value"],
        ])
    entities = parse_survey(source)

    assert [row["answer_text"] for row in entities.comments] == ["CSV explanation"]
    assert [row["is_comment_field"] for row in entities.question_fields] == [True, False]


def test_prefix_only_choice_imports_keep_their_validation_scope(tmp_path):
    entities = _parse(
        tmp_path,
        {
            "QuestionType": "MC",
            "Selector": "MAVR",
            "Choices": {
                "1": {"Display": "Other explanation", "TextEntry": True},
                "2": {
                    "Display": "Other count",
                    "TextEntry": True,
                    "TextEntryValidation": {"Settings": {"ContentType": "ValidNumber"}},
                },
            },
        },
        [("free", "Other explanation", "1_QID1_TEXT"), ("count", "Other count", "2_QID1_TEXT")],
        ["An explanation", "12"],
    )

    assert [row["answer_text"] for row in entities.comments] == ["An explanation"]
    assert [row["choice_external_id"] for row in entities.question_fields] == ["1", "2"]


@pytest.mark.parametrize(
    "definition",
    [
        {"QuestionType": "TE", "Selector": "Calendar"},
        {"QuestionType": "FileUpload"},
        {"QuestionType": "Mystery"},
        {"QuestionType": "Slider"},
    ],
)
def test_explicit_nontext_question_types_override_text_suffix_for_comments(tmp_path, definition):
    entities = _parse(tmp_path, definition, [("QID1_TEXT", "Question", "QID1_TEXT")], ["Exported value"])

    assert entities.comments == []
    assert entities.question_fields[0]["is_comment_field"] is False
    assert entities.question_fields[0]["answer_value_type"] == "text"
    assert entities.response_answers[0]["answer_text"] == "Exported value"


@pytest.mark.parametrize(
    ("definition", "fields", "values", "expected"),
    [
        ({"QuestionType": "TE", "Selector": "SL"}, [("QID1_TEXT", "Code", "QID1_TEXT")], ["0012"], ["0012"]),
        (
            {
                "QuestionType": "TE",
                "Selector": "FORM",
                "Choices": {"1": {"Display": "Name"}, "2": {"Display": "Count"}},
                "Validation": {"Settings": {"SubValidation": {"2": {"ContentType": "ValidNumber"}}}},
            },
            [("QID1_1", "Name", "QID1_1"), ("QID1_2", "Count", "QID1_2")],
            ["Taylor", "12"],
            ["Taylor"],
        ),
        (
            {"QuestionType": "Matrix", "Selector": "TE", "Choices": {"1": {"Display": "Service"}}},
            [("QID1_1", "Service", "QID1_1")],
            ["Helpful"],
            ["Helpful"],
        ),
        (
            {"QuestionType": "MC", "Selector": "SAVR", "Choices": {"1": {"Display": "Other", "TextEntry": True}}},
            [("QID1", "Question", "QID1"), ("QID1_1_TEXT", "Other text", "QID1_1_TEXT")],
            ["1", "Another option"],
            ["Another option"],
        ),
        ({"QuestionType": "TE"}, [("QID1", "Question", "QID1")], [" \t\n "], []),
    ],
)
def test_parser_projects_only_nonblank_comment_fields(tmp_path, definition, fields, values, expected):
    entities = _parse(tmp_path, definition, fields, values)

    assert [row["answer_text"] for row in entities.comments] == expected
    assert [row["answer_text"] for row in entities.response_answers] == values
    assert all(row["user_language"] == "DE" for row in entities.comments)
    output = tmp_path / "report.html"
    render_report(entities, output)
    assert output.read_text(encoding="utf-8").count("class='written-answer'") == len(expected)


def test_sbs_comments_follow_mapped_column_definitions_without_label_inference(tmp_path):
    entities = _parse(
        tmp_path,
        {
            "QuestionType": "SBS",
            "Choices": {"1": {"Display": "Service"}},
            "AdditionalQuestions": {
                "1": {"QuestionType": "MC", "Selector": "SAVR", "QuestionText": "Open options"},
                "2": {"QuestionType": "TE", "Selector": "SL", "QuestionText": "Reason"},
                "3": {"QuestionType": "TE", "Validation": {"Settings": {"ContentType": "ValidNumber"}}},
            },
        },
        [
            ("QID1#1_1", "Open options", "QID1#1_1"),
            ("QID1#2_1", "Reason", "QID1#2_1"),
            ("QID1#3_1", "Open number", "QID1#3_1"),
            ("QID1#9_1", "Open comments", "QID1#9_1"),
        ],
        ["Choice label", "Actual explanation", "42", "Unknown column"],
    )

    assert [row.get("is_comment_field") for row in entities.question_fields] == [False, True, False, False]
    assert [row["answer_text"] for row in entities.comments] == ["Actual explanation"]
    # New comment evidence must not change existing parser types or answer rows.
    assert [row["answer_value_type"] for row in entities.question_fields] == ["text", "categorical", "text", "text"]
    assert len(entities.response_answers) == 4
    output = tmp_path / "report.html"
    render_report(entities, output)
    document = output.read_text(encoding="utf-8")
    assert "class='written-value'>Actual explanation</p>" in document
    assert "class='written-value'>Choice label</p>" not in document
    assert "class='written-value'>42</p>" not in document
    assert "class='written-value'>Unknown column</p>" not in document
    assert "id='written-2'" not in document


def test_sbs_text_companions_use_supported_mapped_columns_and_validation(tmp_path):
    entities = _parse(
        tmp_path,
        {
            "QuestionType": "SBS",
            "Choices": {"1": {"Display": "Service"}},
            "AdditionalQuestions": {
                "1": {"QuestionType": "MC", "Selector": "SAVR"},
                "2": {
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Validation": {"Settings": {"ContentType": "ValidNumber"}},
                },
                "3": {"QuestionType": "FileUpload"},
                "4": {
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {
                        "2": {
                            "Display": "Other count",
                            "TextEntry": True,
                            "TextEntryValidation": {"Settings": {"ContentType": "ValidNumber"}},
                        }
                    },
                },
            },
        },
        [
            ("QID1#1_1_TEXT", "Other", "QID1#1_1_TEXT"),
            ("QID1#2_1_TEXT", "Other number", "QID1#2_1_TEXT"),
            ("QID1#3_1_TEXT", "File name", "QID1#3_1_TEXT"),
            ("QID1#9_1_TEXT", "Unmapped", "QID1#9_1_TEXT"),
            ("QID1#4_1_TEXT", "Other count", "QID1#4_1_TEXT"),
        ],
        ["Custom choice", "42", "file.txt", "Unknown", "18"],
    )

    assert [row.get("is_comment_field") for row in entities.question_fields] == [True, False, False, False, False]
    assert [row["answer_text"] for row in entities.comments] == ["Custom choice"]
