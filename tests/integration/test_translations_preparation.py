"""Prepared labels and comments keep base analytic identities."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import pytest

import qualtrics
from qualtrics._common.models import translations as translation_model
from qualtrics._common.models.entity_set import validate_entity_set
from qualtrics._common.models.semantic import SEMANTIC_TABLE_NAMES
from qualtrics._common.parsers.localization import link_translated_answers
from qualtrics.ui.codebook import build_codebook
from qualtrics.ui.report_languages import build_report_languages


def _survey(tmp_path: Path):
    response_path = tmp_path / "responses.csv"
    with response_path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1", "QID2"],
            ["Response ID", "Language", "Choice", "Comment"],
            ["{}", "{}", json.dumps({"ImportId": "QID1"}), json.dumps({"ImportId": "QID2"})],
            ["R_NO", "NO", "1", "Norsk kommentar"],
            ["R_EN", "EN", "2", "English comment"],
            ["R_UNKNOWN", "", "Maybe", "Unknown comment"],
        ])
    definition = tmp_path / "definition.qsf"
    definition.write_text(
        json.dumps({
            "SurveyID": "SV_NORWAY",
            "SurveyOptions": {"SurveyLanguage": "NO", "AvailableLanguages": {"NO": [], "DE": []}},
            "Questions": {
                "QID1": {
                    "QuestionID": "QID1",
                    "QuestionText": "Velg ett alternativ",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "Choices": {"1": {"Display": "Ja"}, "2": {"Display": "Nei"}},
                    "Language": {"DE": {"QuestionText": "Wählen Sie", "Choices": {"1": {"Display": "Ja"}}}},
                },
                "QID2": {"QuestionID": "QID2", "QuestionText": "Kommentar", "QuestionType": "TE"},
                "QID3": {"QuestionID": "QID3", "QuestionText": "Nur Definition", "QuestionType": "TE"},
            },
        }),
        encoding="utf-8",
    )
    return qualtrics.parse_survey(response_path, definition)


def _prepare(entities, **kwargs):
    prepare = getattr(qualtrics, "prepare_translations", None)
    assert prepare is not None, "public prepare_translations is missing"
    return prepare(entities, **kwargs)


def test_translation_preparation_has_one_public_entry_point() -> None:
    assert callable(qualtrics.prepare_translations)
    assert not hasattr(qualtrics, "prepare_comment_translations")
    assert not hasattr(qualtrics, "import_comment_translations")


def test_english_target_outside_qsf_keeps_base_catalogs_and_fact_count(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    original = copy.deepcopy(source)
    requests = []

    def translate(request):
        requests.append(request)
        return f"EN:{request.kind}:{request.text}"

    prepared = _prepare(source, language="EN", translate=translate)

    assert source == original
    assert len(prepared.response_answers) == len(source.response_answers)
    assert len(prepared.comments) == len(source.comments) == 3
    assert prepared.survey_manifests["SV_NORWAY"]["languages"]["prepared_languages"] == ["EN"]
    base_questions = {row["question_external_id"]: row for row in source.questions if not row.get("is_localized")}
    english = [row for row in prepared.questions if row.get("language_code") == "EN"]
    assert len(english) == len(base_questions)
    assert all(row["is_localized"] for row in english)
    assert all(
        row["question_catalog_id"] == base_questions[row["question_external_id"]]["question_catalog_id"]
        for row in english
    )
    assert all(row["question_id"] != base_questions[row["question_external_id"]]["question_id"] for row in english)
    assert any(request.kind == "answer_option" and request.target_language == "EN" for request in requests)


def test_comment_callback_skips_known_target_and_passes_unknown_source(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    requests = []

    def translate(request):
        requests.append(request)
        return f"English: {request.text}"

    prepared = _prepare(source, language="EN", comment=translate)
    comments = {row["answer_text"]: row for row in prepared.comments}

    assert comments["English comment"]["translated_text__EN"] is None
    assert comments["Norsk kommentar"]["translated_text__EN"] == "English: Norsk kommentar"
    assert comments["Unknown comment"]["translated_text__EN"] == "English: Unknown comment"
    assert {(request.text, request.source_language) for request in requests} == {
        ("Norsk kommentar", "NO"),
        ("Unknown comment", None),
    }
    assert all(request.kind == "comment" for request in requests)


def test_respondent_language_cohorts_ignore_code_case(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    source.responses[0]["user_language"] = "en"
    source.responses[1]["user_language"] = "EN"

    report = build_report_languages(source)

    assert report["respondent_languages"].count("EN") == 1
    assert "en" not in report["respondent_languages"]
    assert report["snapshots"]["EN"]["surveys"]["SV_NORWAY"]["responses"] == 2


def test_default_target_is_survey_language_and_later_target_keeps_earlier_text(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    calls = []

    def translate(request):
        calls.append((request.text, request.source_language, request.target_language))
        return f"{request.target_language}: {request.text}"

    norwegian = _prepare(source, comment=translate)
    english = _prepare(norwegian, language="EN", comment=translate)
    comments = {row["answer_text"]: row for row in english.comments}

    assert comments["English comment"]["translated_text__NO"] == "NO: English comment"
    assert comments["English comment"]["translated_text__EN"] is None
    assert comments["Norsk kommentar"]["translated_text__NO"] is None
    assert comments["Norsk kommentar"]["translated_text__EN"] == "EN: Norsk kommentar"
    assert calls.count(("English comment", "EN", "NO")) == 1
    assert "NO" in english.survey_manifests["SV_NORWAY"]["languages"]["prepared_languages"]
    assert "EN" in english.survey_manifests["SV_NORWAY"]["languages"]["prepared_languages"]


def test_qsf_labels_win_and_specific_option_callback_fills_only_missing_choice(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    requests = []

    def option(request):
        requests.append(request)
        return "Nein"

    prepared = _prepare(source, language="DE", answer_option=option)
    question = next(
        row for row in prepared.questions if row.get("language_code") == "DE" and row["question_external_id"] == "QID1"
    )
    options = {
        row["answer_external_id"]: row
        for row in prepared.answer_options
        if row.get("language_code") == "DE" and row["question_external_id"] == "QID1"
    }

    assert question["question_text"] == "Wählen Sie"
    assert options["1"]["answer_text"] == "Ja"
    assert options["2"]["answer_text"] == "Nein"
    assert [request.text for request in requests] == ["Nei"]


def test_lowercase_qsf_language_key_is_one_display_language(tmp_path: Path) -> None:
    _survey(tmp_path)
    definition = tmp_path / "definition.qsf"
    qsf = json.loads(definition.read_text(encoding="utf-8"))
    qsf["SurveyOptions"]["AvailableLanguages"] = {"NO": [], "de": []}
    qsf["Questions"]["QID1"]["Language"] = {"de": {"QuestionText": "Wählen Sie", "Choices": {"1": {"Display": "Ja"}}}}
    definition.write_text(json.dumps(qsf), encoding="utf-8")
    source = qualtrics.parse_survey(tmp_path / "responses.csv", definition)
    prepared = _prepare(source, language="DE", question=lambda request: f"Callback: {request.text}")

    report = build_report_languages(prepared)
    assert "DE" in report["display_languages"]
    assert "de" not in report["display_languages"]
    base_question = next(
        row for row in source.questions if row["question_external_id"] == "QID1" and not row.get("is_localized")
    )
    assert report["labels"]["DE"]["questions"][base_question["question_id"]] == "Wählen Sie"
    model = qualtrics.build_semantic_model(prepared)
    assert [row["language_code"] for row in model.dim_display_languages].count("DE") == 1
    assert "de" not in [row["language_code"] for row in model.dim_display_languages]
    assert any(
        row["language_code"] == "DE" and row["question_text"] == "Wählen Sie" for row in model.dim_question_labels
    )


def test_missing_qsf_option_label_has_original_language_cue(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    base_option = next(
        row
        for row in source.answer_options
        if row["question_external_id"] == "QID1" and row["answer_external_id"] == "2" and not row.get("is_localized")
    )
    report = build_report_languages(source)

    assert report["label_fallbacks"]["DE"]["options"][base_option["answer_option_id"]] == {
        "source": "NO",
        "reason": "missing",
    }


def test_callback_generated_choice_label_cannot_resolve_response_fact(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    prepared = _prepare(
        source,
        language="EN",
        answer_option=lambda request: "Maybe" if request.text == "Ja" else "Other",
    )
    unknown = next(row for row in prepared.response_answers if row["answer_text"] == "Maybe")
    unknown["user_language"] = "EN"

    link_translated_answers(prepared)

    assert unknown["answer_option_id"] is None


def test_failed_callback_leaves_input_unchanged(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    original = copy.deepcopy(source)

    def fail(_request):
        raise RuntimeError("translation service offline")

    with pytest.raises(RuntimeError, match="translation service offline"):
        _prepare(source, language="EN", translate=fail)
    assert source == original


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_preparation_with_no_written_answers_keeps_valid_comment_schema(tmp_path: Path, format: str) -> None:
    source = _survey(tmp_path)
    source.response_answers = []
    source.comments = []

    prepared = _prepare(source, language="EN", comment=lambda request: f"English: {request.text}")

    assert prepared.comments == []
    validate_entity_set(prepared, strict=True)
    output = tmp_path / "empty_comments"
    qualtrics.write_entities(prepared, output, format=format)
    loaded = qualtrics.load_entities(output)
    assert loaded.comments == []
    assert "translated_text__EN" in loaded._present_columns["comments"]
    model = qualtrics.build_semantic_model(loaded)
    semantic = tmp_path / "empty_semantic"
    qualtrics.write_semantic_model(model, semantic, format="parquet")
    import pyarrow.parquet as pq

    names = pq.read_schema(semantic / "fact_comments.parquet").names
    assert {"translated_text__EN", "translation_source_hash__EN", "translation_is_current__EN"} <= set(names)


@pytest.mark.parametrize("format", ["json", "csv", "parquet"])
def test_prepared_target_validates_and_roundtrips(tmp_path: Path, format: str) -> None:
    source = _survey(tmp_path)
    prepared = _prepare(source, language="EN", translate=lambda request: f"English {request.text}")
    validate_entity_set(prepared, strict=True)

    folder = tmp_path / format
    qualtrics.write_entities(prepared, folder, format=format)
    loaded = qualtrics.load_entities(folder)

    assert loaded.comments == prepared.comments
    assert len(loaded.response_answers) == len(source.response_answers)
    assert loaded.survey_manifests["SV_NORWAY"]["languages"]["prepared_languages"] == ["EN"]


def test_semantic_export_uses_prepared_comment_grain_and_no_translation_fact(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    prepared = _prepare(source, language="EN", comment=lambda request: f"English: {request.text}")
    model = qualtrics.build_semantic_model(prepared)

    assert "fact_comment_translations" not in SEMANTIC_TABLE_NAMES
    assert len(model.fact_comments) == len(source.comments) == 3
    assert any(
        row["translated_text__EN"] == "English: Norsk kommentar" and row["translation_is_current__EN"] is True
        for row in model.fact_comments
    )
    display = {row["language_code"]: row for row in model.dim_display_languages}
    assert display["EN"]["is_available"] is True
    assert display["EN"]["defined_survey_count"] == 0

    output = tmp_path / "powerbi"
    qualtrics.write_semantic_model(model, output, format="parquet")
    import pyarrow.parquet as pq

    fact_comments = pq.read_table(output / "fact_comments.parquet").to_pylist()
    assert any(row["translated_text__EN"] == "English: Norsk kommentar" for row in fact_comments)
    assert not (output / "fact_comment_translations.parquet").exists()


def test_html_report_reads_comment_target_and_marks_stale_text(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    prepared = _prepare(source, language="EN", comment=lambda request: f"English: {request.text}")
    answer = next(row for row in prepared.response_answers if row["answer_text"] == "Norsk kommentar")
    output = tmp_path / "report.html"

    qualtrics.render_report(prepared, output)
    document = output.read_text(encoding="utf-8")
    payload = json.loads(
        document.split("<script id='written-translation-data' type='application/json'>", 1)[1].split("</script>", 1)[0]
    )
    assert payload[answer["response_answer_id"]]["EN"] == {"text": "English: Norsk kommentar", "current": True}

    answer["answer_text"] = "Nytt svar"
    qualtrics.render_report(prepared, output)
    document = output.read_text(encoding="utf-8")
    payload = json.loads(
        document.split("<script id='written-translation-data' type='application/json'>", 1)[1].split("</script>", 1)[0]
    )
    assert payload[answer["response_answer_id"]]["EN"] == {"text": None, "current": False}
    assert "English: Norsk kommentar" not in document


def test_stale_generated_question_label_falls_back_to_current_base(tmp_path: Path) -> None:
    source = _survey(tmp_path)
    prepared = _prepare(source, language="EN", question=lambda request: f"English: {request.text}")
    base = next(
        row for row in prepared.questions if row["question_external_id"] == "QID1" and not row.get("is_localized")
    )
    base["question_text"] = "Revised base question"

    labels = build_report_languages(prepared)["labels"]

    assert labels["EN"]["questions"][base["question_id"]] == "Revised base question"

    output = tmp_path / "stale-label-report.html"
    qualtrics.render_report(prepared, output)
    document = output.read_text(encoding="utf-8")
    payload = json.loads(
        document.split("<script id='report-language-data' type='application/json'>", 1)[1].split("</script>", 1)[0]
    )
    assert payload["stale_labels"]["EN"] >= 1
    assert payload["label_fallbacks"]["EN"]["questions"][base["question_id"]] == {
        "source": "NO",
        "reason": "out_of_date",
    }
    assert "id='display-language-note'" in document
    assert "Prepared labels are out of date" in document


def test_definition_label_freshness_is_shared_by_semantic_and_report(tmp_path: Path) -> None:
    prepared = _prepare(_survey(tmp_path), language="EN", question=lambda request: f"English: {request.text}")
    base = next(row for row in prepared.questions if row["question_external_id"] == "QID1" and not row["is_localized"])
    variant = next(
        row for row in prepared.questions if row["question_external_id"] == "QID1" and row.get("language_code") == "EN"
    )
    current_label = getattr(translation_model, "current_definition_label", None)
    assert current_label is not None, "model-layer definition label freshness helper is missing"
    assert current_label(base, variant, "question_text") is variant
    assert (
        build_report_languages(prepared)["labels"]["EN"]["questions"][base["question_id"]] == variant["question_text"]
    )

    base["question_text"] = "Updated base label"
    assert current_label(base, variant, "question_text") is base
    assert build_report_languages(prepared)["labels"]["EN"]["questions"][base["question_id"]] == "Updated base label"
    assert any(
        row["question_text"] == "Updated base label"
        for row in qualtrics.build_semantic_model(prepared).dim_question_labels
        if row["language_code"] == "EN" and row["question_external_id"] == "QID1"
    )


def test_semantic_labels_fall_back_when_callback_source_changes(tmp_path: Path) -> None:
    prepared = _prepare(_survey(tmp_path), language="EN", translate=lambda request: f"English: {request.text}")
    base_question = next(
        row for row in prepared.questions if row["question_external_id"] == "QID1" and not row.get("is_localized")
    )
    base_field = next(
        row for row in prepared.question_fields if row["question_external_id"] == "QID1" and not row.get("is_localized")
    )
    base_option = next(
        row
        for row in prepared.answer_options
        if row["question_external_id"] == "QID1" and row["answer_external_id"] == "1" and not row.get("is_localized")
    )
    base_question["question_text"] = "Revised question"
    base_field["field_text"] = "Revised field"
    base_option["answer_text"] = "Revised option"

    model = qualtrics.build_semantic_model(prepared)
    label = next(
        row
        for row in model.dim_question_labels
        if row["language_code"] == "EN" and row["question_field_id"] == base_field["question_field_id"]
    )
    option_label = next(
        row
        for row in model.dim_answer_option_labels
        if row["language_code"] == "EN" and row["answer_option_id"] == base_option["answer_option_id"]
    )
    assert label["question_text"] == "Revised question"
    assert label["field_text"] == "Revised field"
    assert option_label["answer_text"] == "Revised option"


def test_codebook_marks_stale_prepared_labels_and_shows_base_text(tmp_path: Path) -> None:
    prepared = _prepare(_survey(tmp_path), language="EN", translate=lambda request: f"English: {request.text}")
    base_question = next(
        row for row in prepared.questions if row["question_external_id"] == "QID1" and not row.get("is_localized")
    )
    base_field = next(
        row for row in prepared.question_fields if row["question_external_id"] == "QID1" and not row.get("is_localized")
    )
    base_question["question_text"] = "Revised question"
    base_field["field_text"] = "Revised field"

    localized = next(
        row for row in build_codebook(prepared) if row["question_id"] == "QID1" and row["language_code"] == "EN"
    )

    assert localized["question"] == "Revised question"
    assert localized["field"] == "Revised field"
    assert "out of date" in localized["reason"]
