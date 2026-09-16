"""Download or reuse surveys, prepare optional translations, and build outputs.

Examples:
    uv run --extra cli --extra ui python examples/survey_workflow.py SV_123 SV_456 --output output/run
    uv run --extra cli --extra ui python examples/survey_workflow.py SV_123 --from-files data \
        --translator my_adapter:translate --language EN --report --output output/run
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from qualtrics import (
    QualtricsClient,
    TranslationRequest,
    build_semantic_model,
    merge_entity_sets,
    parse_survey,
    prepare_translations,
    render_report,
    write_entities,
    write_semantic_model,
)
from qualtrics.api import ResponseExportRequest

Translator = Callable[[TranslationRequest], str]

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
    help="Prepare distinct Qualtrics surveys for reports and Power BI.",
)


@dataclass(frozen=True)
class SurveyResult:
    """Human-facing result for one prepared survey."""

    survey_id: str
    response_count: int
    comment_count: int
    target_language: str
    entities: Path
    report: Path | None


@dataclass(frozen=True)
class WorkflowResult:
    """Paths and totals produced by one workflow run."""

    surveys: tuple[SurveyResult, ...]
    combined_entities: Path
    power_bi: Path
    combined_report: Path | None

    @property
    def survey_count(self) -> int:
        return len(self.surveys)

    @property
    def response_count(self) -> int:
        return sum(survey.response_count for survey in self.surveys)

    @property
    def comment_count(self) -> int:
        return sum(survey.comment_count for survey in self.surveys)


def _load_translator(spec: str | None) -> Translator | None:
    if spec is None:
        return None
    module_name, separator, function_name = spec.partition(":")
    if not separator or not module_name or not function_name:
        raise ValueError("--translator must be module:function")
    function = getattr(importlib.import_module(module_name), function_name)
    if not callable(function):
        raise ValueError(f"{spec} is not callable")
    return function


def _local_inputs(source_root: Path, survey_id: str) -> tuple[Path, Path]:
    folder = source_root / survey_id
    definition = folder / "definition.qsf"
    archive = folder / "export.zip"
    source = archive if archive.is_file() else folder / "responses.csv"
    if not definition.is_file() or not source.is_file():
        raise ValueError(f"{folder} needs definition.qsf and export.zip or responses.csv")
    return source, definition


def _download_inputs(client: Any, output: Path, survey_id: str) -> tuple[Path, Path]:
    raw = output / "raw" / survey_id
    raw.mkdir(parents=True, exist_ok=True)
    definition = raw / "definition.qsf"
    archive = raw / "export.zip"
    qsf = client.survey_definitions.get(survey_id)
    definition.write_text(json.dumps(qsf.payload, ensure_ascii=False, indent=2), encoding="utf-8")
    client.response_exports.export(
        survey_id,
        archive,
        options=ResponseExportRequest(format="csv", compress=True, useLabels=True),
    )
    return archive, definition


def run_workflow(
    survey_ids: Sequence[str],
    output: Path,
    *,
    source_root: Path | None = None,
    translator: Translator | None = None,
    language: str | None = None,
    create_report: bool = False,
    client: Any | None = None,
) -> WorkflowResult:
    """Write one survey snapshot each, then combine once and export Power BI data."""
    ids = list(survey_ids)
    if not ids or any(not survey_id.strip() for survey_id in ids):
        raise ValueError("Supply at least one nonblank survey ID")
    if len(set(ids)) != len(ids):
        raise ValueError("Survey IDs must be distinct; repeated exports must not be combined")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"Choose a fresh output directory: {output}")
    local = [_local_inputs(source_root, survey_id) for survey_id in ids] if source_root else None
    if source_root is None and client is None:
        with QualtricsClient() as owned_client:
            return run_workflow(
                ids,
                output,
                translator=translator,
                language=language,
                create_report=create_report,
                client=owned_client,
            )
        return

    output.mkdir(parents=True, exist_ok=True)
    surveys = []
    results = []
    for index, survey_id in enumerate(ids):
        source, definition = local[index] if local is not None else _download_inputs(client, output, survey_id)
        parsed = parse_survey(source, definition)
        actual = [str(row["survey_id"]) for row in parsed.surveys]
        if actual != [survey_id]:
            raise ValueError(f"{definition} describes {actual}, not requested survey {survey_id}")
        prepared = prepare_translations(parsed, language=language, translate=translator)
        survey_output = output / "surveys" / survey_id
        entities_output = survey_output / "entities"
        write_entities(prepared, entities_output, format="parquet")
        report_output = survey_output / "report.html" if create_report else None
        if report_output is not None:
            render_report(prepared, report_output)
        surveys.append(prepared)
        registry = prepared.survey_manifests[survey_id]["languages"]
        target = str(language or registry.get("base_language") or "—").upper()
        results.append(
            SurveyResult(
                survey_id=survey_id,
                response_count=len(prepared.responses),
                comment_count=len(prepared.comments),
                target_language=target,
                entities=entities_output,
                report=report_output,
            )
        )

    combined = merge_entity_sets(surveys)
    combined_entities = output / "combined" / "entities"
    power_bi = output / "power-bi"
    combined_report = output / "combined" / "report.html" if create_report else None
    write_entities(combined, combined_entities, format="parquet")
    write_semantic_model(build_semantic_model(combined), power_bi, format="parquet")
    if combined_report is not None:
        render_report(combined, combined_report)
    return WorkflowResult(tuple(results), combined_entities, power_bi, combined_report)


def _print_path(console: Console, label: str, path: Path) -> None:
    console.print(Text.assemble((f"{label}:", "bold"), " ", str(path)), soft_wrap=True)


def print_result(result: WorkflowResult, console: Console | None = None) -> None:
    """Render one compact result table and copyable artifact paths."""
    console = console or Console()
    surveys = Table(title="Survey preparation", box=box.SIMPLE_HEAD, header_style="bold cyan")
    surveys.add_column("Survey", style="bold")
    surveys.add_column("Responses", justify="right")
    surveys.add_column("Comments", justify="right")
    surveys.add_column("Target", justify="center")
    for survey in result.surveys:
        surveys.add_row(
            survey.survey_id,
            f"{survey.response_count:,}",
            f"{survey.comment_count:,}",
            survey.target_language,
        )
    console.print(surveys)

    totals = Table(title="Output summary", box=box.SIMPLE, show_header=False)
    totals.add_column(style="bold")
    totals.add_column(justify="right")
    totals.add_row("Surveys", f"{result.survey_count:,}")
    totals.add_row("Responses", f"{result.response_count:,}")
    totals.add_row("Comments", f"{result.comment_count:,}")
    console.print(totals)
    _print_path(console, "Combined entities", result.combined_entities)
    _print_path(console, "Power BI model", result.power_bi)
    if result.combined_report is not None:
        _print_path(console, "Combined report", result.combined_report)


@app.command()
def main(
    survey_ids: Annotated[
        list[str],
        typer.Argument(help="Distinct Qualtrics survey IDs, for example SV_123 SV_456"),
    ],
    output: Annotated[Path, typer.Option("--output", "-o", help="Fresh output directory")],
    source_root: Annotated[
        Path | None,
        typer.Option(
            "--from-files",
            exists=True,
            file_okay=False,
            readable=True,
            help="Reuse ROOT/SV_ID/definition.qsf and export.zip or responses.csv",
        ),
    ] = None,
    translator: Annotated[str | None, typer.Option(help="Python callback as module:function")] = None,
    language: Annotated[
        str | None,
        typer.Option(help="One target language for all surveys; defaults to each SurveyLanguage"),
    ] = None,
    report: Annotated[bool, typer.Option("--report", help="Also create HTML reports")] = False,
) -> None:
    """Parse, translate, combine, and export one or more surveys."""
    try:
        result = run_workflow(
            survey_ids,
            output,
            source_root=source_root,
            translator=_load_translator(translator),
            language=language,
            create_report=report,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    print_result(result)


if __name__ == "__main__":
    app()
