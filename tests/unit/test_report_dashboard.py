"""Dashboard aggregates retain survey, field, and respondent identities."""

import json

from qualtrics.analytics import analyze_entities
from qualtrics.models import EntitySet
from qualtrics.reporting.dashboard import build_dashboard


def question(survey="s", key="q", kind="MC", **values):
    return {
        "survey_id": survey,
        "question_id": key,
        "question_type": kind,
        "question_text": key,
        "question_role": "response",
        **values,
    }


def field(survey="s", key="q", name="f", **values):
    return {"survey_id": survey, "question_id": key, "field_id": name, **values}


def answer(response, value, survey="s", key="q", name="f", **values):
    return {**field(survey, key, name), "response_id": response, "answer_text": value, **values}


def response(key, survey="s", **values):
    return {"survey_id": survey, "response_id": key, **values}


def dashboard(entities):
    return build_dashboard(entities, analyze_entities(entities))


def test_recorded_dates_use_export_calendar_and_keep_missing_values_explicit():
    entities = EntitySet(
        surveys=[{"survey_id": "s", "survey_name": "Survey"}, {"survey_id": "empty"}],
        responses=[
            response("r1", recorded_at="2026-01-02T23:55:00-10:00", is_finished=True),
            response("r2", recorded_at="2026-01-02 10:00:00", is_finished="1"),
            response("r3", recorded_at="2025-12-31", is_finished=False),
            response("r4", recorded_at="2026-02-30", is_finished="false"),
            response("r5", recorded_at="2026-01-03 rubbish", is_finished=None),
            response("r6", started_at="2026-01-03"),
        ],
    )
    result = dashboard(entities)
    assert result["surveys"] == [
        {
            "id": "s",
            "label": "Survey",
            "responses": 6,
            "finished": 2,
            "dates": [["2025-12-31", 1], ["2026-01-02", 2]],
            "undated": 3,
        },
        {"id": "empty", "label": "empty", "responses": 0, "finished": 0, "dates": [], "undated": 0},
    ]
    assert result["coverage"] == result["spotlights"] == []
    assert dashboard(EntitySet()) == {"surveys": [], "coverage": [], "spotlights": []}


def test_coverage_matches_question_occurrence_order_and_never_pools_surveys():
    entities = EntitySet(
        surveys=[{"survey_id": "a"}, {"survey_id": "b"}],
        questions=[
            question("b", "q", question_text="Shared"),
            question("a", "q", question_text="Shared"),
            question("a", "missing"),
            question("a", "meta", question_role="metadata"),
        ],
        responses=[response("r", "a"), response("other", "a"), response("r", "b")],
        response_answers=[answer("r", "Yes", "a"), answer("r", "Yes", "a"), answer("r", "Yes", "b")],
    )
    assert dashboard(entities)["coverage"] == [
        {"survey": "b", "label": "Shared", "answered": 1, "total": 1, "target": "question-detail-1"},
        {"survey": "a", "label": "Shared", "answered": 1, "total": 2, "target": "question-detail-2"},
        {"survey": "a", "label": "missing", "answered": 0, "total": 2, "target": "question-detail-3"},
    ]


def test_single_choice_fields_keep_domains_and_their_actual_answered_denominators():
    entities = EntitySet(
        surveys=[{"survey_id": "s"}, {"survey_id": "other"}],
        questions=[question(), question("other")],
        question_fields=[field(field_text="First"), field(name="g", field_text="Second"), field("other")],
        answer_options=[
            {**field(), "answer_id": "1", "answer_text": "Yes"},
            {**field(name="g"), "answer_id": "1", "answer_text": "No"},
            {**field("other"), "answer_id": "1", "answer_text": "Different survey"},
        ],
        responses=[response("r1"), response("r2"), response("r1", "other")],
        response_answers=[answer("r1", "1"), answer("r2", "1", name="g"), answer("r1", "1", "other")],
    )
    spots = dashboard(entities)["spotlights"]
    assert [(row["survey"], row["field"], row["denominator"], row["bins"]) for row in spots] == [
        ("s", "First", 1, [{"label": "Yes", "count": 1}]),
        ("s", "Second", 1, [{"label": "No", "count": 1}]),
        ("other", "", 1, [{"label": "Different survey", "count": 1}]),
    ]
    assert len({row["id"] for row in spots}) == 3
    assert all(row["metric"] is None for row in spots)


def test_multiple_choice_deduplicates_selections_and_excludes_text_only_followups():
    entities = EntitySet(
        surveys=[{"survey_id": "s"}],
        questions=[question(selector="MAVR")],
        question_fields=[field(), field(name="g"), field(name="comment", is_text_field=True)],
        answer_options=[
            {**field(), "answer_id": "1", "answer_text": "A"},
            {**field(name="g"), "answer_id": "2", "answer_text": "B"},
            {**field(name="g"), "answer_id": "3", "answer_text": "Unused"},
        ],
        responses=[response("r1"), response("r2"), response("r3")],
        response_answers=[
            answer("r1", "1"),
            answer("r1", "1"),
            answer("r2", "1"),
            answer("r1", "2", name="g"),
            answer("r3", "Numeric-looking identifier 001", name="comment"),
        ],
    )
    result = dashboard(entities)
    [spot] = result["spotlights"]
    assert spot["denominator"] == 2
    assert spot["bins"] == [{"label": "A", "count": 2}, {"label": "B", "count": 1}, {"label": "Unused", "count": 0}]
    assert "once per option" in spot["note"]
    assert "more than 100%" in spot["note"]
    assert result["coverage"][0]["answered"] == 3
    assert "Numeric-looking identifier" not in json.dumps(result)


