from qualtrics.reporting.components.primitives import empty_state, metric, page_heading, pagination, search_control


def test_heading_and_controls_escape_labels_and_attributes():
    assert "<script>" not in page_heading("<script>", "A & B", heading_id="x' autofocus='")
    assert "A &amp; B" in page_heading("Title", "A & B")
    control = search_control("x'", "<Search>", placeholder='"quoted"')
    assert "for='x&#x27;'" in control
    assert "&lt;Search&gt;" in control
    assert "&quot;quoted&quot;" in control


def test_empty_state_and_pagination_keep_controller_contract():
    assert (
        empty_state("written-empty", "Nothing <here>", hidden=True)
        == "<p id='written-empty' hidden>Nothing &lt;here&gt;</p>"
    )
    assert " hidden" not in empty_state("empty", "Nothing")
    assert pagination("written-pagination") == "<div id='written-pagination' class='pagination'></div>"
    assert (
        metric("stat-responses", 1234, "Responses")
        == "<div class='stat'><strong id='stat-responses'>1,234</strong><span>Responses</span></div>"
    )


def test_disclosure_heading_preserves_summary_and_escapes_count():
    markup = page_heading("Questions", "Compare <surveys>", disclosure=True, count="<2>", count_id="count'")
    assert markup.startswith("<summary class='section-summary'>")
    assert "<small>Compare &lt;surveys&gt;</small>" in markup
    assert "id='count&#x27;' class='section-count'>&lt;2&gt;" in markup
    assert markup.endswith("</summary>")


def test_navigation_registers_every_page_with_one_current_view():
    from qualtrics.reporting.components.navigation import render_navigation

    markup = render_navigation()
    for view in ("overview", "survey-flow", "question-analytics", "written-answers", "by-responses", "codebook"):
        assert f"data-view='{view}' href='#{view}'" in markup
    assert markup.count("aria-current='page'") == 1
    assert markup.count("class='nav-icon'") == 6
    assert markup.count("aria-hidden='true'") == 6


def test_scope_controls_keep_survey_specific_tokens_and_escape_hostile_names():
    from qualtrics.models.entities import EntitySet
    from qualtrics.reporting.components.controls import render_question_choices, render_survey_choices
    from qualtrics.reporting.context import ReportContext

    entities = EntitySet(
        surveys=[{"survey_id": "s'", "survey_name": "<Survey>"}],
        questions=[
            {"survey_id": "s'", "question_id": "q", "question_external_id": 'Q"1', "question_text": "<Question>"}
        ],
        responses=[{"survey_id": "s'", "response_id": "r"}],
        question_fields=[{"survey_id": "s'", "question_id": "q", "field_id": "f"}],
        response_answers=[
            {"survey_id": "s'", "question_id": "q", "field_id": "f", "response_id": "r", "answer_text": "answer"}
        ],
    )
    context = ReportContext.build(entities)
    surveys = render_survey_choices(context)
    questions = render_question_choices(context)
    assert "value='s&#x27;'" in surveys
    assert "data-responses='1'" in surveys
    assert "&lt;Survey&gt;" in surveys
    assert "value='s&#x27;::Q&quot;1'" in questions
    assert "&lt;Question&gt;" in questions
    assert "<small>1/1</small>" in questions
