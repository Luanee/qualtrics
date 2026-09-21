"""The reusable verifier checks real parser/translation contracts offline."""

from __future__ import annotations

import csv
import importlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def _export(root: Path, survey_id: str, *, archived: bool) -> None:
    folder = root / survey_id
    folder.mkdir()
    rows = [
        ["ResponseId", "UserLanguage", "QID1"],
        ["Response", "Language", "Comment"],
        [json.dumps({"ImportId": value}) for value in ("responseId", "userLanguage", "QID1")],
        [f"{survey_id}_R1", "NO", "Hei"],
    ]
    source = folder / "responses.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    if archived:
        with ZipFile(folder / "export.zip", "w", ZIP_DEFLATED) as archive:
            archive.write(source, arcname="responses.csv")
    (folder / "definition.qsf").write_text(
        json.dumps({
            "SurveyID": survey_id,
            "SurveyOptions": {"SurveyLanguage": "NO"},
            "Questions": {"QID1": {"QuestionID": "QID1", "QuestionText": "Kommentar", "QuestionType": "TE"}},
        }),
        encoding="utf-8",
    )


def test_verifier_preserves_two_survey_facts_and_builds_semantic_model(tmp_path: Path) -> None:
    assert importlib.util.find_spec("scripts.verify_translation_workflow") is not None, "smoke verifier is missing"
    verifier = importlib.import_module("scripts.verify_translation_workflow")
    _export(tmp_path, "SV_first", archived=False)
    _export(tmp_path, "SV_second", archived=True)

    summary = verifier.verify_exports(tmp_path, ("SV_first", "SV_second"), target_language="EN")
    assert summary["target_language"] == "EN"
    assert [row["survey_id"] for row in summary["surveys"]] == ["SV_first", "SV_second"]
    assert all(
        row["responses"] == row["answers"] == row["comments_original"] == row["comments_translated"] == 1
        for row in summary["surveys"]
    )
    assert all(row["localized_questions"] == 1 for row in summary["surveys"])
    assert summary["combined"] == {
        "surveys": 2,
        "responses": 2,
        "answers": 2,
        "comments": 2,
        "semantic_model_built": True,
    }
    output = tmp_path / "results" / "verification.json"
    verifier.write_summary(summary, output)
    assert json.loads(output.read_text(encoding="utf-8")) == summary


def test_verifier_rejects_missing_definition_and_duplicate_survey_ids(tmp_path: Path) -> None:
    assert importlib.util.find_spec("scripts.verify_translation_workflow") is not None, "smoke verifier is missing"
    verifier = importlib.import_module("scripts.verify_translation_workflow")
    _export(tmp_path, "SV_first", archived=False)
    import pytest

    with pytest.raises(ValueError, match="distinct"):
        verifier.verify_exports(tmp_path, ("SV_first", "SV_first"), target_language="EN")
    (tmp_path / "SV_first" / "definition.qsf").unlink()
    with pytest.raises(ValueError, match="definition.qsf"):
        verifier.verify_exports(tmp_path, ("SV_first",), target_language="EN")
