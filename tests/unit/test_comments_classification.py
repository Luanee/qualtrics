from copy import deepcopy

import pytest

from qualtrics._common.models.entities import EntitySet


@pytest.mark.parametrize(
    ("question", "field", "value", "expected"),
    [
        ({"question_type": "TE"}, {}, "0012", True),
        ({"question_type": "TE", "selector": "FORM"}, {}, "Taylor", True),
        ({"question_type": "Matrix", "selector": "TE"}, {}, "Explain", True),
        ({"question_type": "MC"}, {"is_text_field": True}, "Another choice", True),
        ({"question_type": "TE"}, {"answer_value_type": "numeric"}, "42", False),
        ({"question_type": "TE"}, {"is_comment_field": False}, "42", False),
        ({"question_type": "SBS"}, {"is_comment_field": True}, "Explain", True),
        ({"question_type": "MC"}, {}, "Friendly label", False),
        ({"question_type": "Mystery"}, {}, "Some words", False),
        ({"question_type": "TE", "selector": "Calendar"}, {}, "2026-09-12", False),
        ({"question_type": "FileUpload"}, {}, "https://example.invalid/file", False),
        ({"question_type": "TE", "question_role": "metadata"}, {}, "Chrome", False),
        ({"question_type": "Meta"}, {"is_comment_field": True}, "Chrome", False),
        ({"question_type": "Timing"}, {"is_comment_field": True}, "12", False),
        ({"question_type": "TE", "selector": "Calendar"}, {"is_text_field": True}, "2026-09-12", False),
        ({"question_type": "FileUpload"}, {"is_text_field": True}, "file.txt", False),
        ({"question_type": "Mystery"}, {"is_text_field": True}, "Words", False),
        ({"question_type": "DB"}, {"is_comment_field": True}, "Instructions", False),
        ({"question_type": "TE"}, {}, " \t\n ", False),
        ({"question_type": "TE"}, {}, "", False),
        ({"question_type": "TE"}, {}, None, False),
    ],
)
def test_comment_membership_uses_semantic_fields_not_string_values(question, field, value, expected):
    from qualtrics._common.models.comments import is_comment_answer

    assert is_comment_answer(question, field, {"answer_text": value}) is expected


def test_comment_projection_keeps_field_grain_exact_values_and_response_language():
    from qualtrics._common.models.comments import build_comments

    entities = EntitySet(
        surveys=[{"survey_id": "s", "default_language": "FR"}],
        questions=[{"survey_id": "s", "question_id": "q", "question_type": "TE"}],
        question_fields=[
            {"survey_id": "s", "question_id": "q", "question_field_id": field, "field_id": field}
            for field in ("f1", "f2")
        ],
        responses=[
            {"survey_id": "s", "response_id": "r1", "user_language": "DE-DE"},
            {"survey_id": "s", "response_id": "r2"},
        ],
        response_answers=[
            {
                "response_answer_id": answer_id,
                "survey_id": "s",
                "response_id": response_id,
                "question_id": "q",
                "question_field_id": field_id,
                "field_id": field_id,
                "answer_text": "  Same <text>\n",
                "user_language": "WRONG",
                **({"raw_value": "  Same <text>\n"} if answer_id != "a3" else {}),
            }
            for answer_id, response_id, field_id in (("a1", "r1", "f1"), ("a2", "r1", "f2"), ("a3", "r2", "f1"))
        ],
    )
    before = deepcopy(entities)

    comments = build_comments(entities)

    assert comments == [
        {
            "response_answer_id": answer_id,
            "response_id": response_id,
            "survey_id": "s",
            "question_id": "q",
            "question_field_id": field_id,
            "answer_text": "  Same <text>\n",
            "raw_value": raw_value,
            "user_language": language,
        }
        for answer_id, response_id, field_id, raw_value, language in (
            ("a1", "r1", "f1", "  Same <text>\n", "DE-DE"),
            ("a2", "r1", "f2", "  Same <text>\n", "DE-DE"),
            ("a3", "r2", "f1", None, None),
        )
    ]
    assert entities == before
    comments[0]["answer_text"] = "Changed copy"
    assert entities == before


def test_legacy_comment_field_does_not_require_optional_survey_lineage():
    from qualtrics._common.models.comments import build_comments

    entities = EntitySet(
        questions=[{"survey_id": "s", "question_id": "q", "question_type": "TE"}],
        question_fields=[{"question_id": "q", "question_field_id": "f", "answer_value_type": "text"}],
        responses=[{"survey_id": "s", "response_id": "r", "user_language": "DE"}],
        response_answers=[
            {
                "response_answer_id": "a",
                "survey_id": "s",
                "response_id": "r",
                "question_id": "q",
                "question_field_id": "f",
                "answer_text": "Legacy comment",
            }
        ],
    )

    assert build_comments(entities) == [
        {
            "response_answer_id": "a",
            "survey_id": "s",
            "response_id": "r",
            "question_id": "q",
            "question_field_id": "f",
            "answer_text": "Legacy comment",
            "raw_value": None,
            "user_language": "DE",
        }
    ]
