# ruff: noqa: E501 -- embedded standalone HTML/CSS remains readable at natural line lengths
from __future__ import annotations

import contextlib
import csv
import glob
import hashlib
import html
import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NAMES = (
    "surveys",
    "sections",
    "question_catalog",
    "question_field_catalog",
    "questions",
    "answer_options",
    "question_fields",
    "responses",
    "response_answers",
)
META = {
    "StartDate",
    "EndDate",
    "Status",
    "IPAddress",
    "Progress",
    "Finished",
    "RecordedDate",
    "ResponseId",
    "RecipientLastName",
    "RecipientFirstName",
    "RecipientEmail",
    "ExternalReference",
    "DistributionChannel",
    "UserLanguage",
    "Duration (in seconds)",
}


@dataclass
class EntitySet:
    surveys: list[dict[str, Any]] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    question_catalog: list[dict[str, Any]] = field(default_factory=list)
    question_field_catalog: list[dict[str, Any]] = field(default_factory=list)
    questions: list[dict[str, Any]] = field(default_factory=list)
    answer_options: list[dict[str, Any]] = field(default_factory=list)
    question_fields: list[dict[str, Any]] = field(default_factory=list)
    responses: list[dict[str, Any]] = field(default_factory=list)
    response_answers: list[dict[str, Any]] = field(default_factory=list)


