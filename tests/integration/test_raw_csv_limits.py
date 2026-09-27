"""Raw survey readers preserve cells exceeding Python's default CSV limit."""

import csv
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from qualtrics import load_entities, parse_survey, write_entities


@pytest.mark.parametrize("source_kind", ["csv", "zip"])
@pytest.mark.parametrize("large_cell", ["label", "answer", "property"])
def test_large_raw_csv_cells_keep_multiline_text(tmp_path: Path, source_kind: str, large_cell: str) -> None:
    long_text = '  Café, "quoted"\r\n' + "x" * 140_000 + "\nlast line  "
    label = long_text if large_cell == "label" else "Comment"
    answer = long_text if large_cell == "answer" else 'Written, "answer"\r\nnext line'
    property_value = long_text if large_cell == "property" else "North\nWest"
    source = tmp_path / "responses.csv"
    with source.open("w", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle).writerows([
            ["ResponseId", "QID1", "Region"],
            ["Response ID", label, "Region"],
            ["{}", json.dumps({"ImportId": "QID1"}), "{}"],
            ["R1", answer, property_value],
        ])
    if source_kind == "zip":
        archive = tmp_path / "responses.zip"
        with ZipFile(archive, "w") as handle:
            handle.write(source, "responses.csv")
        source = archive
    definition = tmp_path / "definition.qsf"
    definition.write_text(
        json.dumps({
            "SurveyID": "SV_LONG_CELLS",
            "Questions": {"QID1": {"QuestionID": "QID1", "QuestionText": "Comment", "QuestionType": "TE"}},
        }),
        encoding="utf-8",
    )
    previous_limit = csv.field_size_limit()
    try:
        csv.field_size_limit(131_072)
        entities = parse_survey(source, definition)
        assert csv.field_size_limit() >= len(long_text)
        assert len(entities.responses) == len(entities.response_answers) == len(entities.comments) == 1
        assert entities.response_answers[0]["raw_value"] == answer
        assert entities.comments[0]["answer_text"] == answer
        assert entities.responses[0]["Region"] == property_value
        descriptor = entities.survey_manifests["SV_LONG_CELLS"]["source_columns_json"][1]
        assert descriptor["label"] == label
        write_entities(entities, tmp_path / "entities", "csv")
        restored = load_entities(tmp_path / "entities")
        assert restored.responses == entities.responses
        assert restored.response_answers == entities.response_answers
        assert restored.survey_manifests == entities.survey_manifests
        assert restored.comments == entities.comments
    finally:
        csv.field_size_limit(previous_limit)
