"""The published example can run from local exports without an API or provider."""

from __future__ import annotations

import csv
import json
import runpy
from pathlib import Path

import pytest

from qualtrics import load_entities


def _example():
    return runpy.run_path(str(Path(__file__).parents[2] / "examples" / "survey_workflow.py"))["run_workflow"]


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

    _example()(
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


def test_example_rejects_duplicate_ids_before_any_download(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="distinct"):
        _example()(["SV_FIRST", "SV_FIRST"], tmp_path / "output", client=object())
    assert not (tmp_path / "output").exists()
