"""Prepare survey and question scope choices for reusable controls."""

from dataclasses import dataclass

from ..context import ReportContext
from ..templating import render_template


@dataclass(frozen=True)
class SurveyChoice:
    id: str
    label: str
    responses: int
    finished: int
    questions: int
    answers: int
    unanswered: int
    unused_fields: int


@dataclass(frozen=True)
class QuestionChoice:
    survey_id: str
    token: str
    label: str
    survey_label: str
    count: int
    total: int


def render_survey_choices(context: ReportContext) -> str:
    analysis = context.analysis
    choices = []
    for item in context.entities.surveys:
        sid = str(item["survey_id"])
        choices.append(
            SurveyChoice(
                sid,
                str(item.get("survey_name") or sid),
                analysis.survey_response_counts.get(sid, 0),
                analysis.survey_finished_counts.get(sid, 0),
                analysis.survey_question_counts.get(sid, 0),
                analysis.survey_answer_counts.get(sid, 0),
                analysis.survey_unanswered_counts.get(sid, 0),
                analysis.survey_unused_field_counts.get(sid, 0),
            )
        )
    return render_template("components/survey_choices.html.jinja", choices=choices)


def render_question_choices(context: ReportContext) -> str:
    analysis = context.analysis
    choices = []
    for key, question in analysis.response_questions.items():
        sid = str(key[0])
        qid = str(question["question_id"])
        external_id = str(question.get("question_external_id") or qid)
        choices.append(
            QuestionChoice(
                sid,
                f"{sid}::{external_id}",
                str(question.get("question_text") or qid),
                str(analysis.survey_lookup.get(sid, {}).get("survey_name") or sid),
                len(analysis.question_responses.get(key, set())),
                analysis.survey_response_counts.get(sid, 0),
            )
        )
    return render_template(
        "components/question_choices.html.jinja", choices=choices, multiple_surveys=len(context.entities.surveys) > 1
    )
