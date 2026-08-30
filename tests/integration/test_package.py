from copy import deepcopy
from pathlib import Path

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
    counts = {
        qid: sum(item["question_id"] == qid for item in entities.question_fields) for qid in ("QID18", "QID30", "QID37")
    }
    assert counts == {"QID18": 10, "QID30": 6, "QID37": 4}
    assert entities.question_catalog
    assert entities.question_field_catalog
    assert entities.sections
    training = next(item for item in entities.sections if item["section_name"] == "Training")
    assert training == {
        "survey_id": "SV_SAMPLE",
        "section_id": "BL_TRAINING",
        "section_name": "Training",
        "section_type": "Standard",
        "section_order": 1,
    }
    for rows in vars(entities).values():
        assert all("ingestion_run_id" not in row for row in rows)
    assert len(entities.question_catalog) == len(entities.questions)
    qid18 = next(item for item in entities.questions if item["question_id"] == "QID18")
    assert qid18["question_text"] == "Cat"
    assert qid18["block_name"] == "Categorize faces"
    assert qid18["block_id"] == "BL_FACES"
    assert next(item["question_role"] for item in entities.questions if item["question_id"] == "QID37") == "metadata"
    assert any(
        item["question_id"] == "QID37" and item["field_id"] == "browser_Browser" for item in entities.response_answers
    )
    write_entities(entities, tmp_path, "json")
    loaded = load_entities(tmp_path)
    render_report(loaded, tmp_path / "report.html")
    report = (tmp_path / "report.html").read_text()
    assert "<b>Browser</b>" in report
    assert "value='QID37'" not in report
    assert not any(item["question_id"] == "QID37" for item in entities.answer_options)
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
    assert "class='question-analysis'" in report
    assert "class='distribution-row'" in report
    assert "Multiple choice" in report
    assert "class='question-choice'" in report
    assert "response-meta" in report


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
    assert "id='survey-select'" in report
    assert "Second survey" in report
    assert "data-survey='SV_SECOND'" in report
    assert "SV_SECOND::QID30" in report
    assert "surveySelect.addEventListener('change',filter)" in report
    assert "count.textContent=visible+' of '+eligibleCards.length" in report
    assert "id='overview-finished'" in report
    assert "data-responses='2'" in report
    assert report.count("class='quality' data-survey=") == 2
    assert "card.hidden=!show" in report
    assert "visibleChoices().forEach(c=>c.checked=true)" in report
    assert "visibleChoices().forEach(c=>c.checked=false)" in report


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
    qid37 = next(item for item in entities.questions if item["question_id"] == "QID37")
    assert survey["survey_id"] == "SV_SAMPLE"
    assert qid37["question_role"] == "metadata"
    assert qid37["block_name"] == "Instructions"
