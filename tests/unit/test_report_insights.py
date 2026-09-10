from qualtrics.ui.insights import question_highlight


def answer(response, value, field="f"):
    return {"response_id": response, "field_id": field, "answer_text": value}


def test_choice_leader_ties_and_duplicate_selections():
    q = {"question_type": "MC", "selector": "MAVR"}
    options = [{"answer_id": "1", "answer_text": "A"}, {"answer_id": "2", "answer_text": "B"}]
    rows = [answer("r1", "A"), answer("r1", "A"), answer("r2", "A"), answer("r1", "B")]
    assert question_highlight(q, [], rows, options, 2) == "Most selected: A — 2 of 2 respondents (100%)."
    rows.append(answer("r2", "B"))
    assert question_highlight(q, [], rows, options, 2) == "Tied most selected: A; B — 2 of 2 respondents each (100%)."
    assert question_highlight(q, [], [], options, 0) is None


def test_unknown_values_and_field_scope():
    q = {"question_type": "Matrix"}
    fields = [{"field_id": "f", "field_text": "First"}, {"field_id": "g", "field_text": "Second"}]
    options = [
        {"field_id": "f", "answer_id": "1", "answer_text": "Yes"},
        {"field_id": "g", "answer_id": "1", "answer_text": "No"},
    ]
    result = question_highlight(q, fields, [answer("r1", "1"), answer("r2", "unlisted", "g")], options, 2)
    assert result is not None
    assert "First: Most selected: Yes — 1 of 1 respondents" in result
    assert "Second: Most selected: unlisted (unknown option) — 1 of 1 respondents" in result


def test_numeric_types_text_identifiers_and_exclusions():
    rows = [answer("a", "001"), answer("b", "003"), answer("c", "NaN")]
    assert question_highlight({"question_type": "TE"}, [], rows, [], 3) == "3 written values from 3 respondents."
    assert (
        question_highlight({"question_type": "Slider"}, [], rows, [], 3)
        == "Median: 2 (2 numeric values; 1 non-numeric or non-finite values excluded)."
    )
    assert question_highlight({"question_type": "Slider"}, [], [answer("a", "NaN")], [], 1) is None
    assert (
        question_highlight({"question_type": "Slider"}, [{"field_id": "f", "is_text_field": True}], rows, [], 3)
        == "3 written values from 3 respondents."
    )


def test_single_choice_fields_keep_separate_domains():
    fields = [{"field_id": "f", "field_text": "First"}, {"field_id": "g", "field_text": "Second"}]
    options = [
        {"field_id": "f", "answer_id": "1", "answer_text": "A"},
        {"field_id": "g", "answer_id": "1", "answer_text": "B"},
    ]
    result = question_highlight(
        {"question_type": "MC"}, fields, [answer("r1", "1"), answer("r2", "1", "g")], options, 2
    )
    assert result is not None
    assert "First: Most selected: A — 1 of 2 respondents" in result
    assert "Second: Most selected: B — 1 of 2 respondents" in result


def test_highlights_bound_fields_and_long_ties():
    fields = [{"field_id": str(i), "field_text": f"Field {i}"} for i in range(5)]
    rows = [answer("r", "text", str(i)) for i in range(5)]
    result = question_highlight({"question_type": "TE"}, fields, rows, [], 1)
    assert result is not None
    assert "Field 2:" in result
    assert "Field 3:" not in result
    assert result.endswith("See question details for 2 more fields.")
    options = [{"answer_id": str(i), "answer_text": f"Option {i}"} for i in range(6)]
    result = question_highlight(
        {"question_type": "MC", "selector": "MAVR"}, [], [answer("r", f"Option {i}") for i in range(6)], options, 1
    )
    assert result is not None
    assert "Tied most selected (6 options): Option 0; Option 1; Option 2; and 3 others" in result
    assert "1 of 1 respondents each (100%)" in result


def test_written_choice_followup_counts_only_its_respondents():
    fields = [{"field_id": "f"}, {"field_id": "text", "is_text_field": True, "field_text": "Comment"}]
    rows = [answer("a", "Yes"), answer("b", "Yes"), answer("a", "001", "text")]
    result = question_highlight({"question_type": "MC"}, fields, rows, [{"answer_id": "1", "answer_text": "Yes"}], 2)
    assert result is not None
    assert "Comment: 1 written values from 1 respondents." in result
