"""Precompute independent respondent cohorts and definition-language labels."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .._common.models.entities import EntitySet
from .context import ReportContext
from .dashboard import build_dashboard
from .pages.overview import build_quality_panels
from .pages.questions import render_questions
from .templating import render_template

MISSING_LANGUAGE = "__missing__"


def response_language(response: dict[str, Any]) -> str:
    """Give missing or blank UserLanguage a selectable, non-dropping cohort."""
    return str(response.get("user_language") or "").strip() or MISSING_LANGUAGE


def _definition_labels(entities: EntitySet) -> tuple[list[str], dict[str, dict[str, dict[str, str]]]]:
    languages = sorted(
        {
            str(code)
            for manifest in entities.survey_manifests.values()
            for code in manifest.get("languages", {}).get("all_languages", [])
        }
        | {str(row["language_code"]) for row in entities.questions if row.get("language_code")}
    )
    if not languages:
        return [], {}
    base_codes = [
        str(manifest.get("languages", {}).get("base_language"))
        for manifest in entities.survey_manifests.values()
        if manifest.get("languages", {}).get("base_language")
    ]
    languages.sort(key=lambda code: (code not in base_codes, code))
    questions = [row for row in entities.questions if not row.get("is_localized")]
    fields = [row for row in entities.question_fields if not row.get("is_localized")]
    options = [row for row in entities.answer_options if not row.get("is_localized")]
    q_variants = {
        (str(row["survey_id"]), str(row.get("question_external_id")), str(row.get("language_code"))): row
        for row in entities.questions
    }
    f_variants = {
        (str(row["survey_id"]), str(row.get("question_field_catalog_id")), str(row.get("language_code"))): row
        for row in entities.question_fields
    }
    field_by_id = {str(row.get("question_field_id")): row for row in entities.question_fields}
    o_variants = {
        (
            str(row["survey_id"]),
            str(field_by_id.get(str(row.get("question_field_id")), {}).get("question_field_catalog_id")),
            str(row.get("answer_external_id")),
            str(row.get("language_code")),
        ): row
        for row in entities.answer_options
    }
    labels = {}
    for code in languages:
        q_labels = {
            str(row["question_id"]): str(
                (q_variants.get((str(row["survey_id"]), str(row.get("question_external_id")), code)) or row).get(
                    "question_text"
                )
                or row.get("question_text")
                or row["question_id"]
            )
            for row in questions
        }
        f_labels = {
            str(row.get("question_field_id") or row.get("field_id")): str(
                (f_variants.get((str(row["survey_id"]), str(row.get("question_field_catalog_id")), code)) or row).get(
                    "field_text"
                )
                or row.get("field_text")
                or ""
            )
            for row in fields
        }
        o_labels = {}
        for row in options:
            if not row.get("answer_option_id"):
                continue
            catalog_id = str(field_by_id.get(str(row.get("question_field_id")), {}).get("question_field_catalog_id"))
            variant = o_variants.get((str(row["survey_id"]), catalog_id, str(row.get("answer_external_id")), code))
            o_labels[str(row["answer_option_id"])] = str(
                (variant or row).get("answer_text") or row.get("answer_text") or ""
            )
        labels[code] = {"questions": q_labels, "fields": f_labels, "options": o_labels}
    return languages, labels


def _snapshot(entities: EntitySet, display_labels: dict[str, dict[str, dict[str, str]]]) -> dict[str, Any]:
    context = ReportContext.build(entities)
    analysis = context.analysis
    questions = render_questions(context)
    surveys = {
        sid: {
            "responses": analysis.survey_response_counts[sid],
            "finished": analysis.survey_finished_counts[sid],
            "questions": analysis.survey_question_counts[sid],
            "answers": analysis.survey_answer_counts[sid],
            "unanswered": analysis.survey_unanswered_counts[sid],
            "unusedFields": analysis.survey_unused_field_counts[sid],
        }
        for sid in analysis.survey_lookup
    }
    return {
        "surveys": surveys,
        "dashboard": build_dashboard(entities, analysis, include_label_ids=True),
        "questions": questions.metrics,
        "findings": list(questions.findings),
        "quality": {
            code: {
                panel.survey_id: render_template(
                    "components/quality_panel.html.jinja", panel=panel, multiple_surveys=len(entities.surveys) > 1
                )
                for panel in build_quality_panels(context, labels)
            }
            for code, labels in (display_labels or {"": {}}).items()
        },
    }


def build_report_languages(entities: EntitySet) -> dict[str, Any]:
    """Keep fact rows immutable while preparing all observed respondent cohorts."""
    respondent_languages = list(dict.fromkeys(response_language(row) for row in entities.responses))
    display_languages, labels = _definition_labels(entities)
    base_questions = [row for row in entities.questions if not row.get("is_localized")]
    base_options = [row for row in entities.answer_options if not row.get("is_localized")]
    flow_labels: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for code in display_languages:
        by_survey: dict[str, dict[str, dict[str, Any]]] = {}
        for question in base_questions:
            sid = str(question["survey_id"])
            external = str(question.get("question_external_id") or "")
            qid = str(question["question_id"])
            native_choices = {
                str(option.get("answer_external_id")): labels[code]["options"].get(
                    str(option.get("answer_option_id")), str(option.get("answer_text") or "")
                )
                for option in base_options
                if str(option["survey_id"]) == sid and str(option.get("question_external_id")) == external
            }
            if str(question.get("canonical_question_type")) == "matrix":
                for field in entities.question_fields:
                    if field.get("is_localized") or str(field["survey_id"]) != sid or str(field["question_id"]) != qid:
                        continue
                    if field.get("choice_external_id"):
                        native_choices[str(field["choice_external_id"])] = labels[code]["fields"].get(
                            str(field.get("question_field_id") or field.get("field_id")),
                            str(field.get("statement_text") or field.get("field_text") or ""),
                        )
            by_survey.setdefault(sid, {})[external] = {
                "text": labels[code]["questions"][qid],
                "choices": native_choices,
            }
        flow_labels[code] = by_survey
    snapshots = {"all": _snapshot(entities, labels)}
    for code in respondent_languages:
        responses = [row for row in entities.responses if response_language(row) == code]
        response_keys = {(str(row["survey_id"]), str(row["response_id"])) for row in responses}
        answers = [
            row
            for row in entities.response_answers
            if (str(row["survey_id"]), str(row["response_id"])) in response_keys
        ]
        snapshots[code] = _snapshot(replace(entities, responses=responses, response_answers=answers), labels)
    return {
        "respondent_languages": respondent_languages,
        "display_languages": display_languages,
        "labels": labels,
        "flow_labels": flow_labels,
        "snapshots": snapshots,
    }
