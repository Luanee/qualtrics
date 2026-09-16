"""The published example can run from local exports without an API or provider."""

from __future__ import annotations

import csv
import json
import runpy
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qualtrics import TranslationRequest, load_entities


def _module():
    return runpy.run_path(str(Path(__file__).parents[2] / "examples" / "survey_workflow.py"))


def _example():
    return _module()["run_workflow"]


def _inputs(root: Path, survey_id: str) -> None:
    folder = root / survey_id
    folder.mkdir(parents=True)
    with (folder / "responses.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "UserLanguage", "QID1"],
            ["Response", "Language", "Comment"],
            [json.dumps({"ImportId": value}) for value in ("responseId", "userLanguage", "QID1")],
            ["R1", "NO", "Hei"],
        ])
    (folder / "definition.qsf").write_text(
        json.dumps({
            "SurveyID": survey_id,
            "SurveyOptions": {"SurveyLanguage": "NO"},
            "Questions": {"QID1": {"QuestionID": "QID1", "QuestionText": "Kommentar", "QuestionType": "TE"}},
        }),
        encoding="utf-8",
    )


def test_example_combines_distinct_local_surveys_with_prepared_comments(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _inputs(source, "SV_FIRST")
    _inputs(source, "SV_SECOND")
    output = tmp_path / "output"
    requests = []

    def translate(request):
        requests.append(request)
        return f"English: {request.text}"

    result = _example()(
        ["SV_FIRST", "SV_SECOND"],
        output,
        source_root=source,
        translator=translate,
        language="EN",
        create_report=True,
    )

    first = load_entities(output / "surveys" / "SV_FIRST" / "entities")
    combined = load_entities(output / "combined" / "entities")
    assert first.comments[0]["translated_text__EN"] == "English: Hei"
    assert len(combined.surveys) == len(combined.comments) == 2
    assert len({row["response_answer_id"] for row in combined.comments}) == 2
    assert (output / "power-bi" / "fact_comments.parquet").is_file()
    assert (output / "combined" / "report.html").is_file()
    assert requests and all(request.target_language == "EN" for request in requests)
    assert result.survey_count == 2
    assert result.response_count == 2
    assert result.comment_count == 2
    assert result.combined_entities == output / "combined" / "entities"


def test_example_rejects_duplicate_ids_before_any_download(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="distinct"):
        _example()(["SV_FIRST", "SV_FIRST"], tmp_path / "output", client=object())
    assert not (tmp_path / "output").exists()


def test_example_cli_uses_typer_and_prints_a_human_readable_summary(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _inputs(source, "SV_FIRST")
    output = tmp_path / "[readable]" / "output"

    result = CliRunner().invoke(
        _module()["app"],
        ["SV_FIRST", "--from-files", str(source), "--output", str(output)],
        color=False,
    )

    assert result.exit_code == 0, result.output
    assert "Survey preparation" in result.output
    assert "Survey" in result.output
    assert "Responses" in result.output
    assert "Comments" in result.output
    assert "SV_FIRST" in result.output
    assert "1" in result.output
    assert "Output summary" in result.output
    assert str(output / "combined" / "entities") in result.output
    assert str(output / "power-bi") in result.output


def test_example_cli_reports_validation_errors_without_a_traceback(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        _module()["app"],
        ["SV_REPEAT", "SV_REPEAT", "--output", str(tmp_path / "output")],
        color=False,
    )

    assert result.exit_code == 2
    assert "Survey IDs must be distinct" in result.output
    assert "Traceback" not in result.output


def test_dynamic_translator_rejects_a_non_text_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = f"bad_adapter_{tmp_path.name.replace('-', '_')}"
    (tmp_path / f"{module_name}.py").write_text(
        "def translate(_request):\n    return 42\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    translator = _module()["_load_translator"](f"{module_name}:translate")
    request = TranslationRequest("comment", "Hei", "NO", "EN", "SV_FIRST")

    assert translator is not None
    with pytest.raises(ValueError, match="must return text"):
        translator(request)