def _clean(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


def _hash(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _qid(value: str) -> str | None:
    match = re.search(r"(QID\d+|Q\d+)", value, re.I)
    return match.group(1).upper() if match else None


def _question_role(definition: dict[str, Any], import_ids: list[str]) -> str:
    question_type = str(definition.get("QuestionType") or "").casefold()
    selector = str(definition.get("Selector") or "").casefold()
    if question_type in {"meta", "metadata"} or selector == "browser":
        return "metadata"
    if question_type == "timing" or selector == "timing":
        return "timing"
    technical = " ".join(import_ids).upper()
    metadata_suffixes = ("_BROWSER", "_VERSION", "_OS", "_RESOLUTION", "_USERAGENT")
    if technical and all(
        any(code in item.upper() for code in metadata_suffixes) for item in import_ids
    ):
        return "metadata"
    timing_suffixes = ("FIRST_CLICK", "LAST_CLICK", "PAGE_SUBMIT", "CLICK_COUNT")
    if any(code in technical for code in timing_suffixes):
        return "timing"
    return "response"


def _field_text(header: str, question_text: str, column: str, suffix: str | None) -> str:
    """Return a compact field label without losing its technical identity."""
    cleaned_header = _clean(header)
    if cleaned_header.casefold().startswith((question_text + " - ").casefold()):
        return cleaned_header[len(question_text) + 3 :]
    if cleaned_header.casefold().endswith((" - " + question_text).casefold()):
        candidate = cleaned_header[: -(len(question_text) + 3)]
        if not candidate.startswith(("http://", "https://")):
            return candidate
    number = re.match(r"(\d+)", str(suffix or column))
    if cleaned_header.startswith(("http://", "https://")) and number:
        return f"Item {number.group(1)}"
    return cleaned_header or str(suffix or column)


def _qsf(
    path: Path | None,
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    if not path:
        return {}, {}, {}, []
    data = json.loads(path.read_text(encoding="utf-8"))
    entry = data.get("SurveyEntry", data)
    questions = {}
    for element in data.get("SurveyElements", []):
        if element.get("Element") == "SQ":
            payload = element.get("Payload", {})
            qid = payload.get("QuestionID") or element.get("PrimaryAttribute")
            if qid:
                questions[str(qid)] = payload
    questions.update(data.get("Questions", {}))
    question_blocks = {}
    sections = []
    block_elements = next(
        (
            element.get("Payload", {})
            for element in data.get("SurveyElements", [])
            if element.get("Element") == "BL"
        ),
        {},
    )
    for block_order, block in enumerate(block_elements.values(), start=1):
        if block.get("Type") == "Trash":
            continue
        section_id = block.get("ID")
        sections.append(
            {
                "section_id": section_id,
                "section_name": block.get("Description"),
                "section_type": block.get("Type"),
                "section_order": block_order,
            }
        )
        for question_order, element in enumerate(block.get("BlockElements", []), start=1):
            question_id = element.get("QuestionID")
            if question_id:
                question_blocks[str(question_id)] = {
                    "section_id": section_id,
                    "block_id": section_id,
                    "block_name": block.get("Description"),
                    "block_type": block.get("Type"),
                    "block_order": block_order,
                    "question_order_in_block": question_order,
                }
    return entry, questions, question_blocks, sections


def _matching_definition(csv_path: Path) -> Path | None:
    candidates = {candidate.name.casefold(): candidate for candidate in csv_path.parent.iterdir()}
    for suffix in (".qsf", ".json"):
        match = candidates.get(f"{csv_path.stem}{suffix}".casefold())
        if match and match.is_file():
            return match
    return None


def _expand_paths(paths: Sequence[str | Path]) -> list[Path]:
    expanded: list[Path] = []
    for value in paths:
        pattern = str(value)
        matches = (
            sorted(glob.glob(pattern, recursive=True)) if glob.has_magic(pattern) else [pattern]
        )
        if not matches:
            raise FileNotFoundError(f"Path pattern matched no files: {pattern}")
        expanded.extend(Path(match) for match in matches)
    return expanded


def _parse_survey_file(
    csv_path: str | Path,
    qsf_path: str | Path | None = None,
    survey_id: str | None = None,
) -> EntitySet:
    csv_path = Path(csv_path)
    qsf_path = Path(qsf_path) if qsf_path else _matching_definition(csv_path)
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    if len(rows) < 2:
        raise ValueError("Qualtrics CSV must contain column and question-text rows")
    columns, headers = rows[0], rows[1]
    metadata = rows[2] if len(rows) > 2 else [""] * len(columns)
    has_import = any("ImportId" in value for value in metadata)
    entry, qsf_questions, question_blocks, sections = _qsf(qsf_path)
    sid = survey_id or entry.get("SurveyID") or csv_path.stem
    entities = EntitySet(
        surveys=[
            {
                "survey_id": sid,
                "survey_name": entry.get("SurveyName") or csv_path.stem,
                "survey_status": entry.get("SurveyStatus"),
                "default_language": entry.get("SurveyLanguage"),
            }
        ]
    )
    entities.sections = [{"survey_id": sid, **section} for section in sections]
    field_specs: list[tuple[int, str, str, str]] = []
    grouped_headers: dict[str, list[str]] = {}
    for index, (column, header, raw_meta) in enumerate(
        zip(columns, headers, metadata, strict=True)
    ):
        import_id = ""
        if has_import:
            with contextlib.suppress(json.JSONDecodeError, AttributeError):
                import_id = str(json.loads(raw_meta).get("ImportId") or "")
        question_id = _qid(import_id or column)
        if question_id and column not in META:
            field_specs.append((index, column, header, import_id))
            grouped_headers.setdefault(question_id, []).append(header)
    seen = set()
    for index, column, header, import_id in field_specs:
        question_id = _qid(import_id or column)
        if question_id is None:
            continue
        definition = qsf_questions.get(question_id, {})
        question_text = _clean(definition.get("QuestionText"))
        if not question_text:
            export_tag = _clean(definition.get("DataExportTag"))
            if export_tag:
                question_text = export_tag.replace("_", " ").strip().title()
            else:
                prefixes = [text.split(" - ", 1)[0] for text in grouped_headers[question_id]]
                question_text = prefixes[0] if len(set(prefixes)) == 1 else header
        catalog_id = _hash(question_text.casefold())
        if question_id not in seen:
            question_import_ids = [
                item[3] for item in field_specs if _qid(item[3] or item[1]) == question_id
            ]
            role = _question_role(definition, question_import_ids)
            entities.questions.append(
                {
                    "survey_id": sid,
                    "question_id": question_id,
                    "question_catalog_id": catalog_id,
                    "question_text": question_text,
                    "question_description": definition.get("DataExportTag"),
                    "question_type": definition.get("QuestionType"),
                    "selector": definition.get("Selector"),
                    "sub_selector": definition.get("SubSelector"),
                    "question_role": role,
                    **question_blocks.get(question_id, {}),
                }
            )
            # Meta Info and Timing choices describe captured fields, not respondent
            # answer options. Treating them as options creates false "unused" alerts.
            for option_id, option in (
                (definition.get("Choices") or {}).items() if role == "response" else []
            ):
                entities.answer_options.append(
                    {
                        "survey_id": sid,
                        "question_id": question_id,
                        "answer_id": str(option_id),
                        "answer_text": _clean(
                            option.get("Display") if isinstance(option, dict) else option
                        ),
                    }
                )
            seen.add(question_id)
        suffix = (import_id.replace(question_id, "", 1).strip("_") or None) if import_id else None
        field_text = _field_text(header, question_text, column, suffix)
        entities.question_fields.append(
            {
                "survey_id": sid,
                "question_id": question_id,
                "field_id": column,
                "source_import_id": import_id or None,
                "source_field_suffix": suffix,
                "source_column_index": index,
                "question_catalog_id": catalog_id,
                "question_field_catalog_id": _hash(catalog_id, _clean(field_text).casefold()),
                "field_text": field_text,
                "is_text_field": bool(suffix and "TEXT" in suffix),
            }
        )
    field_map = {row["field_id"]: row["question_id"] for row in entities.question_fields}
    entities.question_catalog = list(
        {
            item["question_catalog_id"]: {
                "question_catalog_id": item["question_catalog_id"],
                "question_text": item["question_text"],
                "normalized_question_text": _clean(item["question_text"]).casefold(),
            }
            for item in entities.questions
        }.values()
    )
    entities.question_field_catalog = list(
        {
            item["question_field_catalog_id"]: {
                "question_field_catalog_id": item["question_field_catalog_id"],
                "question_catalog_id": item["question_catalog_id"],
                "field_text": item["field_text"],
                "normalized_field_text": _clean(item["field_text"]).casefold(),
            }
            for item in entities.question_fields
        }.values()
    )
    for values in rows[3 if has_import else 2 :]:
        record = dict(zip(columns, values, strict=False))
        response_id = record.get("ResponseId", "")
        if not response_id:
            continue
        entities.responses.append(
            {
                "survey_id": sid,
                "response_id": response_id,
                "started_at": record.get("StartDate"),
                "ended_at": record.get("EndDate"),
                "recorded_at": record.get("RecordedDate"),
                "is_finished": record.get("Finished"),
                "user_language": record.get("UserLanguage"),
            }
        )
        for column, question_id in field_map.items():
            value = record.get(column, "")
            if value:
                entities.response_answers.append(
                    {
                        "survey_id": sid,
                        "response_id": response_id,
                        "question_id": question_id,
                        "field_id": column,
                        "user_language": record.get("UserLanguage"),
                        "answer_text": value,
                    }
                )
    return entities


def parse_survey(
    csv_path: str | Path,
    qsf_path: str | Path | None = None,
    survey_id: str | None = None,
) -> EntitySet:
    """Parse one CSV or merge every survey matched by a wildcard path."""
    csv_files = _expand_paths([csv_path])
    definition_files = _expand_paths([qsf_path]) if qsf_path else []
    if len(csv_files) == 1 and len(definition_files) <= 1:
        return _parse_survey_file(
            csv_files[0],
            definition_files[0] if definition_files else None,
            survey_id=survey_id,
        )
    if survey_id:
        raise ValueError("survey_id cannot be forced when a wildcard matches multiple CSV files")
    return parse_surveys(csv_files, definition_files or None)


def merge_entity_sets(entity_sets: list[EntitySet]) -> EntitySet:
    """Combine surveys while de-duplicating the two canonical catalogs."""
    result = EntitySet()
    survey_ids = [str(survey["survey_id"]) for item in entity_sets for survey in item.surveys]
    duplicates = {survey_id for survey_id in survey_ids if survey_ids.count(survey_id) > 1}
    if duplicates:
        raise ValueError(f"Duplicate survey_id values: {', '.join(sorted(duplicates))}")
    for name in NAMES:
        rows = [row for item in entity_sets for row in getattr(item, name)]
        if name in {"question_catalog", "question_field_catalog"}:
            id_key = f"{name}_id"
            rows = list({str(row[id_key]): row for row in rows}.values())
        setattr(result, name, rows)
    return result


def parse_surveys(
    csv_paths: Sequence[str | Path],
    qsf_paths: Sequence[str | Path] | None = None,
) -> EntitySet:
    """Parse multiple CSV/QSF pairs into one consistent entity collection."""
    csv_files = _expand_paths(csv_paths)
    qsf_files = _expand_paths(qsf_paths or [])
    if qsf_files and len(qsf_files) not in {1, len(csv_files)}:
        raise ValueError("Provide no QSF files, one QSF for one CSV, or one QSF per CSV")
    if len(qsf_files) == 1 and len(csv_files) > 1:
        raise ValueError("A single QSF cannot be applied to multiple CSV files")
    parsed = [
        _parse_survey_file(
            csv_path,
            qsf_files[index] if qsf_files else None,
        )
        for index, csv_path in enumerate(csv_files)
    ]
    return merge_entity_sets(parsed)


def write_entities(entities: EntitySet, folder: str | Path, format: str = "json") -> None:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        records = getattr(entities, name)
        path = folder / f"{name}.{format}"
        if format == "json":
            path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        elif format == "csv":
            keys = list(dict.fromkeys(key for row in records for key in row))
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=keys)
                writer.writeheader()
                writer.writerows(records)
        elif format == "parquet":
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError as exc:
                raise RuntimeError("Install qualtrics-toolkit[parquet]") from exc
            pq.write_table(pa.Table.from_pylist(records), path)
        else:
            raise ValueError(f"Unsupported format: {format}")


def load_entities(folder: str | Path | None = None, **paths: str | Path) -> EntitySet:
    folder = Path(folder) if folder else None
    result = EntitySet()
    for name in NAMES:
        path = (
            Path(paths[name])
            if name in paths
            else next(
                (
                    p
                    for ext in ("json", "csv", "parquet")
                    if folder and (p := folder / f"{name}.{ext}").exists()
                ),
                None,
            )
        )
        if not path:
            continue
        if path.suffix == ".json":
            records = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".csv":
            with path.open(encoding="utf-8", newline="") as handle:
                records = list(csv.DictReader(handle))
        else:
            try:
                import pyarrow.parquet as pq
            except ImportError as exc:
                raise RuntimeError("Install qualtrics-toolkit[parquet]") from exc
            records = pq.read_table(path).to_pylist()
        setattr(result, name, records)
    return result


def render_report(entities: EntitySet, output: str | Path) -> None:
    questions = {(q["survey_id"], q["question_id"]): q for q in entities.questions}
    fields = {
        (f["survey_id"], f["question_id"], f["field_id"]): f for f in entities.question_fields
    }
    answers: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for answer in entities.response_answers:
        answers.setdefault((answer["survey_id"], answer["response_id"]), []).append(answer)
    survey_lookup = {str(item["survey_id"]): item for item in entities.surveys}
    survey_name = (
        str(entities.surveys[0].get("survey_name") or "Qualtrics survey")
        if len(entities.surveys) == 1
        else "Qualtrics survey collection"
    )
    question_roles = {
        key: str(
            question.get("question_role")
            or _question_role(
                question,
                [
                    str(item.get("source_import_id") or "")
                    for field_key, item in fields.items()
                    if field_key[:2] == key
                ],
            )
        )
        for key, question in questions.items()
    }
    response_questions = {
        key: question for key, question in questions.items() if question_roles[key] == "response"
    }
    question_responses: dict[tuple[str, str], set[str]] = {key: set() for key in response_questions}
    question_answers: dict[tuple[str, str], list[dict[str, Any]]] = {
        key: [] for key in response_questions
    }
    used_fields = set()
    used_values: dict[tuple[str, str], set[str]] = {}
    for answer in entities.response_answers:
        question_key = (answer["survey_id"], answer["question_id"])
        if question_roles.get(question_key, "response") != "response":
            continue
        question_responses.setdefault(question_key, set()).add(answer["response_id"])
        question_answers.setdefault(question_key, []).append(answer)
        used_fields.add((answer["survey_id"], answer["question_id"], answer["field_id"]))
        used_values.setdefault(question_key, set()).add(str(answer["answer_text"]).casefold())
    unanswered_questions = [
        question for key, question in response_questions.items() if not question_responses.get(key)
    ]
    unused_fields = [
        item
        for key, item in fields.items()
        if question_roles.get((key[0], key[1]), "response") == "response" and key not in used_fields
    ]
    unused_options = [
        option
        for option in entities.answer_options
        if question_roles.get((option["survey_id"], option["question_id"]), "response")
        == "response"
        and str(option["answer_id"]).casefold()
        not in used_values.get((option["survey_id"], option["question_id"]), set())
        and str(option["answer_text"]).casefold()
        not in used_values.get((option["survey_id"], option["question_id"]), set())
    ]
    response_count = len(entities.responses)
    survey_response_counts = Counter(str(item["survey_id"]) for item in entities.responses)
    content_answer_count = len(
        {
            (item["survey_id"], item["response_id"], item["question_id"])
            for item in entities.response_answers
            if question_roles.get((item["survey_id"], item["question_id"]), "response")
            == "response"
        }
    )
    finished_count = sum(
        str(item.get("is_finished", "")).casefold() in {"true", "1"} for item in entities.responses
    )
    survey_finished_counts = Counter(
        str(item["survey_id"])
        for item in entities.responses
        if str(item.get("is_finished", "")).casefold() in {"true", "1"}
    )
    survey_answer_counts = Counter(
        str(survey_id)
        for survey_id, _, _ in {
            (item["survey_id"], item["response_id"], item["question_id"])
            for item in entities.response_answers
            if question_roles.get((item["survey_id"], item["question_id"]), "response")
            == "response"
        }
    )
    survey_question_counts = Counter(str(key[0]) for key in response_questions)
    survey_unanswered_counts = Counter(str(item["survey_id"]) for item in unanswered_questions)
    survey_unused_field_counts = Counter(str(item["survey_id"]) for item in unused_fields)
    survey_options = "".join(
        f"<option value='{html.escape(str(item['survey_id']), quote=True)}' "
        f"data-responses='{survey_response_counts.get(str(item['survey_id']), 0)}' "
        f"data-finished='{survey_finished_counts.get(str(item['survey_id']), 0)}' "
        f"data-questions='{survey_question_counts.get(str(item['survey_id']), 0)}' "
        f"data-answers='{survey_answer_counts.get(str(item['survey_id']), 0)}' "
        f"data-unanswered='{survey_unanswered_counts.get(str(item['survey_id']), 0)}' "
        f"data-unused-fields='{survey_unused_field_counts.get(str(item['survey_id']), 0)}'>"
        f"{html.escape(str(item.get('survey_name') or item['survey_id']))}</option>"
        for item in entities.surveys
    )
    question_choices = []
    coverage_rows = []
    for key, question in response_questions.items():
        question_id = question["question_id"]
        survey_id = str(key[0])
        question_token = f"{survey_id}::{question_id}"
        label = str(question.get("question_text") or question_id)
        block_name = str(question.get("block_name") or "")
        choice_label = html.escape(label)
        if len(entities.surveys) > 1:
            choice_label += f"<em>{html.escape(str(survey_lookup.get(survey_id, {}).get('survey_name') or survey_id))}</em>"
        count = len(question_responses.get(key, set()))
        question_response_total = survey_response_counts.get(survey_id, 0)
        rate = round((count / question_response_total * 100) if question_response_total else 0)
        question_choices.append(
            f"<label data-survey='{html.escape(survey_id, quote=True)}'><input class='question-choice' "
            f"type='checkbox' value='{html.escape(question_token, quote=True)}' "
            f"checked><span>{choice_label}</span><small>{count}/{question_response_total}</small></label>"
        )
        coverage_rows.append(
            f"<tr data-survey='{html.escape(survey_id, quote=True)}'><td><strong>{html.escape(label)}</strong>"
            f"<small>{html.escape(question_id)}"
            f"{f' · {html.escape(block_name)}' if block_name else ''}"
            "</small></td>"
            f"<td>{count:,}</td><td><div class='meter'><i style='width:{rate}%'></i></div>{rate}%</td></tr>"
        )

    def issue_list(items: list[dict[str, Any]], label_key: str, empty: str) -> str:
        if not items:
            return f"<p class='meta'>{empty}</p>"
        labels = [
            str(item.get(label_key) or item.get("question_id") or "Unknown") for item in items
        ]
        preview = "".join(f"<li>{html.escape(label)}</li>" for label in labels[:8])
        remaining = f"<li>…and {len(labels) - 8} more</li>" if len(labels) > 8 else ""
        return f"<ul>{preview}{remaining}</ul>"

    quality_panels = []
    for survey_id, survey in survey_lookup.items():
        quality_groups = [
            (
                "Questions without responses",
                [item for item in unanswered_questions if str(item["survey_id"]) == survey_id],
                "question_text",
            ),
            (
                "Fields without values",
                [item for item in unused_fields if str(item["survey_id"]) == survey_id],
                "field_text",
            ),
            (
                "Defined options not observed",
                [item for item in unused_options if str(item["survey_id"]) == survey_id],
                "answer_text",
            ),
        ]
        quality_html = "".join(
            f"<div class='quality-group'><strong>{html.escape(title)}</strong>"
            f"{issue_list(items, label_key, '')}</div>"
            for title, items, label_key in quality_groups
            if items
        )
        if not quality_html:
            quality_html = (
                "<div class='healthy'><strong>No coverage gaps detected</strong>"
                "<span>Every response question and concrete field has data.</span></div>"
            )
        survey_label = str(survey.get("survey_name") or survey_id)
        quality_panels.append(
            f"<div class='quality' data-survey='{html.escape(survey_id, quote=True)}'>"
            "<div class='quality-head'><i></i><strong>Data quality"
            f"{f' · {html.escape(survey_label)}' if len(entities.surveys) > 1 else ''}</strong></div>"
            f"<div class='quality-groups'>{quality_html}</div></div>"
        )

    def distribution(values: list[str], denominator: int) -> str:
        counts = Counter(values)
        rows = []
        for value, count in counts.most_common(12):
            rate = count / denominator * 100 if denominator else 0
            rows.append(
                f"<div class='distribution-row'><span title='{html.escape(value, quote=True)}'>"
                f"{html.escape(value)}</span><div class='distribution-bar'><i style='width:{rate:.1f}%'></i>"
                f"</div><b>{count:,}</b><small>{rate:.0f}%</small></div>"
            )
        hidden_count = sum(counts.values()) - sum(count for _, count in counts.most_common(12))
        if hidden_count:
            rows.append(f"<p class='meta'>Other values: {hidden_count:,}</p>")
        return "".join(rows) or "<p class='meta'>No values observed.</p>"

    question_analytics = []
    categorical_types = {"MC", "MATRIX", "SBS", "DD", "DRILLDOWN", "RO", "RANKORDER"}
    numeric_types = {"SLIDER", "CS", "CONSTANTSUM"}
    for key, question in response_questions.items():
        question_id = str(question["question_id"])
        label = str(question.get("question_text") or question_id)
        question_type = str(question.get("question_type") or "Unknown").upper()
        selector = str(question.get("selector") or "")
        observed = question_answers.get(key, [])
        respondent_count = len(question_responses.get(key, set()))
        question_response_total = survey_response_counts.get(str(key[0]), 0)
        coverage = (
            respondent_count / question_response_total * 100 if question_response_total else 0
        )
        field_groups: dict[str, list[str]] = {}
        for answer in observed:
            field_groups.setdefault(str(answer["field_id"]), []).append(str(answer["answer_text"]))
        summary = (
            f"<span><b>{respondent_count:,}</b> respondents</span>"
            f"<span><b>{coverage:.0f}%</b> coverage</span>"
            f"<span><b>{len(observed):,}</b> values</span>"
        )
        bodies = []
        if question_type == "TE":
            for field_id, values in field_groups.items():
                numeric_values = []
                for value in values:
                    with contextlib.suppress(ValueError):
                        numeric_values.append(float(value.replace(",", "")))
                field_label = (
                    fields.get((key[0], key[1], field_id), {}).get("field_text") or field_id
                )
                heading = (
                    f"<h4>{html.escape(str(field_label))}</h4>" if len(field_groups) > 1 else ""
                )
                if values and len(numeric_values) / len(values) >= 0.8:
                    content = (
                        "<div class='numeric-summary'>"
                        f"<span><b>{min(numeric_values):g}</b> Minimum</span>"
                        f"<span><b>{sum(numeric_values) / len(numeric_values):.1f}</b> Average</span>"
                        f"<span><b>{max(numeric_values):g}</b> Maximum</span></div>"
                    )
                else:
                    content = (
                        f"<p class='meta'>{len(set(values)):,} unique text answers. Most frequent values:</p>"
                        + distribution(values, len(values))
                    )
                bodies.append(f"<div class='field-analysis'>{heading}{content}</div>")
        elif question_type in numeric_types:
            for field_id, values in field_groups.items():
                numeric_values = []
                for value in values:
                    with contextlib.suppress(ValueError):
                        numeric_values.append(float(value.replace(",", "")))
                field_label = (
                    fields.get((key[0], key[1], field_id), {}).get("field_text") or field_id
                )
                if numeric_values:
                    bodies.append(
                        f"<div class='field-analysis'><h4>{html.escape(str(field_label))}</h4>"
                        f"<div class='numeric-summary'><span><b>{min(numeric_values):g}</b> Minimum</span>"
                        f"<span><b>{sum(numeric_values) / len(numeric_values):.1f}</b> Average</span>"
                        f"<span><b>{max(numeric_values):g}</b> Maximum</span></div></div>"
                    )
        else:
            for field_id, values in field_groups.items():
                field_label = (
                    fields.get((key[0], key[1], field_id), {}).get("field_text") or field_id
                )
                show_field = len(field_groups) > 1 or question_type in categorical_types
                heading = f"<h4>{html.escape(str(field_label))}</h4>" if show_field else ""
                bodies.append(
                    f"<div class='field-analysis'>{heading}{distribution(values, len(values))}</div>"
                )
        type_label = {"MC": "Multiple choice", "TE": "Text entry"}.get(
            question_type, question_type.replace("_", " ").title()
        )
        block_label = str(question.get("block_name") or "")
        analysis_body = "".join(bodies) or '<p class="meta">No values observed.</p>'
        question_analytics.append(
            f"<details class='question-analysis' data-survey='{html.escape(str(key[0]), quote=True)}' "
            f"data-question='{html.escape(question_id)}'>"
            f"<summary><span class='analysis-title'>{html.escape(label)}<small>{html.escape(question_id)}"
            f" · {html.escape(type_label)}{f' · {html.escape(selector)}' if selector else ''}"
            f"{f' · Block: {html.escape(block_label)}' if block_label else ''}</small></span>"
            f"<span class='analysis-summary'>{summary}</span></summary>"
            f"<div class='analysis-body'>{analysis_body}</div></details>"
        )

    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{html.escape(survey_name)} · Response report</title>",
        """<style>
        :root{--ink:#172033;--muted:#64748b;--line:#dbe3ee;--paper:#fff;--wash:#f4f7fb;
        --brand:#155eef}*{box-sizing:border-box}body{margin:0;background:var(--wash);color:var(--ink);
        font:15px/1.5 system-ui,sans-serif}.shell{width:min(1100px,calc(100% - 2rem));margin:auto}
        header{background:linear-gradient(135deg,#0b2559,#155eef);color:#fff;padding:3rem 1rem 5rem}
        header h1{font-size:clamp(2rem,5vw,3.4rem);line-height:1.05;margin:.3rem 0}
        header p{opacity:.8;margin:0}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;
        margin-top:-2.5rem}.stat,.toolbar,details,.empty{background:#fff;border:1px solid var(--line);
        border-radius:15px;box-shadow:0 10px 30px #17346a12}.stat{padding:1.1rem}.stat strong{display:block;
        font-size:1.7rem}.stat span,.meta,#count{color:var(--muted);font-size:.85rem}.toolbar{display:flex;
        gap:.7rem;align-items:center;padding:1rem;margin:1.2rem 0}
        input,select{flex:1;min-width:10rem;padding:.75rem 1rem;border:1px solid var(--line);border-radius:10px;
        font:inherit}button{padding:.7rem .9rem;border:1px solid var(--line);border-radius:10px;background:#fff;
        font-weight:700;cursor:pointer}details{margin:.75rem 0;overflow:hidden}summary{cursor:pointer;
        display:flex;gap:1rem;align-items:center;padding:1rem;list-style:none}summary:before{content:'›';
        color:var(--brand);font-size:1.5rem}details[open] summary:before{transform:rotate(90deg)}
        .identity{font-weight:800;flex:1}.badge{background:#e9f0ff;color:#0b3da5;border-radius:999px;
        padding:.25rem .65rem;font-size:.78rem;font-weight:800}.answers{border-top:1px solid var(--line);
        padding:.2rem 1rem}.answer{padding:.9rem 0;border-bottom:1px solid #edf1f6}.answer:last-child{border:0}
        .question-head{margin-bottom:.45rem}.question{display:block;font-weight:750}.question-meta{display:block;
        color:var(--muted);font-size:.72rem;margin-top:.08rem}
        .type{color:var(--muted);background:var(--wash);border-radius:999px;padding:.12rem .45rem;font-size:.7rem}
        .field-answer{display:grid;grid-template-columns:minmax(150px,34%) 1fr;gap:1rem;padding:.4rem 0}
        .field{color:var(--muted);font-size:.82rem;overflow-wrap:anywhere}.value{white-space:pre-wrap;overflow-wrap:anywhere}
        .no-selected{margin:.7rem 1rem;padding:.8rem;border-radius:9px;background:var(--wash);color:var(--muted);
        font-size:.82rem;text-align:center}
        nav{display:flex;gap:.5rem;margin:1.3rem 0}nav a{text-decoration:none;color:var(--brand);
        background:#fff;border:1px solid var(--line);border-radius:999px;padding:.55rem .9rem;font-weight:700}
        section>h2{font-size:1.7rem;margin:2rem 0 .2rem}.section-intro{color:var(--muted);margin:0 0 1rem}
        .analytics{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}.analytic{background:#fff;
        border:1px solid var(--line);border-radius:12px;padding:1rem}.analytic strong{display:block;font-size:1.5rem}
        .panel{background:#fff;border:1px solid var(--line);border-radius:15px;padding:1rem;margin:1rem 0}
        table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:.65rem;border-bottom:1px solid #edf1f6}
        td small{display:block;color:var(--muted)}.meter{display:inline-block;width:120px;height:7px;
        background:#e8eef8;border-radius:9px;margin-right:.5rem}.meter i{display:block;height:100%;
        background:var(--brand);border-radius:9px}.quality{background:#fff;border:1px solid var(--line);
        border-radius:15px;padding:1rem;margin:1rem 0}.quality-head{display:flex;align-items:center;gap:.7rem;
        margin-bottom:.7rem}.quality-head i{width:10px;height:10px;border-radius:50%;background:#f59e0b}
        .quality-groups{display:grid;grid-template-columns:repeat(3,1fr);gap:.8rem}.quality-group{background:#fff8e8;
        border-radius:10px;padding:.8rem}.quality-group ul{margin:.5rem 0 0;padding-left:1.2rem}
        .healthy{display:flex;gap:.7rem;align-items:center;color:#087e6b}.healthy span{color:var(--muted)}
        .survey-switcher{display:flex;align-items:center;gap:.8rem;background:#fff;border:1px solid var(--line);
        border-radius:13px;padding:.8rem 1rem;margin:1.2rem 0}.survey-switcher label{font-weight:750}.survey-switcher select{max-width:420px}
        [hidden]{display:none!important}.question-analysis summary{align-items:flex-start}.analysis-title{font-weight:750;min-width:0;flex:1}
        .analysis-title small{display:block;color:var(--muted);font-weight:500}.analysis-summary{display:flex;
        gap:1rem;color:var(--muted);font-size:.8rem;flex-wrap:wrap;justify-content:flex-end}.analysis-summary b{color:var(--ink)}
        .analysis-body{border-top:1px solid var(--line);padding:1rem}.field-analysis+ .field-analysis{margin-top:1.1rem}
        .field-analysis h4{margin:0 0 .5rem}.distribution-row{display:grid;grid-template-columns:minmax(120px,26%) 1fr 55px 45px;
        gap:.65rem;align-items:center;padding:.28rem 0}.distribution-row>span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
        .distribution-row b,.distribution-row small{text-align:right}.distribution-row small{color:var(--muted)}
        .distribution-bar{height:9px;background:#e8eef8;border-radius:999px;overflow:hidden}.distribution-bar i{display:block;
        height:100%;background:linear-gradient(90deg,#155eef,#65a2ff);border-radius:999px}.numeric-summary{display:grid;
        grid-template-columns:repeat(3,1fr);gap:.7rem}.numeric-summary span{background:var(--wash);padding:.7rem;border-radius:9px;
        color:var(--muted);font-size:.78rem}.numeric-summary b{display:block;color:var(--ink);font-size:1.15rem}
        .filter-wrap{position:relative}.question-menu{position:absolute;right:0;top:calc(100% + .35rem);
        width:min(500px,90vw);max-height:380px;overflow:auto;background:#fff;z-index:3;
        border:1px solid var(--line);border-radius:12px;padding:.7rem;box-shadow:0 15px 35px #17346a25}
        .question-menu[hidden]{display:none}.question-menu label{display:grid;grid-template-columns:20px minmax(0,1fr) auto;
        gap:.55rem;align-items:start;text-align:left;padding:.5rem;border-radius:7px}.question-menu label:hover{background:var(--wash)}
        .question-menu input{min-width:0;margin:.2rem 0}.question-menu span{overflow-wrap:anywhere}.question-menu small{color:var(--muted);
        white-space:nowrap}.question-menu em{display:block;color:var(--muted);font-size:.72rem;font-style:normal}
        .selector-actions{display:flex;gap:.4rem;position:sticky;top:0;
        background:#fff;padding:.3rem 0}.response-meta{color:var(--muted);font-size:.78rem;padding:.55rem 1rem;
        display:flex;gap:.9rem;flex-wrap:wrap}.response-meta b{color:#475569;font-weight:700}
        border-top:1px solid #edf1f6;background:#fbfcfe}
        .hidden{display:none}.empty{text-align:center;padding:3rem}@media(max-width:700px){.stats{grid-template-columns:1fr}
        .analytics,.quality-groups{grid-template-columns:1fr 1fr}.toolbar{flex-wrap:wrap}.analysis-summary{display:none}}
        @media(max-width:480px){.analytics,.quality-groups,.numeric-summary{grid-template-columns:1fr}
        .distribution-row{grid-template-columns:minmax(90px,1fr) 1fr 42px}.distribution-row small{display:none}}
        @media print{.toolbar{display:none}
        body{background:#fff}header{background:#fff;color:#000;padding:1rem}.stats{margin-top:0}}</style></head><body>""",
        f"<header><div class='shell'><small>RESPONSE REPORT</small><h1>{html.escape(survey_name)}</h1>"
        "<p>Search, review, expand, or print individual survey responses.</p></div></header>",
        "<div class='shell stats'>"
        f"<div class='stat'><strong id='stat-responses'>{len(entities.responses):,}</strong><span>Responses</span></div>"
        f"<div class='stat'><strong id='stat-questions'>{len(response_questions):,}</strong><span>Response questions</span></div>"
        f"<div class='stat'><strong id='stat-answers'>{content_answer_count:,}</strong><span>Respondent answers</span></div></div>",
        "<main class='shell'><div class='survey-switcher'><label for='survey-select'>Survey</label>"
        f"<select id='survey-select'><option value='' data-responses='{response_count}' "
        f"data-finished='{finished_count}' data-questions='{len(response_questions)}' "
        f"data-answers='{content_answer_count}' data-unanswered='{len(unanswered_questions)}' "
        f"data-unused-fields='{len(unused_fields)}'>All surveys</option>{survey_options}</select></div>"
        "<nav><a href='#overview'>Overview</a>"
        "<a href='#question-analytics'>Question analytics</a>"
        "<a href='#by-responses'>By responses</a></nav>",
        "<section id='overview'><h2>Overview</h2><p class='section-intro'>Coverage, completion, "
        "and data-quality signals across this survey.</p><div class='analytics'>"
        f"<div class='analytic'><strong id='overview-finished'>{finished_count:,}</strong><span>Finished responses</span></div>"
        f"<div class='analytic'><strong id='overview-completion'>{(finished_count / response_count * 100 if response_count else 0):.0f}%</strong>"
        "<span>Completion rate</span></div>"
        f"<div class='analytic'><strong id='overview-unanswered'>{len(unanswered_questions):,}</strong><span>Unanswered questions</span></div>"
        f"<div class='analytic'><strong id='overview-unused-fields'>{len(unused_fields):,}</strong><span>Unused fields</span></div></div>",
        f"{''.join(quality_panels)}",
        "<div class='panel'><h3>Question coverage</h3><table><thead><tr><th>Question</th>"
        f"<th>Responses</th><th>Coverage</th></tr></thead><tbody>{''.join(coverage_rows)}</tbody></table></div>"
        "</section><section id='question-analytics'><h2>Question analytics</h2>"
        "<p class='section-intro'>Answer patterns summarized according to each question type. "
        "Expand a question to inspect its fields and distributions.</p>"
        f"{''.join(question_analytics)}</section><section id='by-responses'><h2>By responses</h2>"
        "<p class='section-intro'>Review individual answers and filter to the questions you need.</p>",
        "<div class='toolbar'><input id='search' type='search' "
        "placeholder='Search responses, questions, or answers…'><span id='count'></span>"
        "<div class='filter-wrap'><button id='question-toggle' type='button' aria-expanded='false'>"
        "Questions · <span id='selected-count'>All</span></button><div id='question-menu' "
        "class='question-menu' hidden>"
        "<div class='selector-actions'><button id='select-all' type='button'>Select all</button>"
        "<button id='clear-all' type='button'>Clear</button></div>"
        f"{''.join(question_choices)}</div></div>"
        "<button id='expand'>Expand all</button><button id='collapse'>Collapse</button></div>",
    ]
    for index, response in enumerate(entities.responses):
        key = (response["survey_id"], response["response_id"])
        response_survey_id = str(response["survey_id"])
        response_survey_name = str(
            survey_lookup.get(response_survey_id, {}).get("survey_name") or response_survey_id
        )
        response_answers = answers.get(key, [])
        search_terms = [str(response["response_id"])]
        rows = []
        metadata_values = []
        grouped_response_answers: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
        for answer in response_answers:
            q = questions.get((answer["survey_id"], answer["question_id"]), {})
            f = fields.get((answer["survey_id"], answer["question_id"], answer["field_id"]), {})
            label = q.get("question_text") or answer["question_id"]
            field_label = f.get("field_text")
            search_terms.extend((str(label), str(field_label or ""), str(answer["answer_text"])))
            question_key = (answer["survey_id"], answer["question_id"])
            if question_roles.get(question_key, "response") != "response":
                metadata_label = field_label or label
                metadata_values.append(
                    f"<span><b>{html.escape(str(metadata_label))}</b> "
                    f"{html.escape(str(answer['answer_text']))}</span>"
                )
                continue
            grouped_response_answers.setdefault(str(answer["question_id"]), []).append((answer, f))
        for question_id, grouped_answers in grouped_response_answers.items():
            first_answer = grouped_answers[0][0]
            q = questions.get((first_answer["survey_id"], question_id), {})
            label = q.get("question_text") or question_id
            question_type = str(q.get("question_type") or "").upper()
            type_label = {"MC": "Multiple choice", "TE": "Text entry"}.get(
                question_type, question_type.replace("_", " ").title()
            )
            block_name = str(q.get("block_name") or "")
            field_rows = []
            for answer, field_definition in grouped_answers:
                field_label = (
                    field_definition.get("field_text")
                    or field_definition.get("field_id")
                    or "Answer"
                )
                field_rows.append(
                    f"<div class='field-answer'><span class='field'>{html.escape(str(field_label))}</span>"
                    f"<span class='value'>{html.escape(str(answer['answer_text']))}</span></div>"
                )
            question_meta = " · ".join(
                item for item in (type_label, f"Block: {block_name}" if block_name else "") if item
            )
            rows.append(
                f"<div class='answer' data-question='"
                f"{html.escape(f'{response_survey_id}::{question_id}', quote=True)}'>"
                f"<div class='question-head'><span class='question'>{html.escape(str(label))}</span>"
                f"<span class='question-meta'>{html.escape(question_meta)}</span></div>"
                f"{''.join(field_rows)}</div>"
            )
        searchable = html.escape(" ".join(search_terms).casefold(), quote=True)
        metadata_parts = [
            value
            for value in (
                f"Recorded {response.get('recorded_at')}" if response.get("recorded_at") else "",
                f"Language {response.get('user_language')}"
                if response.get("user_language")
                else "",
                "Finished"
                if str(response.get("is_finished", "")).casefold() in {"true", "1"}
                else "",
            )
            if value
        ]
        metadata_values.insert(0, f"<span>{html.escape(' · '.join(metadata_parts))}</span>")
        if len(entities.surveys) > 1:
            metadata_values.insert(
                0, f"<span><b>Survey</b> {html.escape(response_survey_name)}</span>"
            )
        parts.append(
            f"<details class='respondent' data-survey='{html.escape(response_survey_id, quote=True)}' "
            f"data-total-answers='{len(rows)}' data-search='{searchable}'{' open' if index == 0 else ''}>"
            f"<summary><span class='identity'>{html.escape(str(response['response_id']))}</span>"
            f"<span class='badge'>{len(rows)} answers</span></summary>"
            f"<div class='response-meta'>{''.join(metadata_values)}</div>"
            f"<div class='answers'>{''.join(rows)}"
            "<div class='no-selected' hidden>No selected questions were answered in this response.</div>"
            "</div></details>"
        )
    parts.append(
        """<div id='empty' class='empty hidden'>No matching responses.</div></section></main><script>
        const cards=[...document.querySelectorAll('.respondent')],search=document.querySelector('#search'),
        count=document.querySelector('#count'),empty=document.querySelector('#empty'),
        choices=[...document.querySelectorAll('.question-choice')],
        toggle=document.querySelector('#question-toggle'),menu=document.querySelector('#question-menu'),
        selectedCount=document.querySelector('#selected-count'),surveySelect=document.querySelector('#survey-select');
        function filter(){const term=search.value.trim().toLowerCase(),survey=surveySelect.value,
        activeChoices=choices.filter(c=>!survey||c.closest('label').dataset.survey===survey),selected=new Set(
        activeChoices.filter(c=>c.checked).map(c=>c.value));let visible=0;
        choices.forEach(c=>c.closest('label').hidden=!!survey&&c.closest('label').dataset.survey!==survey);
        document.querySelectorAll('.question-analysis,.quality').forEach(item=>
        item.hidden=!!survey&&item.dataset.survey!==survey);
        document.querySelectorAll('#overview tr[data-survey]').forEach(item=>
        item.hidden=!!survey&&item.dataset.survey!==survey);
        cards.forEach(card=>{const answerRows=[...card.querySelectorAll('.answer')];let shownAnswers=0;
        answerRows.forEach(row=>{const show=selected.has(row.dataset.question);
        row.hidden=!show;if(show)shownAnswers+=1;});
        card.querySelector('.no-selected').hidden=shownAnswers>0;
        card.querySelector('.badge').textContent=shownAnswers+' '+(shownAnswers===1?'answer':'answers');
        const show=(!survey||card.dataset.survey===survey)&&(!term||card.dataset.search.includes(term));
        card.hidden=!show;if(show)visible+=1;});
        const eligibleCards=cards.filter(card=>!survey||card.dataset.survey===survey),
        metrics=surveySelect.selectedOptions[0].dataset,responses=Number(metrics.responses||0),
        finished=Number(metrics.finished||0);
        count.textContent=visible+' of '+eligibleCards.length;empty.classList.toggle('hidden',visible>0);
        selectedCount.textContent=selected.size===activeChoices.length?'All':selected.size+' selected';
        document.querySelector('#stat-responses').textContent=responses.toLocaleString();
        document.querySelector('#stat-questions').textContent=Number(metrics.questions||0).toLocaleString();
        document.querySelector('#stat-answers').textContent=Number(metrics.answers||0).toLocaleString();
        document.querySelector('#overview-finished').textContent=finished.toLocaleString();
        document.querySelector('#overview-completion').textContent=(responses?Math.round(finished/responses*100):0)+'%';
        document.querySelector('#overview-unanswered').textContent=Number(metrics.unanswered||0).toLocaleString();
        document.querySelector('#overview-unused-fields').textContent=Number(metrics.unusedFields||0).toLocaleString();}
        search.addEventListener('input',filter);
        surveySelect.addEventListener('change',filter);
        choices.forEach(choice=>choice.addEventListener('change',filter));
        toggle.onclick=event=>{event.stopPropagation();const opening=menu.hidden;
        menu.hidden=!opening;toggle.setAttribute('aria-expanded',String(opening));};
        menu.onclick=event=>event.stopPropagation();
        document.addEventListener('click',()=>{menu.hidden=true;
        toggle.setAttribute('aria-expanded','false');});
        function visibleChoices(){const survey=surveySelect.value;return choices.filter(c=>
        !survey||c.closest('label').dataset.survey===survey);}
        document.querySelector('#select-all').onclick=()=>{visibleChoices().forEach(c=>c.checked=true);filter();};
        document.querySelector('#clear-all').onclick=()=>{visibleChoices().forEach(c=>c.checked=false);filter();};
        document.querySelector('#expand').onclick=()=>cards.filter(c=>!c.classList.contains('hidden'))
        .forEach(c=>c.open=true);
        document.querySelector('#collapse').onclick=()=>cards.forEach(c=>c.open=false);
        filter();</script></body></html>"""
    )
    Path(output).write_text("".join(parts), encoding="utf-8")
