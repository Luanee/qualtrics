"""Usage diagnostics follow resolved choice links before legacy raw aliases."""

import pytest

from qualtrics import EntitySet, analyze_entities


def _entities(raw: str, linked: str | None) -> EntitySet:
    return EntitySet(
        surveys=[{"survey_id": "s"}],
        questions=[{"survey_id": "s", "question_id": "q", "question_role": "response"}],
        question_fields=[{"survey_id": "s", "question_id": "q", "field_id": "f"}],
        responses=[{"survey_id": "s", "response_id": "r"}],
        answer_options=[
            {
                "survey_id": "s",
                "question_id": "q",
                "field_id": "f",
                "answer_option_id": "option-one",
                "answer_id": "1",
                "answer_code": "2",
                "answer_text": "One",
            },
            {
                "survey_id": "s",
                "question_id": "q",
                "field_id": "f",
                "answer_option_id": "option-two",
                "answer_id": "2",
                "answer_code": "1",
                "answer_text": "Two",
            },
        ],
        response_answers=[
            {
                "survey_id": "s",
                "question_id": "q",
                "field_id": "f",
                "response_id": "r",
                "answer_text": raw,
                "answer_option_id": linked,
            }
        ],
    )


def test_valid_option_link_does_not_mark_a_colliding_native_choice_as_used() -> None:
    analysis = analyze_entities(_entities("2", "option-one"))

    assert [option["answer_option_id"] for option in analysis.unused_options] == ["option-two"]
    assert analysis.content_answer_count == 1


@pytest.mark.parametrize("linked", [None, "stale-option"])
def test_missing_or_stale_option_links_keep_legacy_raw_label_matching(linked: str | None) -> None:
    analysis = analyze_entities(_entities("Two", linked))

    assert [option["answer_option_id"] for option in analysis.unused_options] == ["option-one"]


def test_legacy_unlinked_ambiguous_codes_keep_existing_usage_behavior() -> None:
    assert analyze_entities(_entities("2", None)).unused_options == []


def test_cross_field_option_link_does_not_mark_an_unrelated_option_as_used() -> None:
    entities = _entities("Two", "other-option")
    entities.question_fields.append({"survey_id": "s", "question_id": "q", "field_id": "other"})
    entities.answer_options.append({
        "survey_id": "s",
        "question_id": "q",
        "field_id": "other",
        "answer_option_id": "other-option",
        "answer_id": "3",
        "answer_code": "3",
        "answer_text": "Other",
    })

    assert [option["answer_option_id"] for option in analyze_entities(entities).unused_options] == [
        "option-one",
        "other-option",
    ]
