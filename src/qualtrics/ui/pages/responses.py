"""Prepare respondent metadata and grouped answer values without building markup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..components.controls import render_question_choices
from ..components.field_labels import display_field_label
from ..context import ReportContext
from ..templating import render_template, trusted_html


@dataclass(frozen=True)
class MetadataValue:
    label: str
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
    questions: tuple[ResponseQuestion, ...]
    open: bool


def render_responses(context: ReportContext) -> str:
    analysis = context.analysis
    cards = []
    for index, response in enumerate(context.entities.responses):
        key = (response["survey_id"], response["response_id"])
        sid = str(response["survey_id"])
        survey_name = str(analysis.survey_lookup.get(sid, {}).get("survey_name") or sid)
        stable_metadata = [
            ("Browser", response.get("browser")),
            ("Version", response.get("browser_version")),
            ("Operating System", response.get("operating_system")),
            ("Resolution", response.get("screen_resolution")),
            ("User Agent", response.get("user_agent")),
        ]
        label = str(response.get("response_external_id") or response["response_id"])
        search_terms = [label, *(str(value) for _, value in stable_metadata if value)]
        metadata = [MetadataValue(label, str(value)) for label, value in stable_metadata if value]
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
                questions=tuple(rows),
                open=index == 0,
            )
        )
    return render_template(
        "pages/responses.html.jinja", cards=cards, question_choices=trusted_html(render_question_choices(context))
    )
