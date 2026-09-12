"""Prepare respondent metadata and grouped answer values without building markup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..._common.models.response_columns import read_source_columns
from ..components.controls import render_question_choices
from ..components.field_labels import display_field_label
from ..context import ReportContext
from ..templating import render_template, trusted_html

_BROWSER_LABELS = {
    "browser": "Browser",
    "browser_version": "Version",
    "operating_system": "Operating System",
    "screen_resolution": "Resolution",
    "user_agent": "User Agent",
}


@dataclass(frozen=True)
class MetadataValue:
    label: str
    value: str


@dataclass(frozen=True)
class ResponseProperty:
    label: str
    source: str
    value: str


@dataclass(frozen=True)
class FieldAnswer:
    id: str
    label: str
    value: str
    text: bool


@dataclass(frozen=True)
class ResponseQuestion:
    token: str
    label: str
    metadata: str
    fields: tuple[FieldAnswer, ...]


@dataclass(frozen=True)
class ResponseCard:
    id: str
    survey_id: str
    label: str
    searchable: str
    metadata: tuple[MetadataValue, ...]
    properties: tuple[ResponseProperty, ...]
    questions: tuple[ResponseQuestion, ...]
    open: bool


def render_responses(context: ReportContext) -> str:
    analysis = context.analysis
    source_columns = {str(row["survey_id"]): read_source_columns(row) for row in context.entities.surveys}
    cards = []
    for index, response in enumerate(context.entities.responses):
        key = (response["survey_id"], response["response_id"])
        sid = str(response["survey_id"])
        survey = analysis.survey_lookup.get(sid, {})
        survey_name = str(survey.get("survey_name") or sid)
        properties = []
        property_columns = set()
        for column in source_columns.get(sid, []):
            if column.get("storage_table") != "responses":
                continue
            storage = str(column.get("storage_column") or "")
            if not storage or storage in property_columns:
                continue
            property_columns.add(storage)
            value = response.get(storage)
            if value is None or value == "":
                continue
            source = str(column.get("source_column") or storage)
            properties.append(
                ResponseProperty(_BROWSER_LABELS.get(storage, str(column.get("label") or source)), source, str(value))
            )
        stable_metadata = [
            (label, response.get(storage))
            for storage, label in _BROWSER_LABELS.items()
            if storage not in property_columns
        ]
        label = str(response.get("response_external_id") or response["response_id"])
        search_terms = [label, *(f"{label} {value}" for label, value in stable_metadata if value is not None)]
        metadata = [
            MetadataValue(label, str(value)) for label, value in stable_metadata if value is not None and value != ""
        ]
        grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
        for answer in analysis.answers.get(key, []):
            qkey = (answer["survey_id"], answer["question_id"])
            question = analysis.questions.get(qkey, {})
            field = analysis.fields.get((*qkey, answer["field_id"]), {})
            question_label = question.get("question_text") or answer["question_id"]
            field_label = field.get("field_text")
            search_terms.extend((str(question_label), str(field_label or ""), str(answer["answer_text"])))
            if analysis.question_roles.get(qkey, "response") != "response":
                metadata.append(MetadataValue(str(field_label or question_label), str(answer["answer_text"])))
                continue
            grouped.setdefault(str(answer["question_id"]), []).append((answer, field))
        rows = []
        for qid, grouped_answers in grouped.items():
            question = analysis.questions.get((grouped_answers[0][0]["survey_id"], qid), {})
            external_id = str(question.get("question_external_id") or qid)
            question_type = str(question.get("question_type") or "").upper()
            type_label = {"MC": "Multiple choice", "TE": "Text entry"}.get(
                question_type, question_type.replace("_", " ").title()
            )
            block_name = str(question.get("block_name") or "")
            fields = tuple(
                FieldAnswer(
                    str(answer["field_id"]),
                    display_field_label(field, question, context.answer_options),
                    str(answer["answer_text"]),
                    bool(field.get("is_text_field")),
                )
                for answer, field in grouped_answers
            )
            question_meta = " · ".join(
                item for item in (type_label, f"Block: {block_name}" if block_name else "") if item
            )
            rows.append(
                ResponseQuestion(
                    f"{sid}::{external_id}", str(question.get("question_text") or qid), question_meta, fields
                )
            )
        response_meta = " · ".join(
            value
            for value in (
                f"Recorded {response.get('recorded_at')}" if response.get("recorded_at") else "",
                f"Language {response.get('user_language')}" if response.get("user_language") else "",
                "Finished" if str(response.get("is_finished", "")).casefold() in {"true", "1"} else "",
            )
            if value
        )
        metadata.insert(0, MetadataValue("", response_meta))
        if len(context.entities.surveys) > 1:
            metadata.insert(0, MetadataValue("Survey", survey_name))
        cards.append(
            ResponseCard(
                id=f"response-{index + 1}",
                survey_id=sid,
                label=label,
                searchable=" ".join(search_terms).casefold(),
                metadata=tuple(metadata),
                properties=tuple(properties),
                questions=tuple(rows),
                open=index == 0,
            )
        )
    return render_template(
        "pages/responses.html.jinja", cards=cards, question_choices=trusted_html(render_question_choices(context))
    )
