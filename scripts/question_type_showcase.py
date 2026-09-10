"""Generate the entirely fictional, reproducible documentation report showcase.

This QSF-shaped coverage fixture is not an import-tested Qualtrics survey. Its
advanced fields demonstrate the toolkit's generic fallbacks, not platform assets
or every possible licensed question configuration. All source data is invented.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from qualtrics import parse_survey, render_report
from qualtrics._common.models.entity_set import validate_entity_set
from qualtrics._common.models.question_types import resolve_question_type

QUESTION_GUIDE = (
    "https://www.qualtrics.com/support/survey-platform/survey-module/editing-questions/question-types-guide/"
)
OVERVIEW = QUESTION_GUIDE + "question-types-overview/"
MATRIX_GUIDE = QUESTION_GUIDE + "standard-content/matrix-table/"
SBS_GUIDE = QUESTION_GUIDE + "standard-content/side-by-side/"
SURVEY_ID = "SV_SYNTHETIC_QUESTION_TYPES"
RESPONSE_COUNT = 100


@dataclass(frozen=True)
class ExportField:
    suffix: str = ""
    label: str = ""
    choice_id: str = ""
    answer_id: str = ""
    separator: str = "_"


@dataclass(frozen=True)
class QuestionCase:
    case_id: str
    label: str
    question_type: str
    canonical_type: str
    presentation: str
    fields: tuple[ExportField, ...] = (ExportField(),)
    # Each tuple is a coherent response to the whole question. Sampling whole
    # rows preserves rank uniqueness, sums and dependent selection/text fields.
    rows: tuple[tuple[str, ...], ...] = ()
    selector: str = ""
    sub_selector: str = ""
    choices: tuple[str, ...] = ()
    answers: tuple[str, ...] = ()
    limitations: str = ""
    source_url: str = OVERVIEW


def _single_rows(*values: str) -> tuple[tuple[str, ...], ...]:
    return tuple((value,) for value in values)


def _item_fields(*labels: str) -> tuple[ExportField, ...]:
    return tuple(ExportField(str(index), label, str(index)) for index, label in enumerate(labels, start=1))


def _cases() -> list[QuestionCase]:
    """Enumerate meaningful variants explicitly; this is not a selector registry."""
    cases = [
        QuestionCase(
            "introduction",
            "Welcome to the fictional community workspace survey",
            "DB",
            "descriptive_text",
            "Definition only",
            fields=(),
            limitations="Display content has no answer column and is absent from the parsed report and codebook.",
        ),
    ]
    for selector, label in (
        ("SAVR", "vertical choices"),
        ("SAHR", "horizontal choices"),
        ("SACOL", "choice columns"),
        ("Dropdown", "dropdown"),
        ("SelectBox", "select box"),
    ):
        cases.append(
            QuestionCase(
                f"single_{selector.lower()}",
                f"Which team are you part of? ({label})",
                "MC",
                "multiple_choice_single",
                "Choice distribution",
                selector=selector,
                sub_selector="TX",
                choices=("Engineering", "Sales", "Operations", "Prefer not to say"),
                rows=_single_rows("1", "1", "1", "2", "2", "3"),
                limitations="Repeated layouts are separate example questions. The final option is deliberately unused.",
            )
        )
    cases.append(
        QuestionCase(
            "single_other",
            "Where do you usually work?",
            "MC",
            "multiple_choice_single",
            "Choice distribution",
            fields=(ExportField(), ExportField("4_TEXT", "Other - Text", "4")),
            selector="SAVR",
            sub_selector="TX",
            choices=("Main office", "Home", "Shared studio", "Other"),
            rows=(("1", ""), ("1", ""), ("2", ""), ("3", ""), ("4", "Community library")),
            limitations="Other text is a separate field and appears only when Other is selected.",
        )
    )
    for selector, label in (("MAVR", "vertical"), ("MAHR", "horizontal"), ("MACOL", "columns"), ("MABox", "box")):
        choices = ("Quiet desks", "Meeting rooms", "Coffee area", "Games room")
        cases.append(
            QuestionCase(
                f"multiple_{selector.lower()}",
                f"Which facilities did you use? ({label})",
                "MC",
                "multiple_choice_multiple",
                "Choice distribution",
                fields=_item_fields(*choices),
                selector=selector,
                sub_selector="TX",
                choices=choices,
                rows=(("1", "1", "", ""), ("1", "", "1", ""), ("1", "1", "1", ""), ("", "1", "", "")),
                limitations=(
                    "Split option columns use 1 for selected and blank for unselected; Games room stays unused."
                ),
            )
        )
    cases.extend([
        QuestionCase(
            "text_single",
            "What is your fictional desk code?",
            "TE",
            "text_entry",
            "Written answers",
            selector="SL",
            fields=(ExportField("TEXT"),),
            rows=_single_rows("0012", "0042", "0091"),
            limitations="Numeric-looking identifiers remain text, preserving leading zeros.",
        ),
        QuestionCase(
            "text_multi",
            "What would improve your workspace?",
            "TE",
            "text_entry",
            "Written answers",
            selector="ML",
            fields=(ExportField("TEXT"),),
            rows=_single_rows(
                "More quiet desks would help.",
                "A room-booking guide, please.\nExamples would save time.",
                "A gemütlich reading corner would be lovely.",
                "Keep the friendly welcome — thank you!",
            ),
            limitations="Includes optional blanks, Unicode, punctuation and a multiline CSV value.",
        ),
        QuestionCase(
            "text_essay",
            "Describe a good day in this fictional workspace",
            "TE",
            "text_entry",
            "Written answers",
            selector="ESTB",
            fields=(ExportField("TEXT"),),
            rows=_single_rows(
                "I found a quiet desk, finished a draft, then shared ideas with a teammate over coffee.",
                "A morning workshop was followed by focused work. A clearer booking page would help next time.",
            ),
        ),
        QuestionCase(
            "form",
            "Describe your ideal work area",
            "TE",
            "form_field",
            "Written answers",
            selector="FORM",
            fields=_item_fields("Area name", "Desk code", "Useful feature"),
            choices=("Area name", "Desk code", "Useful feature"),
            rows=(("North nook", "0017", "Natural light"), ("Garden studio", "0049", "Whiteboard")),
            limitations="One text field per form item; no personal contact details are generated.",
        ),
        QuestionCase(
            "calendar",
            "Which date would suit a team workshop?",
            "TE",
            "calendar",
            "Generic value frequencies",
            selector="Calendar",
            rows=_single_rows("2026-04-14", "2026-04-21", "2026-05-05"),
            limitations="Date strings are retained; this question has no calendar chart.",
        ),
        QuestionCase(
            "matrix_single",
            "How satisfied are you with each facility?",
            "Matrix",
            "matrix",
            "Matrix table",
            selector="Likert",
            sub_selector="SingleAnswer",
            fields=_item_fields("Quiet desks", "Meeting rooms"),
            choices=("Quiet desks", "Meeting rooms"),
            answers=("Needs improvement", "Fine", "Excellent"),
            rows=(("3", "3"), ("3", "2"), ("2", "2"), ("2", "1"), ("1", "2")),
            source_url=MATRIX_GUIDE,
        ),
        QuestionCase(
            "matrix_multiple",
            "Which features matter in each work area?",
            "Matrix",
            "matrix",
            "Matrix table",
            selector="Likert",
            sub_selector="MultipleAnswer",
            choices=("Quiet desks", "Meeting rooms"),
            answers=("Natural light", "Power sockets", "Whiteboard"),
            fields=tuple(
                ExportField(f"{row}_{answer}", f"{row_label} - {answer_label}", str(row), str(answer))
                for row, row_label in enumerate(("Quiet desks", "Meeting rooms"), start=1)
                for answer, answer_label in enumerate(("Natural light", "Power sockets", "Whiteboard"), start=1)
            ),
            rows=(("1", "1", "", "", "1", "1"), ("", "1", "", "1", "1", "1")),
            limitations="One exported column per statement/option cell; selections can total more than 100%.",
            source_url=MATRIX_GUIDE,
        ),
        QuestionCase(
            "matrix_sum",
            "Allocate 100 improvement points between these work areas",
            "Matrix",
            "matrix",
            "Numeric summaries",
            selector="CS",
            fields=_item_fields("Quiet desks", "Meeting rooms"),
            choices=("Quiet desks", "Meeting rooms"),
            rows=(("60", "40"), ("35", "65"), ("50", "50")),
            limitations="Numeric columns sum to 100 per answered question; shown as field summaries.",
            source_url=MATRIX_GUIDE,
        ),
        QuestionCase(
            "matrix_text",
            "Suggest one change for each work area",
            "Matrix",
            "matrix",
            "Written answers",
            selector="TE",
            fields=_item_fields("Quiet desks", "Meeting rooms"),
            choices=("Quiet desks", "Meeting rooms"),
            rows=(("Adjustable lamps", "More whiteboards"), ("Quieter chairs", "Clearer room labels")),
            source_url=MATRIX_GUIDE,
        ),
        QuestionCase(
            "slider",
            "Rate comfort and convenience from 1 to 5",
            "Slider",
            "slider",
            "Numeric summaries",
            selector="HSLIDER",
            fields=_item_fields("Comfort", "Convenience"),
            choices=("Comfort", "Convenience"),
            rows=(("5", "4"), ("4", "4"), ("4", "3"), ("3", "3"), ("2", "1")),
        ),
        QuestionCase(
            "rank_order",
            "Rank the next three workspace improvements",
            "RO",
            "rank_order",
            "Numeric summaries",
            selector="DND",
            fields=_item_fields("Quiet desks", "Booking tools", "Social space"),
            choices=("Quiet desks", "Booking tools", "Social space"),
            rows=(("1", "2", "3"), ("2", "1", "3"), ("1", "3", "2")),
            limitations="Ranks form a permutation of 1–3; the report summarizes each item's numeric rank.",
        ),
        QuestionCase(
            "side_by_side",
            "Assess each work area: preference, visits and suggestion",
            "SBS",
            "side_by_side",
            "Mixed fields",
            choices=("Quiet desks", "Meeting rooms"),
            fields=(
                ExportField("1_1", "Quiet desks - Preference", "1", separator="#"),
                ExportField("1_2", "Meeting rooms - Preference", "2", separator="#"),
                ExportField("2_1", "Quiet desks - Number of visits", "1", separator="#"),
                ExportField("2_2", "Meeting rooms - Number of visits", "2", separator="#"),
                ExportField("3_1", "Quiet desks - Open text", "1", separator="#"),
                ExportField("3_2", "Meeting rooms - Open text", "2", separator="#"),
            ),
            rows=(
                ("Preferred", "Useful", "4", "2", "Add lamps", "More whiteboards"),
                ("Useful", "Preferred", "2", "5", "Quieter chairs", "Better booking"),
            ),
            limitations="Mixed columns use field-label/type heuristics. Nested SBS choice domains are not resolved.",
            source_url=SBS_GUIDE,
        ),
        QuestionCase(
            "nps",
            "How likely are you to recommend this fictional workspace?",
            "MC",
            "nps",
            "Numeric summaries",
            selector="NPS",
            choices=tuple(str(score) for score in range(11)),
            rows=_single_rows(*(str(score) for score in (10, 10, 9, 9, 9, 8, 8, 7, 6, 5, 4, 3, 2, 1, 0))),
            limitations="Scores range from 0 to 10. The Summary dashboard includes an NPS spotlight.",
        ),
        QuestionCase(
            "timing",
            "Workspace section timing (technical)",
            "Timing",
            "timing",
            "Technical timing",
            fields=tuple(
                ExportField(suffix, label)
                for suffix, label in (
                    ("FIRST_CLICK", "First click"),
                    ("LAST_CLICK", "Last click"),
                    ("PAGE_SUBMIT", "Page submit"),
                    ("CLICK_COUNT", "Click count"),
                )
            ),
            rows=(("1.5", "14.2", "17.0", "4"), ("2.0", "25.0", "28.5", "7")),
            limitations="Retained as technical fields and excluded from respondent question charts and totals.",
        ),
        QuestionCase(
            "graphic_slider",
            "Rate the workspace mood from 1 to 5",
            "GraphicSlider",
            "graphic_slider",
            "Numeric summaries",
            rows=_single_rows("5", "4", "4", "3", "2", "1"),
            limitations="Only numeric exports are illustrated; no licensed graphic assets are included.",
        ),
        QuestionCase(
            "constant_sum",
            "Allocate 100 points to the next investment",
            "CS",
            "constant_sum",
            "Numeric summaries",
            selector="VRTL",
            fields=_item_fields("Furniture", "Booking tools", "Lighting"),
            choices=("Furniture", "Booking tools", "Lighting"),
            rows=(("45", "35", "20"), ("20", "50", "30"), ("30", "30", "40")),
            limitations="Each answered allocation sums to 100; field summaries do not imply separate budgets.",
        ),
        QuestionCase(
            "file_upload",
            "Attach a fictional workspace sketch",
            "FileUpload",
            "file_upload",
            "Generic value frequencies",
            fields=(ExportField("FILE_NAME", "File name"),),
            rows=_single_rows("example-desk-layout.pdf", "example-room-sketch.png"),
            limitations="Filenames only. There are no uploaded files, URLs or Qualtrics library IDs.",
        ),
        QuestionCase(
            "pick_group_rank",
            "Group and rank two workspace proposals",
            "PGR",
            "pick_group_rank",
            "Generic value frequencies",
            fields=(
                ExportField("1_GROUP", "Quiet desks - Group", "1"),
                ExportField("1_RANK", "Quiet desks - Rank", "1"),
                ExportField("2_GROUP", "Booking tools - Group", "2"),
                ExportField("2_RANK", "Booking tools - Rank", "2"),
            ),
            choices=("Quiet desks", "Booking tools"),
            rows=(("Next quarter", "1", "Next quarter", "2"), ("Later", "1", "Next quarter", "1")),
            limitations=(
                "Group/rank values remain generic fields; no grouped-rank visualization or validation is inferred."
            ),
        ),
        QuestionCase(
            "drill_down",
            "Choose the area for the next workshop",
            "DD",
            "drill_down",
            "Choice distribution",
            fields=_item_fields("Campus", "Building", "Room"),
            rows=(
                ("North campus", "North campus / Studio", "North campus / Studio / Room A"),
                ("South campus", "South campus / Hub", "South campus / Hub / Room B"),
            ),
            limitations="Illustrative label-export paths stay consistent; no nested option domain is reconstructed.",
            source_url=QUESTION_GUIDE + "specialty-questions/drill-down/",
        ),
        QuestionCase(
            "signature",
            "Sign the fictional workshop attendance card",
            "Signature",
            "signature",
            "Generic value frequencies",
            rows=_single_rows("synthetic-signature-a.png", "synthetic-signature-b.png"),
            limitations="Synthetic filenames only; no signatures or image assets are created.",
        ),
        QuestionCase(
            "heat_map",
            "Mark a preferred position on an imaginary floor plan",
            "HeatMap",
            "heat_map",
            "Generic value frequencies",
            rows=_single_rows('{"x":0.25,"y":0.4}', '{"x":0.7,"y":0.6}'),
            limitations="Illustrative normalized coordinate values; the report does not draw a heat map.",
        ),
        QuestionCase(
            "hot_spot",
            "Choose a zone on the imaginary floor plan",
            "HotSpot",
            "hot_spot",
            "Generic value frequencies",
            rows=_single_rows("Quiet zone", "Collaboration zone", "Quiet zone"),
            limitations="Illustrative region labels; no image regions or hotspot overlay are rendered.",
        ),
        QuestionCase(
            "metadata",
            "Synthetic browser metadata",
            "Meta",
            "metadata",
            "Response metadata",
            selector="Browser",
            fields=(ExportField("BROWSER", "Browser"), ExportField("VERSION", "Version"), ExportField("OS", "OS")),
            rows=(("ExampleBrowser", "1.0", "ExampleOS"), ("DemoBrowser", "2.0", "DemoOS")),
            limitations="Browser fields move to response metadata and do not become respondent answers.",
        ),
        QuestionCase(
            "captcha",
            "Verification placeholder (no respondent answer)",
            "Captcha",
            "captcha",
            "Definition only",
            fields=(),
            limitations="No challenge or fake CAPTCHA solution is generated; absent from report and codebook.",
        ),
        QuestionCase(
            "highlight",
            "Highlight a useful phrase in the workspace guide",
            "Highlight",
            "highlight",
            "Generic value frequencies",
            rows=_single_rows("quiet desks: useful", "booking guide: unclear"),
            limitations="Illustrative annotation values; no highlighted source-document view is rendered.",
        ),
        QuestionCase(
            "screen_capture",
            "Capture the fictional booking page",
            "ScreenCapture",
            "screen_capture",
            "Generic value frequencies",
            rows=_single_rows("synthetic-booking-desktop.png", "synthetic-booking-mobile.png"),
            limitations="Filenames only; no screen capture or product-specific collection service is included.",
        ),
        QuestionCase(
            "video_response",
            "Describe your fictional workspace visit on video",
            "VideoResponse",
            "video_response",
            "Generic value frequencies",
            rows=_single_rows("synthetic-visit-a.mp4", "synthetic-visit-b.mp4"),
            limitations="Filenames only; no recordings, media playback or transcripts are generated.",
        ),
        QuestionCase(
            "user_testing",
            "Try booking an imaginary meeting room",
            "UnmoderatedUserTesting",
            "unmoderated_user_testing",
            "Generic value frequencies",
            fields=_item_fields("Outcome", "Path"),
            rows=(("Completed", "Home > Rooms > Book"), ("Abandoned", "Home > Help")),
            limitations="Illustrative task outcomes and paths, not a platform session or usability visualization.",
        ),
        QuestionCase(
            "location",
            "Select a fictional meeting point",
            "LocationSelector",
            "location_selector",
            "Generic value frequencies",
            rows=_single_rows('{"lat":0.0,"lon":0.0}', '{"lat":0.1,"lon":0.2}'),
            limitations="Invented ocean coordinates with no respondent location; displayed as values, not a map.",
        ),
        QuestionCase(
            "arcgis",
            "Mark a fictional study area",
            "ArcGISMap",
            "arcgis_map",
            "Generic value frequencies",
            rows=_single_rows('{"type":"Point","coordinates":[0.0,0.0]}', '{"type":"Point","coordinates":[0.2,0.1]}'),
            limitations="Illustrative GeoJSON-like strings only; no ArcGIS service, map or licensed layer is used.",
        ),
        QuestionCase(
            "solicit_reviews",
            "Would you open a fictional review invitation?",
            "SolicitReviews",
            "solicit_reviews",
            "Generic value frequencies",
            rows=_single_rows("Invitation opened", "Skipped", "Invitation opened"),
            limitations="Illustrative status labels only; no external review is requested or posted.",
        ),
        QuestionCase(
            "tree_testing",
            "Find room-booking guidance in an imaginary menu",
            "TreeTesting",
            "tree_testing",
            "Generic value frequencies",
            fields=_item_fields("Chosen path", "Outcome"),
            rows=(
                ("Help > Rooms > Booking", "Direct success"),
                ("Help > Workspace > Rooms > Booking", "Indirect success"),
                ("Help > Events", "Not found"),
            ),
            limitations="Illustrative paths/outcomes are generic values; no navigation tree is reconstructed.",
        ),
        QuestionCase(
            "number_scale",
            "How easy was it to book a room, from 1 to 7?",
            "NumberScale",
            "number_scale",
            "Numeric summaries",
            rows=_single_rows("7", "6", "6", "5", "5", "4", "3", "2", "1"),
        ),
        QuestionCase(
            "org_hierarchy",
            "Choose your fictional team within the organization",
            "OrgHierarchy",
            "org_hierarchy",
            "Choice distribution",
            rows=_single_rows(
                "Example Co / Product / Engineering",
                "Example Co / Revenue / Sales",
                "Example Co / Operations / Facilities",
            ),
            limitations="Observed path-label frequencies only; no organization directory or nested domain is inferred.",
        ),
    ])
    return cases


def _definition(cases: list[QuestionCase]) -> dict[str, Any]:
    elements: list[dict[str, Any]] = []
    blocks: dict[str, dict[str, Any]] = {}
    for number, case in enumerate(cases, start=1):
        qid = f"QID{number}"
        payload: dict[str, Any] = {
            "QuestionID": qid,
            "DataExportTag": case.case_id,
            "QuestionText": case.label,
            "QuestionDescription": case.label,
            "QuestionType": case.question_type,
        }
        if case.selector:
            payload["Selector"] = case.selector
        if case.sub_selector:
            payload["SubSelector"] = case.sub_selector
        for key, values, order in (("Choices", case.choices, "ChoiceOrder"), ("Answers", case.answers, "AnswerOrder")):
            if values:
                payload[key] = {str(index): {"Display": value} for index, value in enumerate(values, start=1)}
                payload[order] = [str(index) for index in range(1, len(values) + 1)]
        if case.choices or case.answers:
            values = case.answers or case.choices
            payload["RecodeValues"] = {
                str(index): str(index - 1 if case.canonical_type == "nps" else index)
                for index in range(1, len(values) + 1)
            }
        if case.case_id == "single_other":
            payload["Choices"]["4"]["TextEntry"] = "true"
        if case.case_id == "side_by_side":
            payload["AdditionalQuestions"] = {
                "1": {
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "QuestionText": "Preference",
                    "Choices": {"1": {"Display": "Preferred"}, "2": {"Display": "Useful"}},
                    "ChoiceOrder": ["1", "2"],
                    "RecodeValues": {"1": "1", "2": "2"},
                },
                "2": {
                    "QuestionType": "TE",
                    "Selector": "SL",
                    "QuestionText": "Number of visits",
                    "Validation": {"Settings": {"ContentType": "ValidNumber"}},
                },
                "3": {"QuestionType": "TE", "Selector": "SL", "QuestionText": "Open text"},
            }
        elements.append({"Element": "SQ", "PrimaryAttribute": qid, "Payload": payload})
        section = 1 if number <= 16 else 2 if number <= 29 else 3
        block_id = f"BL_SHOWCASE_{section}"
        block = blocks.setdefault(
            block_id,
            {
                "ID": block_id,
                "Type": "Standard",
                "Description": (
                    "Choice and written answers",
                    "Compound and numeric questions",
                    "Advanced and technical fields",
                )[section - 1],
                "BlockElements": [],
            },
        )
        block["BlockElements"].append({"Type": "Question", "QuestionID": qid})
    elements.extend([
        {"Element": "BL", "Payload": blocks},
        {
            "Element": "FL",
            "Payload": {
                "Type": "Root",
                "FlowID": "FL_1",
                "Flow": [
                    {"Type": "Block", "ID": block_id, "FlowID": f"FL_{index}"}
                    for index, block_id in enumerate(blocks, start=2)
                ],
            },
        },
    ])
    return {
        "SurveyEntry": {
            "SurveyID": SURVEY_ID,
            "SurveyName": "Question type showcase · 100 fictional responses",
            "SurveyLanguage": "EN",
            "SurveyStatus": "Inactive",
            "SurveyDescription": "Synthetic toolkit coverage fixture. Not import-tested in Qualtrics.",
        },
        "SurveyElements": elements,
    }


def _write_responses(path: Path, cases: list[QuestionCase]) -> None:
    metadata = (
        "ResponseId",
        "StartDate",
        "EndDate",
        "RecordedDate",
        "Finished",
        "Progress",
        "Duration (in seconds)",
        "UserLanguage",
        "DistributionChannel",
    )
    columns, labels = list(metadata), list(metadata)
    imports: list[dict[str, str]] = [{"ImportId": column} for column in metadata]
    for number, case in enumerate(cases, start=1):
        if any(len(row) != len(case.fields) for row in case.rows) or (case.fields and not case.rows):
            raise ValueError(f"Sample row width differs from exported fields: {case.case_id}")
        for field in case.fields:
            suffix = f"{field.separator}{field.suffix}" if field.suffix else ""
            columns.append(case.case_id + suffix)
            labels.append(case.label + (" - " + field.label if field.label else ""))
            import_info = {"ImportId": f"QID{number}{suffix}"}
            if field.choice_id and case.choices:
                import_info["choiceId"] = field.choice_id
            if field.answer_id:
                import_info["answerId"] = field.answer_id
            imports.append(import_info)
    rng = random.Random(20260909)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerows((columns, labels, [json.dumps(info, sort_keys=True) for info in imports]))
        for index in range(RESPONSE_COUNT):
            finished = index % 7 != 0
            progress = 100 if finished else (35, 55, 75)[index % 3]
            recorded = datetime(2026, 1, 5, 9) + timedelta(days=index * 84 // RESPONSE_COUNT, hours=index % 8)
            duration = 160 + index * 19 % 420
            row = [
                f"R_SYNTHETIC_{index + 1:03d}",
                (recorded - timedelta(seconds=duration)).isoformat(sep=" "),
                recorded.isoformat(sep=" "),
                recorded.isoformat(sep=" "),
                str(finished),
                str(progress),
                str(duration),
                "EN",
                "anonymous",
            ]
            for number, case in enumerate(cases, start=1):
                if not case.fields:
                    continue
                technical = case.canonical_type in {"metadata", "timing"}
                skipped = not technical and (number / len(cases) * 100 > progress or (index + number) % 17 == 0)
                if skipped:
                    values = ("",) * len(case.fields)
                elif case.case_id.startswith("single_") and case.case_id != "single_other":
                    # A person's department stays consistent across layout examples.
                    values = case.rows[index % len(case.rows)]
                else:
                    values = rng.choice(case.rows)
                row.extend(values)
            writer.writerow(row)


def build_showcase(output_dir: Path) -> dict[str, Path]:
    """Write the QSF, three-header-row CSV, honest coverage manifest and real report."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        key: output_dir / name
        for key, name in (
            ("survey", "survey.qsf"),
            ("responses", "responses.csv"),
            ("coverage", "coverage.json"),
            ("report", "report.html"),
        )
    }
    cases = _cases()
    paths["survey"].write_text(json.dumps(_definition(cases), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_responses(paths["responses"], cases)
    entities = parse_survey(paths["responses"], paths["survey"])
    validate_entity_set(entities, strict=True)
    questions = {str(question["question_external_id"]): question for question in entities.questions}
    field_counts = Counter(str(field["question_external_id"]) for field in entities.question_fields)
    entries = []
    for number, case in enumerate(cases, start=1):
        qid = f"QID{number}"
        canonical = resolve_question_type(case.question_type, case.selector, case.sub_selector).canonical_question_type
        if canonical != case.canonical_type or field_counts[qid] != len(case.fields):
            raise ValueError(f"Showcase definition no longer matches parser coverage: {case.case_id}")
        if case.fields and questions[qid]["canonical_question_type"] != canonical:
            raise ValueError(f"Unexpected parsed question type: {case.case_id}")
        entries.append({
            "case_id": case.case_id,
            "question_id": qid,
            "label": case.label,
            "question_type": case.question_type,
            "selector": case.selector,
            "sub_selector": case.sub_selector,
            "canonical_type": canonical,
            "field_count": field_counts[qid],
            "presentation": case.presentation,
            "question_role": questions[qid]["question_role"] if qid in questions else "definition_only",
            "limitations": case.limitations,
            "source_url": case.source_url,
        })
    coverage = {
        "response_count": len(entities.responses),
        "family_count": len({case.canonical_type for case in cases}),
        "case_count": len(cases),
        "synthetic": True,
        "import_tested": False,
        "scope": "Toolkit-recognized families and selected export variants, not every Qualtrics configuration.",
        "cases": entries,
    }
    paths["coverage"].write_text(json.dumps(coverage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    render_report(entities, paths["report"])
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Directory for generated example files")
    args = parser.parse_args()
    for kind, path in build_showcase(args.output).items():
        print(f"{kind}: {path}")


if __name__ == "__main__":
    main()
