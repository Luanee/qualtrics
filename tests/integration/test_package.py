import csv
import json
from copy import deepcopy
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from qualtrics import (
    load_entities,
    merge_entity_sets,
    parse_survey,
    parse_surveys,
    render_report,
    write_entities,
)


def test_sample_preserves_multifield_identity(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*survey_files)

    question = next(item for item in entities.questions if item.get("question_external_id") == "QID18")
    assert question["question_id"] != "QID18"
    assert question["canonical_question_type"] == "multiple_choice_single"
    field = next(item for item in entities.question_fields if item.get("question_id") == question["question_id"])
    assert field["question_external_id"] == "QID18"
    assert len(str(field["question_field_id"])) == 64
    counts = {
        qid: sum(item["question_external_id"] == qid for item in entities.question_fields)
        for qid in ("QID18", "QID30", "QID37")
    }
    assert counts == {"QID18": 10, "QID30": 6, "QID37": 5}
    assert entities.question_catalog
    assert entities.question_field_catalog
    assert entities.sections
    training = next(item for item in entities.sections if item["section_name"] == "Training")
    assert training["survey_id"] == "SV_SAMPLE"
    assert training["section_external_id"] == "BL_TRAINING"
    assert len(training["section_id"]) == 64
    for rows in vars(entities).values():
        assert all("ingestion_run_id" not in row for row in rows)
    assert len(entities.question_catalog) == len(entities.questions)
    qid18 = next(item for item in entities.questions if item["question_external_id"] == "QID18")
    assert qid18["question_text"] == "Cat"
    assert qid18["block_name"] == "Categorize faces"
    assert qid18["block_id"] == "BL_FACES"
    assert (
        next(item["question_role"] for item in entities.questions if item["question_external_id"] == "QID37")
        == "metadata"
    )
    first_response = entities.responses[0]
    assert first_response | {"response_id": "R_1", "response_external_id": "R_1"} == {
        "survey_id": "SV_SAMPLE",
        "response_id": "R_1",
        "response_external_id": "R_1",
        "started_at": "2026-01-01 10:00:00",
        "ended_at": "2026-01-01 10:00:42",
        "recorded_at": "2026-01-01 10:00:43",
        "is_finished": "True",
        "user_language": "EN",
        "status": "0",
        "ip_address": "192.0.2.1",
        "progress": "100",
        "duration_seconds": "42",
        "recipient_last_name": "Lovelace",
        "recipient_first_name": "Ada",
        "recipient_email": "ada@example.test",
        "external_reference": "EXT_1",
        "distribution_channel": "anonymous",
        "browser": "Chrome",
        "browser_version": "120",
        "operating_system": "TestOS",
        "screen_resolution": "1920x1080",
        "user_agent": "ExampleAgent/1.0",
    }
    assert not any(item["question_external_id"] == "QID37" for item in entities.response_answers)
    write_entities(entities, tmp_path, "json")
    loaded = load_entities(tmp_path)
    assert loaded.responses[0]["browser"] == "Chrome"
    render_report(loaded, tmp_path / "report.html")
    report = (tmp_path / "report.html").read_text()
    assert "<b>Browser</b>" in report
    assert "<b>User Agent</b> ExampleAgent/1.0" in report
    assert "value='QID37'" not in report
    assert not any(item["question_external_id"] == "QID37" for item in entities.answer_options)
    assert "class='question-menu' hidden" in report
    assert "No selected questions were answered in this response." in report
    assert "class='no-selected' hidden" in report
    assert "card.querySelector('.no-selected').hidden=shownAnswers>0" in report
    assert "(!term||card.dataset.search.includes(term))" in report
    assert "row.hidden=!show" in report
    assert "[hidden]{display:none!important}" in report
    assert "Block: Training" in report
    assert "class='question-meta'>Multiple choice · Block: Training" in report
    assert "position:sticky;top:.5rem" not in report
    assert "<span>PRACTICE QUESTION</span>" in report
    assert "<span class='field'>Item 1</span>" in report
    first_response = report.split("class='respondent'", 2)[1].split("</details>", 1)[0]
    assert first_response.count("::QID30'") == 1
    assert "Search responses, questions, or answers" in report
    assert "class='respondent'" in report
    assert "Expand all" in report
    assert "Overview" in report
    assert "By responses" in report
    assert "Data quality" in report
    assert "Question analytics" in report
    assert "class='question-analysis catalog-group'" in report
    assert "class='distribution-row" in report
    assert "Multiple choice" in report
    assert "class='question-choice'" in report
    assert "response-meta" in report


