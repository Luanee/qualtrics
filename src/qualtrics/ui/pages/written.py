"""Prepare text-answer cards and their question filter choices."""

from __future__ import annotations

from dataclasses import dataclass

from ..components.field_labels import display_field_label
from ..context import ReportContext
from ..insights import field_value_type
from ..templating import render_template


@dataclass(frozen=True)
class WrittenAnswer:
    id: str
    survey_id: str
    token: str
    response_target: str
    field_id: str
    label: str
    metadata: str
    value: str
    response_label: str


@dataclass(frozen=True)
class WrittenQuestion:
    token: str
    label: str
    survey_id: str


def render_written_answers(context: ReportContext) -> str:
    analysis = context.analysis
    written_answers: list[WrittenAnswer] = []
    written_questions: dict[str, WrittenQuestion] = {}
    for response_index, response in enumerate(context.entities.responses, 1):
        for answer in analysis.answers.get((response["survey_id"], response["response_id"]), []):
            key = (answer["survey_id"], answer["question_id"])
            if key not in analysis.response_questions:
                continue
            question = analysis.questions.get(key, {})
            field = analysis.fields.get((*key, answer["field_id"]), {})
            if field_value_type(question, field) != "text":
                continue
            survey_id = str(response["survey_id"])
            label = str(question.get("question_text") or answer["question_id"])
            token = f"{survey_id}::{question.get('question_external_id') or answer['question_id']}"
            written_questions[token] = WrittenQuestion(token, label, survey_id)
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
                    survey_id=survey_id,
                    token=token,
                    response_target=f"response-{response_index}",
                    field_id=str(answer["field_id"]),
                    label=label,
                    metadata=metadata,
                    value=str(answer["answer_text"]),
                    response_label=str(response.get("response_external_id") or response["response_id"]),
                )
            )
    return render_template(
        "pages/written.html.jinja", answers=written_answers, questions=tuple(written_questions.values())
    )
