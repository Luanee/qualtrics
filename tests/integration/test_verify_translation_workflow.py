"""The reusable verifier checks real parser/translation contracts offline."""

from __future__ import annotations

import csv
import importlib
import importlib.util
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from qualtrics import prepare_translations
from qualtrics._common.models.translation_columns import source_text_hash


def _export(root: Path, survey_id: str, *, archived: bool, language: str = "NO") -> None:
    folder = root / survey_id
    folder.mkdir()
    rows = [
        ["ResponseId", "UserLanguage", "QID1"],
        ["Response", "Language", "Comment"],
        [json.dumps({"ImportId": value}) for value in ("responseId", "userLanguage", "QID1")],
        [f"{survey_id}_R1", language, "Hei"],
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
    with pytest.raises(ValueError, match="distinct"):
        verifier.verify_exports(tmp_path, ("SV_first", "SV_first"), target_language="EN")
    (tmp_path / "SV_first" / "definition.qsf").unlink()
    with pytest.raises(ValueError, match="definition.qsf"):
        verifier.verify_exports(tmp_path, ("SV_first",), target_language="EN")


@pytest.mark.parametrize("broken", ["missing", "stale", "lineage"])
def test_verifier_rejects_broken_comment_preparation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, broken: str
) -> None:
    verifier = importlib.import_module("scripts.verify_translation_workflow")
    _export(tmp_path, "SV_first", archived=False)

    def broken_preparation(entities, *, language, translate):
        if broken == "missing":
            return prepare_translations(
                entities, language=language, question=translate, field=translate, answer_option=translate
            )
        prepared = prepare_translations(entities, language=language, translate=translate)
        if broken == "stale":
            prepared.comments[0]["translation_source_hash__EN"] = "0" * 64
        else:
            prepared.comments[0]["response_id"] = "wrong-response"
        return prepared

    monkeypatch.setattr(verifier, "prepare_translations", broken_preparation)
    with pytest.raises(AssertionError, match="comment"):
        verifier.verify_exports(tmp_path, ("SV_first",), target_language="EN")


def test_verifier_requires_matching_language_to_remain_original_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    verifier = importlib.import_module("scripts.verify_translation_workflow")
    _export(tmp_path, "SV_first", archived=False, language="EN")
    assert (
        verifier.verify_exports(tmp_path, ("SV_first",), target_language="EN")["surveys"][0]["comments_translated"] == 0
    )

    def invented_translation(entities, *, language, translate):
        prepared = prepare_translations(entities, language=language, translate=translate)
        prepared.comments[0]["translated_text__EN"] = "unnecessary translation"
        prepared.comments[0]["translation_source_hash__EN"] = source_text_hash("Hei")
        prepared.comments[0]["translation_source_language__EN"] = "EN"
        return prepared

    monkeypatch.setattr(verifier, "prepare_translations", invented_translation)
    with pytest.raises(AssertionError, match="comment"):
        verifier.verify_exports(tmp_path, ("SV_first",), target_language="EN")


def test_verifier_counts_encoded_regional_language_targets(tmp_path: Path) -> None:
    verifier = importlib.import_module("scripts.verify_translation_workflow")
    _export(tmp_path, "SV_first", archived=False)
    summary = verifier.verify_exports(tmp_path, ("SV_first",), target_language="PT-BR")
    assert summary["surveys"][0]["comments_translated"] == 1
