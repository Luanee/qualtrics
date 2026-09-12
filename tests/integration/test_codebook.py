from __future__ import annotations

import csv
import html
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

import pytest

from qualtrics import parse_survey, render_report
from qualtrics._common.models import EntitySet


def _entities() -> EntitySet:
    return EntitySet(
        surveys=[{"survey_id": "SV_A", "survey_name": "First"}, {"survey_id": "SV_B", "survey_name": "Second"}],
        questions=[
            {
                "survey_id": sid,
                "question_id": "internal-q",
                "question_external_id": "QID1",
                "question_text": label,
                "question_type": "MC",
                "selector": "SAVR",
                "block_name": "About you",
            }
            for sid, label in [("SV_A", "Department"), ("SV_B", "Different question")]
        ],
        question_fields=[
            {
                "survey_id": sid,
                "question_id": "internal-q",
                "field_id": "internal-f",
                "field_external_id": "department",
                "import_external_id": "QID1",
                "source_column_index": 3,
                "field_text": "Department",
                "answer_value_type": "categorical",
            }
            for sid in ("SV_A", "SV_B")
        ],
        answer_options=[
            {
                "survey_id": "SV_A",
                "question_id": "internal-q",
                "field_id": "internal-f",
                "answer_id": "2",
                "answer_code": "2",
                "answer_text": "Engineering",
                "answer_order": 2,
            },
            {
                "survey_id": "SV_A",
                "question_id": "internal-q",
                "field_id": "internal-f",
                "answer_id": "1",
                "answer_code": 0,
                "answer_text": "Sales",
                "answer_order": 1,
            },
            {
                "survey_id": "SV_B",
                "question_id": "internal-q",
                "field_id": "internal-f",
                "answer_id": "1",
                "answer_code": "99",
                "answer_text": "Other",
                "answer_order": 1,
            },
        ],
    )


def test_codebook_maps_columns_and_orders_field_scoped_options() -> None:
    from qualtrics.ui.codebook import build_codebook

    rows = build_codebook(_entities())
    assert len(rows) == 2
    assert rows[0]["export_column"] == "department"
    assert rows[0]["import_id"] == "QID1"
    assert rows[0]["question_id"] == "QID1"
    assert rows[0]["question"] == "Department"
    assert rows[0]["section"] == "About you"
    assert rows[0]["choices"].startswith("0 = Sales")
    assert rows[0]["choices"].index("Sales") < rows[0]["choices"].index("Engineering")
    assert "Other" not in rows[0]["choices"]
    assert "Sales" not in rows[1]["choices"]


def test_codebook_with_no_definition_does_not_invent_choices(survey_files: tuple[Path, Path]) -> None:
    from qualtrics.ui.codebook import build_codebook

    entities = parse_survey(survey_files[0])
    rows = build_codebook(entities)
    field_columns = {str(row["field_external_id"]) for row in entities.question_fields}
    represented_fields = [row for row in rows if row["export_column"] in field_columns]
    assert len(represented_fields) == len(entities.question_fields)
    assert all(not row["choices"] for row in rows)
    assert {row["export_column"] for row in represented_fields} == field_columns


@pytest.mark.parametrize(
    ("recode", "label", "value", "expected_recode", "expected_value"),
    [
        ("0", "Sales", "0", "0", "0"),
        ("02", "Sales", "02", "02", "02"),
        (None, "Sales", "Sales", "unavailable", "Sales"),
        (None, "", "", "unavailable", '""'),
    ],
)
def test_codebook_distinguishes_choice_recode_and_normalized_values(
    recode: str | None, label: str, value: str, expected_recode: str, expected_value: str
) -> None:
    from qualtrics.ui.codebook import build_codebook

    entities = _entities()
    option = entities.answer_options[1]
    option.update({
        "source_choice_id": "1",
        "choice_value": label,
        "recode_value": recode,
        "value": value,
        "answer_text": label,
        "answer_code": recode if recode is not None else "1",
        "variable_name": "Sales export label",
        "answer_export_tag": "department-sales",
    })
    entities.answer_options = [option]

    choices = build_codebook(entities)[0]["choices"]

    assert ("label: Sales" if label else 'label: ""') in choices
    assert "native choice ID: 1" in choices
    assert f"explicit recode: {expected_recode}" in choices
    assert f"normalized value: {expected_value}" in choices
    assert "export label: Sales export label" in choices
    assert "export tag: department-sales" in choices


