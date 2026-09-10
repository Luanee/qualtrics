from __future__ import annotations

import re
from typing import Any


def _normalized_label(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def display_field_label(
    field: dict[str, Any],
    question: dict[str, Any],
    answer_options: dict[tuple[str, str, str], dict[str, Any]],
) -> str:
    label = str(field.get("field_text") or field.get("field_id") or "Answer")
    question_text = str(question.get("question_text") or "")
    if not field.get("is_text_field"):
        if _normalized_label(label) == _normalized_label(question_text):
            return ""
        return label

    suffix = str(field.get("source_field_suffix") or "")
    option_match = re.fullmatch(r"(.+)_TEXT", suffix, flags=re.IGNORECASE)
    if option_match:
        option = answer_options.get((str(field.get("survey_id")), str(field.get("question_id")), option_match.group(1)))
        if option and option.get("answer_text"):
            label = str(option["answer_text"])
    label = re.sub(r"\s*-\s*Text\s*$", "", label, flags=re.IGNORECASE).strip()
    if not label or _normalized_label(label) == _normalized_label(question_text):
        return "Written response"
    return label
