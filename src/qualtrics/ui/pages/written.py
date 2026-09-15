"""Prepare text-answer cards and their question filter choices."""

from __future__ import annotations

import json
from dataclasses import dataclass

from ..._common.models.comment_translations import source_text_hash
from ..._common.models.comments import is_comment_answer
from ..components.field_labels import display_field_label
from ..context import ReportContext
from ..report_languages import response_language
from ..templating import render_template, trusted_html


@dataclass(frozen=True)
class WrittenAnswer:
    id: str
    answer_id: str
    survey_id: str
    user_language: str
    question_id: str
    token: str
    response_target: str
    field_id: str
    label: str
    metadata: str
    survey_label: str
    field_label: str
    value: str
    response_label: str


@dataclass(frozen=True)
class WrittenQuestion:
    token: str
    label: str
    survey_id: str
    question_id: str


def render_written_answers(context: ReportContext) -> str:
    analysis = context.analysis
    written_answers: list[WrittenAnswer] = []
    written_questions: dict[str, WrittenQuestion] = {}
    source_texts: dict[str, str] = {}
    for response_index, response in enumerate(context.entities.responses, 1):
        for answer in analysis.answers.get((response["survey_id"], response["response_id"]), []):
            key = (answer["survey_id"], answer["question_id"])
            if key not in analysis.response_questions:
                continue
            question = analysis.questions.get(key, {})
            field = analysis.fields.get((*key, answer["field_id"]), {})
            if not is_comment_answer(question, field, answer):
                continue
            survey_id = str(response["survey_id"])
            answer_id = str(answer.get("response_answer_id") or "")
            label = str(question.get("question_text") or answer["question_id"])
            token = f"{survey_id}::{question.get('question_external_id') or answer['question_id']}"
            written_questions[token] = WrittenQuestion(token, label, survey_id, str(answer["question_id"]))
            field_label = display_field_label(field, question, context.answer_options)
            metadata = " · ".join(
                item
                for item in (
                    str(analysis.survey_lookup.get(survey_id, {}).get("survey_name") or survey_id),
                    field_label,
                )
                if item
            )
            written_answers.append(
                WrittenAnswer(
                    id=f"written-{len(written_answers) + 1}",
                    answer_id=answer_id,
                    survey_id=survey_id,
                    user_language=response_language(response),
                    question_id=str(answer["question_id"]),
                    token=token,
                    response_target=f"response-{response_index}",
                    field_id=str(answer["field_id"]),
                    label=label,
                    metadata=metadata,
                    survey_label=str(analysis.survey_lookup.get(survey_id, {}).get("survey_name") or survey_id),
                    field_label=field_label,
                    value=str(answer["answer_text"]),
                    response_label=str(response.get("response_external_id") or response["response_id"]),
                )
            )
            if answer_id:
                source_texts[answer_id] = str(answer["answer_text"])
    translations: dict[str, dict[str, dict[str, str | bool | None]]] = {}
    for row in context.entities.comment_translations:
        answer_id = str(row.get("response_answer_id"))
        if answer_id not in source_texts:
            continue
        current = row.get("source_text_hash") == source_text_hash(source_texts[answer_id])
        target = str(row.get("target_language"))
        translations.setdefault(answer_id, {})[target] = {
            "text": str(row["translated_text"]) if current else None,
            "current": current,
        }
    payload = json.dumps(translations, ensure_ascii=True, separators=(",", ":")).replace("<", "\\u003c")
    return render_template(
        "pages/written.html.jinja",
        answers=written_answers,
        questions=tuple(written_questions.values()),
        translation_payload=trusted_html(payload),
    )
