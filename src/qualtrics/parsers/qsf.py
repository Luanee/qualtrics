from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
        (element.get("Payload", {}) for element in data.get("SurveyElements", []) if element.get("Element") == "BL"),
        {},
    )
    for block_order, block in enumerate(block_elements.values(), start=1):
        if block.get("Type") == "Trash":
            continue
        section_id = block.get("ID")
        sections.append({
            "section_id": section_id,
            "section_name": block.get("Description"),
            "section_type": block.get("Type"),
            "section_order": block_order,
        })
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