def test_response_answers_have_typed_values_and_option_ids(survey_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*survey_files)
    categorical = next(
        item
        for item in entities.response_answers
        if item["question_external_id"] == "QID18" and item["answer_text"] == "Robot"
    )
    assert categorical["answer_option_id"] is None
    assert categorical["answer_numeric"] is None
    assert categorical["is_selected"] is True

    from qualtrics.parsers.survey import populate_typed_answer

    option: dict[str, object] = {
        "answer_option_id": "option-1",
    }
    populate_typed_answer(categorical, {"robot": [option]})
    assert categorical["answer_option_id"] == "option-1"
    assert categorical["is_selected"] is True

    numeric = dict(categorical, answer_text="42", answer_value_type="numeric")
    populate_typed_answer(numeric, {})
    assert numeric["answer_numeric"] == 42.0
    assert numeric["answer_text"] == "42"


def test_typed_answers_do_not_guess_ambiguous_options_or_boolean_text() -> None:
    from qualtrics.parsers.survey import populate_typed_answer

    ambiguous: dict[str, object] = {"answer_text": "Same", "answer_value_type": "categorical"}
    populate_typed_answer(
        ambiguous,
        {"same": [{"answer_option_id": "one"}, {"answer_option_id": "two"}]},
    )
    assert ambiguous["answer_option_id"] is None

    free_text: dict[str, object] = {"answer_text": "true", "answer_value_type": "text"}
    populate_typed_answer(free_text, {})
    assert free_text["answer_boolean"] is None


def test_field_identity_uses_the_export_column_with_or_without_import_metadata(
    survey_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*survey_files)
    field = entities.question_fields[0]
    from qualtrics.models.identity import entity_id

    assert field["question_field_id"] == entity_id("question-field", field["question_id"], field["field_external_id"])


def test_blank_optional_response_metadata_is_null(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    source_path, definition_path = survey_files
    rows = list(csv.reader(source_path.open(encoding="utf-8", newline="")))
    optional_columns = {
        "StartDate",
        "EndDate",
        "Status",
        "IPAddress",
        "Progress",
        "Finished",
        "RecordedDate",
        "RecipientLastName",
        "RecipientFirstName",
        "RecipientEmail",
        "ExternalReference",
        "DistributionChannel",
        "UserLanguage",
        "Duration (in seconds)",
        "browser_Browser",
        "browser_Version",
        "browser_Operating System",
        "browser_Resolution",
        "browser_User Agent",
    }
    for index, column in enumerate(rows[0]):
        if column in optional_columns:
            rows[3][index] = ""
    blank_path = tmp_path / "blank-metadata.csv"
    with blank_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)

    response = parse_survey(blank_path, definition_path).responses[0]

    assert response["response_external_id"] == "R_1"
    assert response | {"response_id": "R_1"} == {
        "survey_id": "SV_SAMPLE",
        "response_id": "R_1",
        "response_external_id": "R_1",
        "started_at": None,
        "ended_at": None,
        "recorded_at": None,
        "is_finished": None,
        "user_language": None,
        "status": None,
        "ip_address": None,
        "progress": None,
        "duration_seconds": None,
        "recipient_last_name": None,
        "recipient_first_name": None,
        "recipient_email": None,
        "external_reference": None,
        "distribution_channel": None,
        "browser": None,
        "browser_version": None,
        "operating_system": None,
        "screen_resolution": None,
        "user_agent": None,
    }


