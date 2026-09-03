from __future__ import annotations

import contextlib
import csv
import json
from collections.abc import Sequence
from io import TextIOWrapper
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from ..models.entities import EntitySet
from ..models.entity_set import merge_entity_sets
from ..models.identity import entity_id, semantic_id
from ..models.question_types import resolve_question_type
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

RESPONSE_METADATA_COLUMNS = {
    "Status": "status",
    "IPAddress": "ip_address",
    "Progress": "progress",
    "Duration (in seconds)": "duration_seconds",
    "RecipientLastName": "recipient_last_name",
    "RecipientFirstName": "recipient_first_name",
    "RecipientEmail": "recipient_email",
    "ExternalReference": "external_reference",
    "DistributionChannel": "distribution_channel",
}

BROWSER_METADATA_FIELDS = {
    "BROWSER": "browser",
    "VERSION": "browser_version",
    "OS": "operating_system",
    "RESOLUTION": "screen_resolution",
    "USERAGENT": "user_agent",
}


def _apply_identity_contract(entities: EntitySet) -> None:
    sid = str(entities.surveys[0]["survey_id"])
    section_ids: dict[str, str] = {}
    for section in entities.sections:
        external_id = str(section.get("section_id") or f"section-{section.get('section_order', 0)}")
        internal_id = entity_id("section", sid, external_id)
        section_ids[external_id] = internal_id
        section["section_external_id"] = external_id
        section["section_id"] = internal_id

    options_by_question: dict[str, list[dict[str, object]]] = {}
    for option in entities.answer_options:
        options_by_question.setdefault(str(option["question_id"]), []).append(option)

    question_ids: dict[str, str] = {}
    catalog_ids: dict[str, str] = {}
    catalog_rows: dict[str, dict[str, object]] = {}
    for question in entities.questions:
        external_id = str(question["question_id"])
        resolved = resolve_question_type(
            question.get("question_type"), question.get("selector"), question.get("sub_selector")
        )
        content = {
            "text": question.get("question_text"),
            "type": resolved.canonical_question_type,
            "role": question.get("question_role"),
            "answers": [item.get("answer_text") for item in options_by_question.get(external_id, [])],
        }
        catalog_id = semantic_id("question", content)
        internal_id = entity_id("question", sid, external_id)
        question_ids[external_id] = internal_id
        catalog_ids[external_id] = catalog_id
        question["question_external_id"] = external_id
        question["question_id"] = internal_id
        question["question_catalog_id"] = catalog_id
        question["canonical_question_type"] = resolved.canonical_question_type
        question["answer_value_type"] = resolved.answer_value_type
        if question.get("section_id") is not None:
            question["section_external_id"] = str(question["section_id"])
            question["section_id"] = section_ids.get(str(question["section_id"]))
        catalog_rows[catalog_id] = {
            "question_catalog_id": catalog_id,
            "question_text": question.get("question_text"),
            "normalized_question_content": content,
            "canonical_question_type": resolved.canonical_question_type,
        }
    entities.question_catalog = list(catalog_rows.values())

    for option in entities.answer_options:
        external_question_id = str(option["question_id"])
        external_id = str(option["answer_id"])
        option["question_external_id"] = external_question_id
        option["question_id"] = question_ids[external_question_id]
        option["answer_external_id"] = external_id
        option["answer_option_id"] = entity_id("answer-option", option["question_id"], external_id)
        option["answer_option_catalog_id"] = semantic_id(
            "answer-option", {"question": catalog_ids[external_question_id], "text": option.get("answer_text")}
        )

    field_ids: dict[str, str] = {}
    field_catalog_rows: dict[str, dict[str, object]] = {}
    for field in entities.question_fields:
        external_question_id = str(field["question_id"])
        external_id = str(field["field_id"])
        question_id = question_ids[external_question_id]
        stable_source = field.get("source_import_id") or external_id
        internal_id = entity_id("question-field", question_id, stable_source)
        value_type = (
            "text"
            if field.get("is_text_field")
            else next(item["answer_value_type"] for item in entities.questions if item["question_id"] == question_id)
        )
        catalog_id = semantic_id(
            "question-field",
            {"question": catalog_ids[external_question_id], "text": field.get("field_text"), "value_type": value_type},
        )
        field_ids[external_id] = internal_id
        field["question_external_id"] = external_question_id
        field["question_id"] = question_id
        field["field_external_id"] = external_id
        field["import_external_id"] = field.pop("source_import_id", None)
        field["question_field_id"] = internal_id
        field["field_id"] = internal_id
        field["question_catalog_id"] = catalog_ids[external_question_id]
        field["question_field_catalog_id"] = catalog_id
        field["answer_value_type"] = value_type
        field["field_role"] = "text" if field.get("is_text_field") else "answer"
        field_catalog_rows[catalog_id] = {
            "question_field_catalog_id": catalog_id,
            "question_catalog_id": catalog_ids[external_question_id],
            "field_text": field.get("field_text"),
            "normalized_field_content": {
                "text": field.get("field_text"),
                "value_type": value_type,
            },
        }
    entities.question_field_catalog = list(field_catalog_rows.values())

    response_ids: dict[str, str] = {}
    for response in entities.responses:
        external_id = str(response["response_id"])
        internal_id = entity_id("response", sid, external_id)
        response_ids[external_id] = internal_id
        response["response_external_id"] = external_id
        response["response_id"] = internal_id

    for answer in entities.response_answers:
        external_response_id = str(answer["response_id"])
        external_question_id = str(answer["question_id"])
        external_field_id = str(answer["field_id"])
        answer["response_external_id"] = external_response_id
        answer["response_id"] = response_ids[external_response_id]
        answer["question_external_id"] = external_question_id
        answer["question_id"] = question_ids[external_question_id]
        answer["field_external_id"] = external_field_id
        answer["question_field_id"] = field_ids[external_field_id]
        answer["field_id"] = field_ids[external_field_id]
        answer["question_catalog_id"] = catalog_ids[external_question_id]
        field = next(
            item for item in entities.question_fields if item["question_field_id"] == field_ids[external_field_id]
        )
        answer["question_field_catalog_id"] = field["question_field_catalog_id"]
        answer["answer_value_type"] = field["answer_value_type"]
        answer["response_answer_id"] = entity_id("response-answer", answer["response_id"], answer["question_field_id"])


