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
    EntitySet,
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
class SurveyInputs:
    """Raw response export and matching definition for one survey."""

    survey_id: str
    source: Path
    definition: Path


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

    def translate(request: TranslationRequest) -> str:
        result = function(request)
        if not isinstance(result, str):
            raise ValueError(f"{spec} must return text")
        return result

    return translate


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


def acquire_survey_inputs(
    survey_id: str, output: Path, *, source_root: Path | None = None, client: Any | None = None
) -> SurveyInputs:
    """Reuse a local CSV/ZIP and QSF or download both from Qualtrics."""
    if source_root is not None:
        source, definition = _local_inputs(source_root, survey_id)
    elif client is not None:
        source, definition = _download_inputs(client, output, survey_id)
    else:
        raise ValueError("A local source or Qualtrics client is required")
    return SurveyInputs(survey_id, source, definition)


def parse_survey_input(inputs: SurveyInputs) -> EntitySet:
    """Parse one export and verify the QSF identifies the requested survey."""
    entities = parse_survey(inputs.source, inputs.definition)
    actual = [str(row["survey_id"]) for row in entities.surveys]
    if actual != [inputs.survey_id]:
        raise ValueError(f"{inputs.definition} describes {actual}, not requested survey {inputs.survey_id}")
    return entities


def translate_survey(entities: EntitySet, *, target_language: str | None, translator: Translator | None) -> EntitySet:
    """Prepare optional definition labels and comments without changing facts."""
    return prepare_translations(entities, language=target_language, translate=translator)


def write_survey_outputs(
    survey_id: str, entities: EntitySet, output: Path, *, create_report: bool, target_language: str | None = None
) -> SurveyResult:
    """Save one survey's Parquet entities and optional HTML report."""
    survey_output = output / "surveys" / survey_id
    entities_output = survey_output / "entities"
    write_entities(entities, entities_output, format="parquet")
    report_output = survey_output / "report.html" if create_report else None
    if report_output is not None:
        render_report(entities, report_output)
    registry = entities.survey_manifests[survey_id]["languages"]
    prepared = registry.get("prepared_languages", [])
    target = str(target_language or (prepared[-1] if prepared else registry.get("base_language")) or "—").upper()
    return SurveyResult(
        survey_id, len(entities.responses), len(entities.comments), target, entities_output, report_output
    )


def combine_survey_outputs(surveys: Sequence[EntitySet]) -> EntitySet:
    """Combine distinct surveys once, preserving nullable translation targets."""
    return merge_entity_sets(list(surveys))


def write_combined_entities(entities: EntitySet, output: Path) -> Path:
    """Save the combined entity collection as Parquet."""
    destination = output / "combined" / "entities"
    write_entities(entities, destination, format="parquet")
    return destination


def write_combined_report(entities: EntitySet, output: Path, *, create_report: bool) -> Path | None:
    """Write a combined HTML report only when requested."""
    if not create_report:
        return None
    destination = output / "combined" / "report.html"
    render_report(entities, destination)
    return destination


def write_powerbi_model(entities: EntitySet, output: Path) -> Path:
    """Export semantic-model Parquet tables for Power BI."""
    destination = output / "power-bi"
    write_semantic_model(build_semantic_model(entities), destination, format="parquet")
    return destination


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
    local = (
        [acquire_survey_inputs(survey_id, output, source_root=source_root) for survey_id in ids]
        if source_root
        else None
    )
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

    output.mkdir(parents=True, exist_ok=True)
    surveys: list[EntitySet] = []
    results: list[SurveyResult] = []
    for index, survey_id in enumerate(ids):
        inputs = local[index] if local is not None else acquire_survey_inputs(survey_id, output, client=client)
        parsed = parse_survey_input(inputs)
        prepared = translate_survey(parsed, target_language=language, translator=translator)
        surveys.append(prepared)
        results.append(
            write_survey_outputs(survey_id, prepared, output, create_report=create_report, target_language=language)
        )

    combined = combine_survey_outputs(surveys)
    combined_entities = write_combined_entities(combined, output)
    combined_report = write_combined_report(combined, output, create_report=create_report)
    power_bi = write_powerbi_model(combined, output)
    return WorkflowResult(tuple(results), combined_entities, power_bi, combined_report)


def _print_path(console: Console, label: str, path: Path) -> None:
    console.print(Text.assemble((f"{label}:", "bold"), " ", str(path)), soft_wrap=True)


def print_result(result: WorkflowResult, console: Console | None = None) -> None:
    """Render one compact result table and copyable artifact paths."""
    output_console = console if console is not None else Console()
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
    output_console.print(surveys)

    totals = Table(title="Output summary", box=box.SIMPLE, show_header=False)
    totals.add_column(style="bold")
    totals.add_column(justify="right")
    totals.add_row("Surveys", f"{result.survey_count:,}")
    totals.add_row("Responses", f"{result.response_count:,}")
    totals.add_row("Comments", f"{result.comment_count:,}")
    output_console.print(totals)
    _print_path(output_console, "Combined entities", result.combined_entities)
    _print_path(output_console, "Power BI model", result.power_bi)
    if result.combined_report is not None:
        _print_path(output_console, "Combined report", result.combined_report)


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
