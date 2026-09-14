from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .columns import embedded_field_names
from .flow import _items, _unwrap, extract_flow_definition


def _qsf(
    path: Path | None,
    *,
    flow_path: Path | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
]:
    if not path and not flow_path:
        return {}, {}, {}, []
    document = json.loads(path.read_text(encoding="utf-8")) if path else {}
    data = dict(_unwrap(document))
    raw_entry = data.get("SurveyEntry")
    entry = (
        dict(raw_entry)
        if isinstance(raw_entry, dict)
        else {
            key: data.get(key)
            for key in ("SurveyID", "SurveyName", "SurveyStatus", "SurveyLanguage")
            if data.get(key) is not None
        }
    )
    # SurveyDefinition.model_dump_json() uses snake_case wrapper fields.
    entry.setdefault("SurveyID", document.get("survey_id"))
    entry.setdefault("SurveyName", document.get("survey_name"))
    entry["_source_embedded_fields"] = sorted(embedded_field_names(data))
    if flow_path:
        try:
            flow_document = json.loads(flow_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid survey flow JSON in {flow_path}: {exc.msg}") from exc
        if not isinstance(flow_document, dict):
            raise ValueError(f"Invalid survey flow in {flow_path}: expected an object")
        flow_definition = extract_flow_definition(flow_document)
        if flow_definition is None:
            raise ValueError(f"Invalid survey flow in {flow_path}: no Flow or root was found")
        if path:
            metadata_source = dict(data)
            metadata_source["Flow"] = []
            metadata_definition = extract_flow_definition(metadata_source)
            if metadata_definition is not None:
                flow_definition["blocks"].update(metadata_definition["blocks"])
                flow_definition["questions"].update(metadata_definition["questions"])
    else:
        flow_definition = extract_flow_definition(data)
    if flow_definition is not None:
        entry["flow_definition_json"] = json.dumps(
            flow_definition,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    questions = {}
    for element in data.get("SurveyElements", []):
        if element.get("Element") == "SQ":
            payload = element.get("Payload", {})
            qid = payload.get("QuestionID") or element.get("PrimaryAttribute")
            if qid:
                questions[str(qid)] = payload
    direct_questions = data.get("Questions", {})
    if isinstance(direct_questions, dict):
        questions.update(direct_questions)
    options = data.get("SurveyOptions")
    options = options if isinstance(options, dict) else {}
    base_language = entry.get("SurveyLanguage") or options.get("SurveyLanguage")
    entry["SurveyLanguage"] = str(base_language) if base_language else None
    available = options.get("AvailableLanguages") or data.get("AvailableLanguages") or {}
    available_codes = (
        available.keys() if isinstance(available, dict) else available if isinstance(available, list) else []
    )
    available_languages = list(dict.fromkeys(str(code) for code in available_codes if str(code).strip()))
    translated_codes = {
        str(code)
        for question in questions.values()
        if isinstance(question, dict)
        for code in (question.get("Language") or {})
        if str(code).strip()
    }
    all_languages = list(
        dict.fromkeys([
            *([str(base_language)] if base_language else []),
            *available_languages,
            *sorted(translated_codes),
        ])
    )
    entry["_languages"] = {
        "base_language": entry["SurveyLanguage"],
        "available_languages": available_languages,
        "all_languages": all_languages,
    }
    question_blocks = {}
    sections = []
    element_blocks = next(
        (element.get("Payload", {}) for element in data.get("SurveyElements", []) if element.get("Element") == "BL"),
        {},
    )
    direct_blocks = data.get("Blocks", {})
    mixed_containers = isinstance(element_blocks, dict) != isinstance(direct_blocks, dict)
    block_elements = {}
    for source_index, source in enumerate((element_blocks, direct_blocks)):
        for fallback_id, block in _items(source):
            # Retain mapping-key merge precedence for existing dictionary inputs.
            # Anonymous list entries retain their ordering position without
            # becoming source block IDs or entity sections.
            key = fallback_id if fallback_id is not None else block.get("ID") or object()
            if key:
                if source_index == 1 and mixed_containers and key not in block_elements:
                    # Mixed containers can describe the same block under a
                    # positional mapping key and its native ID. Replace the
                    # earlier value in place so section order and grain hold.
                    native_id = block.get("ID") or fallback_id
                    if native_id:
                        for previous_key, (previous_fallback, previous_block) in block_elements.items():
                            if str(previous_block.get("ID") or previous_fallback) == str(native_id):
                                key = previous_key
                                break
                block_elements[key] = (fallback_id, block)
    for block_order, (fallback_id, block) in enumerate(block_elements.values(), start=1):
        if block.get("Type") == "Trash":
            continue
        section_id = block.get("ID") or fallback_id
        if not section_id:
            continue
        sections.append({
            "section_id": section_id,
            "section_name": block.get("Description"),
            "section_type": block.get("Type"),
            "section_order": block_order,
        })
        for question_order, element in enumerate(block.get("BlockElements", []), start=1):
            if not isinstance(element, dict):
                continue
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