def _optional_value(value: str | None) -> str | None:
    return value if value is not None and value.strip() else None


def _choice_items(definition: dict[str, object]) -> list[tuple[str, object]]:
    choices = definition.get("Choices") or {}
    if isinstance(choices, dict):
        return [(str(option_id), option) for option_id, option in choices.items()]
    if isinstance(choices, list):
        choice_order = definition.get("ChoiceOrder") or []
        option_ids = (
            choice_order
            if isinstance(choice_order, list) and len(choice_order) == len(choices)
            else range(1, len(choices) + 1)
        )
        return [(str(option_id), option) for option_id, option in zip(option_ids, choices, strict=True)]
    return []


def _read_response_rows(source_path: Path) -> list[list[str]]:
    if source_path.suffix.casefold() != ".zip":
        with source_path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.reader(handle))

    try:
        with ZipFile(source_path) as archive:
            csv_members = [
                member
                for member in archive.infolist()
                if not member.is_dir()
                and Path(member.filename).suffix.casefold() == ".csv"
                and "__MACOSX" not in Path(member.filename).parts
            ]
            if len(csv_members) != 1:
                raise ValueError(
                    f"Qualtrics response ZIP must contain exactly one CSV; found {len(csv_members)} in {source_path}"
                )
            with (
                archive.open(csv_members[0]) as raw_handle,
                TextIOWrapper(raw_handle, encoding="utf-8-sig", newline="") as text_handle,
            ):
                return list(csv.reader(text_handle))
    except BadZipFile as error:
        raise ValueError(f"Invalid Qualtrics response ZIP: {source_path}") from error