def test_numeric_fields_filter_invalid_values_and_do_not_infer_text_or_nps():
    entities = EntitySet(
        surveys=[{"survey_id": "s"}],
        questions=[
            question(key="text", kind="TE"),
            question(key="number", kind="Slider", question_text="Rating"),
            question(key="recommend", kind="MC", selector="NPS"),
            question(key="bad", kind="Slider"),
            question(key="unknown", kind="Unknown"),
        ],
        question_fields=[
            field(key="text"),
            field(key="number", field_text="Speed"),
            field(key="number", name="g", field_text="Quality"),
            field(key="number", name="comment", is_text_field=True),
        ],
        response_answers=[
            answer("r1", "001", key="text"),
            answer("r1", "1", key="number"),
            answer("r2", "3", key="number"),
            answer("r3", "nan", key="number"),
            answer("r4", "Infinity", key="number"),
            answer("r5", "invalid", key="number"),
            answer("r1", "shown label", key="number", name="g", answer_numeric=7),
            answer("r1", "900", key="number", name="comment"),
            answer("r1", "9", key="recommend"),
            answer("r1", "nan", key="bad"),
            answer("r1", "99", key="unknown"),
        ],
    )
    spots = dashboard(entities)["spotlights"]
    assert [row["kind"] for row in spots] == ["nps", "numeric", "numeric"]
    assert [row["target"] for row in spots] == ["question-detail-3", "question-detail-2", "question-detail-2"]
    assert [row["denominator"] for row in spots] == [1, 2, 1]
    assert spots[1]["bins"] == [{"label": "1", "count": 1}, {"label": "3", "count": 1}]
    assert spots[1]["metric"] == {"label": "Median", "value": "2"}
    assert spots[2]["metric"] == {"label": "Median", "value": "7"}
    assert "3 non-numeric or non-finite values excluded" in spots[1]["note"]
    assert spots[0]["metric"]["label"] != "NPS"
    serialized = json.dumps(spots, allow_nan=False)
    assert "shown label" not in serialized and '"900"' not in serialized and '"001"' not in serialized


def test_malicious_labels_are_plain_payload_data_and_unknown_categories_are_explicit():
    label = "</script><script>alert('x')</script>"
    entities = EntitySet(
        surveys=[{"survey_id": "s", "survey_name": label}],
        questions=[question(question_text=label)],
        question_fields=[field(field_text=label)],
        answer_options=[{**field(), "answer_id": "1", "answer_text": label}],
        responses=[response("r1"), response("r2")],
        response_answers=[answer("r1", "1"), answer("r2", "unlisted")],
    )
    result = dashboard(entities)
    assert result["surveys"][0]["label"] == label
    [spot] = result["spotlights"]
    assert spot["label"] == label and spot["field"] == ""
    assert spot["bins"] == [{"label": label, "count": 1}, {"label": "unlisted (unknown option)", "count": 1}]
    assert "1 respondent-option selection without a defined option" in spot["note"]
    assert label in json.dumps(result)


def test_matrix_multi_selections_group_only_the_same_statement():
    entities = EntitySet(
        surveys=[{"survey_id": "s"}],
        questions=[question(kind="Matrix")],
        question_fields=[
            field(choice_external_id="row-1", statement_text="First statement"),
            field(name="g", choice_external_id="row-1", statement_text="First statement"),
            field(name="h", choice_external_id="row-2", statement_text="Second statement"),
        ],
        answer_options=[
            {**field(), "answer_id": "1", "answer_text": "A"},
            {**field(name="g"), "answer_id": "2", "answer_text": "B"},
            {**field(name="h"), "answer_id": "1", "answer_text": "Separate"},
        ],
        response_answers=[answer("r", "1"), answer("r", "2", name="g"), answer("r", "1", name="h")],
    )
    spots = dashboard(entities)["spotlights"]
    assert [(spot["field"], spot["denominator"], spot["bins"]) for spot in spots] == [
        ("First statement", 1, [{"label": "A", "count": 1}, {"label": "B", "count": 1}]),
        ("Second statement", 1, [{"label": "Separate", "count": 1}]),
    ]
    assert "more than 100%" in spots[0]["note"]


def test_large_numeric_domains_use_complete_bins_and_stable_priority():
    entities = EntitySet(
        surveys=[{"survey_id": "s"}],
        questions=[question(kind="Slider"), question(key="bigger", kind="Slider")],
        response_answers=[answer("r", "4")] + [answer(str(i), str(i), key="bigger") for i in range(101)],
    )
    spots = dashboard(entities)["spotlights"]
    assert [spot["target"] for spot in spots] == ["question-detail-2", "question-detail-1"]
    assert len(spots[0]["bins"]) == 8
    assert sum(item["count"] for item in spots[0]["bins"]) == spots[0]["denominator"] == 101
    assert spots[0]["metric"] == {"label": "Median", "value": "50"}


def test_finite_extreme_numbers_do_not_produce_infinite_median():
    entities = EntitySet(
        surveys=[{"survey_id": "s"}],
        questions=[question(kind="Slider")],
        response_answers=[answer("a", "1e308"), answer("b", "1e308")],
    )
    [spot] = dashboard(entities)["spotlights"]
    assert float(spot["metric"]["value"].replace(",", "")) == 1e308
    assert spot["bins"] == [{"label": "1e+308", "count": 2}]