def test_combined_report_has_survey_selector(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    first = parse_survey(*survey_files)
    second = deepcopy(first)
    for name in (
        "surveys",
        "questions",
        "answer_options",
        "question_fields",
        "responses",
        "response_answers",
    ):
        for row in getattr(second, name):
            row["survey_id"] = "SV_SECOND"
    second.surveys[0]["survey_name"] = "Second survey"
    combined = merge_entity_sets([first, second])
    assert len(combined.surveys) == 2
    assert len(combined.question_catalog) == len(first.question_catalog)
    assert len(combined.question_field_catalog) == len(first.question_field_catalog)
    output = tmp_path / "combined.html"
    render_report(combined, output)
    report = output.read_text()
    assert "id='survey-toggle'" in report
    assert "id='survey-menu'" in report
    assert report.count("class='survey-choice'") == 2
    assert "id='survey-select-all'" in report
    assert "id='survey-clear'" in report
    assert "Second survey" in report
    assert "data-survey='SV_SECOND'" in report
    assert "QID30" in report
    assert "surveyChoices.forEach(choice=>choice.addEventListener('change',filter))" in report
    assert "surveySelectedCount.textContent=surveys.size===surveyChoices.length?'All':" in report
    assert "function selectedSurveys(){return new Set(surveyChoices.filter(choice=>choice.checked)" in report
    assert "surveys=selectedSurveys()" in report
    assert "surveyChoices.filter(choice=>surveys.has(choice.value)).reduce" in report
    assert "count.textContent=visible+' of '+eligibleCards.length" in report
    assert "id='overview-finished'" in report
    assert "data-responses='2'" in report
    assert report.count("class='quality' data-survey=") == 2
    assert "card.hidden=!show" in report
    assert "surveyChoices.forEach(choice=>choice.checked=true)" in report
    assert "surveyChoices.forEach(choice=>choice.checked=false)" in report
    assert "<details id='question-coverage' class='panel report-section'>" in report
    assert "<details id='question-analytics' class='report-section'>" in report
    assert report.count("class='coverage-question catalog-group'") == 2
    assert report.count("class='question-analysis catalog-group'") == 2
    assert report.count("class='coverage-survey-row survey-occurrence'") == 4
    assert report.count("class='survey-analysis survey-occurrence'") == 4
    assert "<strong>Sample</strong><small>Import ID: QID30 · Section: Training</small>" in report
    assert "<strong>Second survey</strong><small>Import ID: QID30 · Section: Training</small>" in report
    assert report.count("class='occurrence-count'") == 4
    assert "new Set(visibleRows.map(row=>row.dataset.survey)).size" in report
    assert "group.hidden=visibleRows.length===0" in report
    assert "document.querySelector('#coverage-count').textContent=visibleCoverageGroups" in report
    assert "document.querySelector('#analytics-count').textContent=visibleAnalyticsGroups" in report


def test_data_quality_is_collapsible_and_groups_issues_by_question(
    tmp_path: Path,
    survey_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*survey_files)
    unused_field = next(item for item in entities.question_fields if item["question_external_id"] == "QID30")
    entities.response_answers = [
        answer for answer in entities.response_answers if answer["field_id"] != unused_field["field_id"]
    ]
    entities.answer_options.append({
        "survey_id": "SV_SAMPLE",
        "question_id": unused_field["question_id"],
        "answer_id": "unused",
        "answer_text": "Never selected",
    })

    output = tmp_path / "quality.html"
    render_report(entities, output)
    report = output.read_text(encoding="utf-8")

    assert "<details class='quality' data-survey='SV_SAMPLE'>" in report
    assert "<b>1</b> field without values" in report
    assert "<b>1</b> defined option not observed" in report
    assert "<h4>Fields without values</h4>" in report
    assert "<h4>Defined options not observed</h4>" in report
    assert ".quality-groups{display:grid;grid-template-columns:1fr;gap:.8rem}" in report
    assert "<strong>PRACTICE QUESTION</strong><small>QID30 · Section: Training</small>" in report
    assert "<li>Item 1</li>" in report
    assert "<li>Never selected</li>" in report
    assert "…and" not in report


def test_report_labels_all_text_fields_as_written_answers(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    entities = parse_survey(*survey_files)
    linked_field = next(item for item in entities.question_fields if item["question_external_id"] == "QID30")
    linked_field.update({
        "field_text": "Other (please indicate) - Text",
        "source_field_suffix": "1_TEXT",
        "is_text_field": True,
    })
    duplicate_field = next(item for item in entities.question_fields if item["question_external_id"] == "QID18")
    duplicate_field.update({
        "field_text": "Cat - Text",
        "source_field_suffix": "TEXT",
        "is_text_field": True,
    })
    entities.answer_options.append({
        "survey_id": "SV_SAMPLE",
        "question_id": linked_field["question_id"],
        "answer_id": "1",
        "answer_text": "Other (please indicate)",
    })

    output = tmp_path / "text-fields.html"
    render_report(entities, output)
    report = output.read_text(encoding="utf-8")

    assert "<div class='field-answer text-field'><span class='field'>Other (please indicate)</span>" in report
    assert "<div class='field-answer text-field'><span class='field'>Written response</span>" in report


def test_response_does_not_repeat_question_as_single_field_label(
    tmp_path: Path,
    survey_files: tuple[Path, Path],
) -> None:
    entities = parse_survey(*survey_files)
    question = next(item for item in entities.questions if item["question_external_id"] == "QID30")
    field = next(item for item in entities.question_fields if item["question_external_id"] == "QID30")
    field["field_text"] = question["question_text"]

    output = tmp_path / "response-field-label.html"
    render_report(entities, output)
    report = output.read_text(encoding="utf-8")
    response_answer = report.split("<div class='answers'>", 1)[1].split("</div></details>", 1)[0]

    assert response_answer.count(str(question["question_text"])) == 1
    assert "<div class='field-answer value-only'><span class='value'>" in response_answer
    assert ".field-answer.value-only{grid-template-columns:1fr}" in report


def test_mc_analytics_consolidates_options_and_includes_zero_counts(
    tmp_path: Path, survey_files: tuple[Path, Path]
) -> None:
    entities = parse_survey(*survey_files)
    question = next(item for item in entities.questions if item["question_external_id"] == "QID18")
    question["selector"] = "MAVR"
    entities.answer_options.extend([
        {"survey_id": "SV_SAMPLE", "question_id": question["question_id"], "answer_id": "1", "answer_text": "Robot"},
        {"survey_id": "SV_SAMPLE", "question_id": question["question_id"], "answer_id": "2", "answer_text": "Human"},
        {
            "survey_id": "SV_SAMPLE",
            "question_id": question["question_id"],
            "answer_id": "3",
            "answer_text": "Not selected",
        },
    ])

    output = tmp_path / "mc-analytics.html"
    render_report(entities, output)
    report = output.read_text(encoding="utf-8")
    analytics = report.split(
        "<details class='survey-analysis survey-occurrence' data-survey='SV_SAMPLE' data-question='QID18'>",
        1,
    )[1].split("</details>", 1)[0]

    assert analytics.count(">Robot</span>") == 1
    assert analytics.count(">Human</span>") == 1
    assert analytics.count(">Not selected</span>") == 1
    assert "<b>1</b><small>50%</small>" in analytics
    assert "<b>0</b><small>0%</small>" in analytics
    assert "Selected Choice" not in analytics


def test_parse_multiple_csv_files(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    source = survey_files[0]
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"
    first_path.write_bytes(source.read_bytes())
    second_path.write_bytes(source.read_bytes())
    entities = parse_surveys([first_path, second_path])
    assert [item["survey_id"] for item in entities.surveys] == ["first", "second"]
    assert len(entities.responses) == 4


def test_parse_survey_accepts_raw_folder_wildcard(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    source = survey_files[0]
    for survey_id in ("SV_FIRST", "SV_SECOND"):
        survey_folder = tmp_path / "run-1" / survey_id
        survey_folder.mkdir(parents=True)
        (survey_folder / f"{survey_id}.csv").write_bytes(source.read_bytes())

    entities = parse_survey(str(tmp_path / "run-1" / "*" / "*.csv"))

    assert [item["survey_id"] for item in entities.surveys] == ["SV_FIRST", "SV_SECOND"]
    assert len(entities.responses) == 4


def test_discovers_matching_qsf_beside_csv(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    csv_path = tmp_path / "automatic.csv"
    qsf_path = tmp_path / "automatic.QSF"
    csv_path.write_bytes(survey_files[0].read_bytes())
    qsf_path.write_bytes(survey_files[1].read_bytes())

    entities = parse_survey(csv_path)

    survey = entities.surveys[0]
    qid37 = next(item for item in entities.questions if item["question_external_id"] == "QID37")
    assert survey["survey_id"] == "SV_SAMPLE"
    assert qid37["question_role"] == "metadata"
    assert qid37["block_name"] == "Instructions"


def test_parse_survey_accepts_response_export_zip(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    zip_path = tmp_path / "automatic.zip"
    qsf_path = tmp_path / "automatic.qsf"
    qsf_path.write_bytes(survey_files[1].read_bytes())
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        archive.write(survey_files[0], "nested/survey responses.csv")

    entities = parse_survey(zip_path)

    assert entities.surveys[0]["survey_id"] == "SV_SAMPLE"
    assert len(entities.responses) == 2


def test_response_export_zip_requires_one_csv(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    zip_path = tmp_path / "ambiguous.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        archive.write(survey_files[0], "first.csv")
        archive.write(survey_files[0], "second.csv")

    try:
        parse_survey(zip_path)
    except ValueError as error:
        assert "exactly one CSV" in str(error)
    else:
        raise AssertionError("Expected an ambiguous response ZIP to be rejected")


def test_parse_survey_accepts_api_definition_wrapper(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    native_definition = json.loads(survey_files[1].read_text(encoding="utf-8"))
    questions = {
        element["PrimaryAttribute"]: element["Payload"]
        for element in native_definition["SurveyElements"]
        if element["Element"] == "SQ"
    }
    questions["QID30"]["Choices"] = {
        "1": {"Display": "Robot"},
        "2": {"Display": "Human"},
    }
    questions["QID18"]["Choices"] = [{"Display": "Robot"}, {"Display": "Human"}]
    questions["QID18"]["ChoiceOrder"] = ["R", "H"]
    blocks = next(element["Payload"] for element in native_definition["SurveyElements"] if element["Element"] == "BL")
    definition_path = tmp_path / "definition.qsf"
    definition_path.write_text(
        json.dumps({
            "survey_id": "SV_SAMPLE",
            "survey_name": None,
            "payload": {
                "SurveyID": "SV_SAMPLE",
                "SurveyName": "API definition survey",
                "SurveyStatus": "Active",
                "Questions": questions,
                "Blocks": blocks,
            },
        }),
        encoding="utf-8",
    )

    entities = parse_survey(survey_files[0], definition_path)

    assert entities.surveys[0]["survey_name"] == "API definition survey"
    assert len(entities.sections) == 3
    assert next(item for item in entities.questions if item["question_external_id"] == "QID30")["question_type"] == "MC"
    assert [item["answer_text"] for item in entities.answer_options if item["question_external_id"] == "QID30"] == [
        "Robot",
        "Human",
    ]
    assert [item["answer_id"] for item in entities.answer_options if item["question_external_id"] == "QID18"] == [
        "R",
        "H",
    ]