def _parse_survey_file(
    source_path: str | Path,
    qsf_path: str | Path | None = None,
    survey_id: str | None = None,
) -> EntitySet:
    source_path = Path(source_path)
    qsf_path = Path(qsf_path) if qsf_path else _matching_definition(source_path)
    rows = _read_response_rows(source_path)
    if len(rows) < 2:
        raise ValueError("Qualtrics CSV must contain column and question-text rows")
    columns, headers = rows[0], rows[1]
    metadata = rows[2] if len(rows) > 2 else [""] * len(columns)
    has_import = any("ImportId" in value for value in metadata)
    entry, qsf_questions, question_blocks, sections = _qsf(qsf_path)
    sid = survey_id or entry.get("SurveyID") or source_path.stem
    entities = EntitySet(
        surveys=[
            {
                "survey_id": sid,
                "survey_name": entry.get("SurveyName") or source_path.stem,
                "survey_status": entry.get("SurveyStatus"),
                "default_language": entry.get("SurveyLanguage"),
            }
        ]
    )
    entities.sections = [{"survey_id": sid, **section} for section in sections]
    field_specs: list[tuple[int, str, str, str]] = []
    grouped_headers: dict[str, list[str]] = {}
    for index, (column, header, raw_meta) in enumerate(zip(columns, headers, metadata, strict=True)):
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
            question_import_ids = [item[3] for item in field_specs if _qid(item[3] or item[1]) == question_id]
            role = _question_role(definition, question_import_ids)
            entities.questions.append({
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
            })
            # Meta Info and Timing choices describe captured fields, not respondent
            # answer options. Treating them as options creates false "unused" alerts.
            for option_id, option in _choice_items(definition) if role == "response" else []:
                entities.answer_options.append({
                    "survey_id": sid,
                    "question_id": question_id,
                    "answer_id": str(option_id),
                    "answer_text": _clean(option.get("Display") if isinstance(option, dict) else option),
                })
            seen.add(question_id)
        suffix = (import_id.replace(question_id, "", 1).strip("_") or None) if import_id else None
        field_text = _field_text(header, question_text, column, suffix)
        entities.question_fields.append({
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
        })
    field_map = {row["field_id"]: row["question_id"] for row in entities.question_fields}
    question_roles = {row["question_id"]: row["question_role"] for row in entities.questions}
    browser_field_map = {
        row["field_id"]: BROWSER_METADATA_FIELDS[row["source_field_suffix"]]
        for row in entities.question_fields
        if question_roles.get(row["question_id"]) == "metadata"
        and row.get("source_field_suffix") in BROWSER_METADATA_FIELDS
    }
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
        response = {
            "survey_id": sid,
            "response_id": response_id,
            "started_at": _optional_value(record.get("StartDate")),
            "ended_at": _optional_value(record.get("EndDate")),
            "recorded_at": _optional_value(record.get("RecordedDate")),
            "is_finished": _optional_value(record.get("Finished")),
            "user_language": _optional_value(record.get("UserLanguage")),
            **{target: _optional_value(record.get(source)) for source, target in RESPONSE_METADATA_COLUMNS.items()},
            **dict.fromkeys(BROWSER_METADATA_FIELDS.values()),
        }
        for column, target in browser_field_map.items():
            value = _optional_value(record.get(column))
            if value and not response[target]:
                response[target] = value
        entities.responses.append(response)
        for column, question_id in field_map.items():
            if column in browser_field_map:
                continue
            value = record.get(column, "")
            if value:
                entities.response_answers.append({
                    "survey_id": sid,
                    "response_id": response_id,
                    "question_id": question_id,
                    "field_id": column,
                    "user_language": record.get("UserLanguage"),
                    "answer_text": value,
                })
    _apply_identity_contract(entities)
    return entities


def parse_survey(
    source_path: str | Path,
    qsf_path: str | Path | None = None,
    survey_id: str | None = None,
) -> EntitySet:
    """Parse one CSV/ZIP or merge every survey matched by a wildcard path."""
    source_files = _expand_paths([source_path])
    definition_files = _expand_paths([qsf_path]) if qsf_path else []
    if len(source_files) == 1 and len(definition_files) <= 1:
        return _parse_survey_file(
            source_files[0],
            definition_files[0] if definition_files else None,
            survey_id=survey_id,
        )
    if survey_id:
        raise ValueError("survey_id cannot be forced when a wildcard matches multiple survey files")
    return parse_surveys(source_files, definition_files or None)


def parse_surveys(
    source_paths: Sequence[str | Path],
    qsf_paths: Sequence[str | Path] | None = None,
) -> EntitySet:
    """Parse multiple CSV-or-ZIP/QSF pairs into one entity collection."""
    source_files = _expand_paths(source_paths)
    qsf_files = _expand_paths(qsf_paths or [])
    if qsf_files and len(qsf_files) not in {1, len(source_files)}:
        raise ValueError("Provide no QSF files, one QSF for one survey, or one QSF per survey")
    if len(qsf_files) == 1 and len(source_files) > 1:
        raise ValueError("A single QSF cannot be applied to multiple survey files")
    parsed = [
        _parse_survey_file(
            source_path,
            qsf_files[index] if qsf_files else None,
        )
        for index, source_path in enumerate(source_files)
    ]
    return merge_entity_sets(parsed)