@pytest.mark.parametrize("empty_provenance_columns", [False, True])
def test_legacy_codebook_does_not_invent_explicit_recode_provenance(empty_provenance_columns: bool) -> None:
    from qualtrics.ui.codebook import build_codebook

    entities = _entities()
    if empty_provenance_columns:
        for option in entities.answer_options:
            option.update(dict.fromkeys(("source_choice_id", "choice_value", "recode_value", "value", "variable_name")))

    choices = build_codebook(entities)[0]["choices"]

    assert choices.startswith("0 = Sales")
    assert "choice ID: 1" in choices
    assert "explicit recode: 0" not in choices
    assert "normalized value: 0" not in choices


class _CodebookParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tr" and values.get("class") == "codebook-row":
            self.rows.append(values)


def test_codebook_escapes_html_and_embeds_valid_csv_rows() -> None:
    from qualtrics.ui.codebook import render_codebook

    entities = _entities()
    entities.questions[0]["question_text"] = '=HYPERLINK("example")\n<script>alert(1)</script>'
    entities.answer_options[0]["answer_text"] = 'Research, "Development" & design'
    rendered = render_codebook(entities)
    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    parser = _CodebookParser()
    parser.feed(rendered)
    assert len(parser.rows) == 2
    cells = next(csv.reader(StringIO(str(parser.rows[0]["data-csv"]))))
    assert any('Research, "Development" & design' in cell for cell in cells)
    assert any(cell.startswith("'=HYPERLINK") for cell in cells)
    assert html.unescape(str(parser.rows[0]["data-survey"])) == "SV_A"


def test_choice_provenance_is_escaped_and_shared_by_search_and_download() -> None:
    from qualtrics.ui.codebook import CODEBOOK_COLUMNS, build_codebook, render_codebook

    entities = _entities()
    label = 'Research, "Growth" & <script>alert(1)</script>'
    variable_name = '<b>Export "label"</b>'
    tag = '<svg onload="bad()">'
    option = entities.answer_options[1]
    option.update({
        "source_choice_id": "1",
        "choice_value": label,
        "recode_value": "02",
        "value": "02",
        "answer_text": label,
        "answer_code": "02",
        "variable_name": variable_name,
        "answer_export_tag": tag,
    })
    entities.answer_options = [option]

    rendered = render_codebook(entities)

    assert "<script>alert(1)</script>" not in rendered
    assert '<svg onload="bad()">' not in rendered
    assert variable_name not in rendered
    assert html.escape(label, quote=True) in rendered
    parser = _CodebookParser()
    parser.feed(rendered)
    choices = build_codebook(entities)[0]["choices"]
    assert "explicit recode: 02" in choices
    assert "normalized value: 02" in choices
    assert "export label: " + variable_name in choices
    assert choices.lower() in str(parser.rows[0]["data-search"])
    downloaded = next(csv.reader(StringIO(str(parser.rows[0]["data-csv"]))))
    assert downloaded[CODEBOOK_COLUMNS.index("choices")] == choices
    assert label in downloaded[CODEBOOK_COLUMNS.index("choices")]
    assert tag in downloaded[CODEBOOK_COLUMNS.index("choices")]
    assert variable_name in downloaded[CODEBOOK_COLUMNS.index("choices")]


def test_empty_codebook_is_explicit() -> None:
    from qualtrics.ui.codebook import render_codebook

    rendered = render_codebook(EntitySet())
    assert "No fields are available" in rendered


def test_report_includes_offline_codebook_controls(tmp_path: Path, survey_files: tuple[Path, Path]) -> None:
    destination = tmp_path / "report.html"
    render_report(parse_survey(*survey_files), destination)
    rendered = destination.read_text()
    assert "href='#codebook'" in rendered
    assert "id='codebook-search'" in rendered
    assert "id='codebook-download'" in rendered
    assert "data-csv=" in rendered
    assert "new Blob" in rendered
