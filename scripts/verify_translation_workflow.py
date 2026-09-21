"""Verify parse → prepare → combine → semantic invariants without a provider.

Example:
    uv run --extra cli python scripts/verify_translation_workflow.py data SV_123 SV_456 \
        --target-language EN --output knowledge/verification/survey-translation-workflow.json
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, TypedDict

import typer
from rich.console import Console
from rich.table import Table

from qualtrics import (
    TranslationRequest,
    build_semantic_model,
    merge_entity_sets,
    parse_survey,
    prepare_translations,
)

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Check local exports and translation invariants.")


class SurveySummary(TypedDict):
    survey_id: str
    responses: int
    answers: int
    comments_original: int
    comments_translated: int
    localized_questions: int


class CombinedSummary(TypedDict):
    surveys: int
    responses: int
    answers: int
    comments: int
    semantic_model_built: bool


class VerificationSummary(TypedDict):
    target_language: str
    surveys: list[SurveySummary]
    combined: CombinedSummary


def _offline_translation(request: TranslationRequest) -> str:
    return f"[{request.target_language}] {request.text}"


def _answer_facts(entities) -> dict[str, tuple[str, str, str]]:
    return {
        str(row["response_answer_id"]): (
            str(row["survey_id"]),
            str(row["response_id"]),
            str(row["answer_text"]),
        )
        for row in entities.response_answers
    }


def verify_exports(source_root: Path, survey_ids: Sequence[str], *, target_language: str) -> VerificationSummary:
    """Assert that translation changes display content but never answer facts."""
    ids = tuple(survey_ids)
    if not ids or any(not survey_id.strip() for survey_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("Supply distinct, nonblank survey IDs")
    if not isinstance(target_language, str) or not target_language.strip():
        raise ValueError("Target language must be nonblank")
    target = target_language.upper()
    prepared_sets = []
    summaries: list[SurveySummary] = []
    for survey_id in ids:
        folder = source_root / survey_id
        definition = folder / "definition.qsf"
        source = folder / "export.zip"
        if not source.is_file():
            source = folder / "responses.csv"
        if not definition.is_file() or not source.is_file():
            raise ValueError(f"{folder} needs definition.qsf and export.zip or responses.csv")
        original = parse_survey(source, definition)
        if [str(row["survey_id"]) for row in original.surveys] != [survey_id]:
            raise ValueError(f"{definition} does not describe {survey_id}")
        prepared = prepare_translations(original, language=target, translate=_offline_translation)
        original_responses = {str(row["response_id"]) for row in original.responses}
        prepared_responses = {str(row["response_id"]) for row in prepared.responses}
        if len(original.responses) != len(prepared.responses) or original_responses != prepared_responses:
            raise AssertionError(f"{survey_id}: response identities changed during preparation")
        if len(original.response_answers) != len(prepared.response_answers) or _answer_facts(original) != _answer_facts(
            prepared
        ):
            raise AssertionError(f"{survey_id}: answer identities or raw values changed during preparation")
        if len(original.comments) != len(prepared.comments):
            raise AssertionError(f"{survey_id}: original written-answer count changed during preparation")
        localized_questions = sum(
            bool(row.get("is_localized")) and str(row.get("language_code") or "").casefold() == target.casefold()
            for row in prepared.questions
        )
        base_language = prepared.survey_manifests[survey_id]["languages"].get("base_language")
        if (
            base_language
            and str(base_language).casefold() != target.casefold()
            and original.questions
            and not localized_questions
        ):
            raise AssertionError(f"{survey_id}: requested definition language has no question labels")
        summaries.append({
            "survey_id": survey_id,
            "responses": len(prepared.responses),
            "answers": len(prepared.response_answers),
            "comments_original": len(prepared.comments),
            "comments_translated": sum(bool(row.get(f"translated_text__{target}")) for row in prepared.comments),
            "localized_questions": localized_questions,
        })
        prepared_sets.append(prepared)

    combined = merge_entity_sets(prepared_sets)
    expected = {
        "surveys": len(ids),
        "responses": sum(row["responses"] for row in summaries),
        "answers": sum(row["answers"] for row in summaries),
        "comments": sum(row["comments_original"] for row in summaries),
    }
    actual = {
        "surveys": len(combined.surveys),
        "responses": len(combined.responses),
        "answers": len(combined.response_answers),
        "comments": len(combined.comments),
    }
    if actual != expected or {str(row["survey_id"]) for row in combined.surveys} != set(ids):
        raise AssertionError(f"Combined survey counts differ from individual exports: {actual} vs {expected}")
    build_semantic_model(combined)
    return {
        "target_language": target,
        "surveys": summaries,
        "combined": {
            "surveys": actual["surveys"],
            "responses": actual["responses"],
            "answers": actual["answers"],
            "comments": actual["comments"],
            "semantic_model_built": True,
        },
    }


def write_summary(summary: Mapping[str, object], output: Path) -> None:
    """Write counts only, never respondent text or definitions."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@app.command()
def main(
    source_root: Annotated[Path, typer.Argument(exists=True, file_okay=False, help="Root with SV_ID folders")],
    survey_ids: Annotated[list[str], typer.Argument(help="Distinct survey IDs to verify")],
    target_language: Annotated[str, typer.Option("--target-language", help="Offline translation target")] = "EN",
    output: Annotated[Path, typer.Option("--output", help="Ignored local JSON summary path")] = Path(
        "knowledge/verification/survey-translation-workflow.json"
    ),
) -> None:
    """Verify real survey exports without writing to source folders."""
    try:
        summary = verify_exports(source_root, survey_ids, target_language=target_language)
        write_summary(summary, output)
    except (ValueError, AssertionError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    table = Table(title=f"Verified offline → {summary['target_language']}")
    table.add_column("Survey")
    table.add_column("Responses", justify="right")
    table.add_column("Answers", justify="right")
    table.add_column("Comments", justify="right")
    table.add_column("Translated", justify="right")
    for row in summary["surveys"]:
        table.add_row(*[
            str(row[key]) for key in ("survey_id", "responses", "answers", "comments_original", "comments_translated")
        ])
    console = Console()
    console.print(table)
    console.print(f"Combined semantic model: [green]valid[/green] · Summary: {output}")


if __name__ == "__main__":
    app()
