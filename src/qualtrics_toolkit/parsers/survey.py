from __future__ import annotations

import contextlib
import csv
import json
from collections.abc import Sequence
from pathlib import Path

from ..models.entities import EntitySet
from ..models.entity_set import merge_entity_sets
from .identity import _clean, _field_text, _hash, _qid, _question_role
from .paths import _expand_paths
from .qsf import _matching_definition, _qsf

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
