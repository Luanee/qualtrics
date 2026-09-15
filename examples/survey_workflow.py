"""Download or reuse surveys, prepare optional translations, and build outputs.

Examples:
    uv run --extra ui python examples/survey_workflow.py SV_123 SV_456 --output output/run
    uv run --extra ui python examples/survey_workflow.py SV_123 --from-files data \
        --translator my_adapter:translate --language EN --report --output output/run
"""

from __future__ import annotations

import argparse
import importlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

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
) -> None:
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
            run_workflow(
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
    for index, survey_id in enumerate(ids):
        source, definition = local[index] if local is not None else _download_inputs(client, output, survey_id)
        parsed = parse_survey(source, definition)
        actual = [str(row["survey_id"]) for row in parsed.surveys]
        if actual != [survey_id]:
            raise ValueError(f"{definition} describes {actual}, not requested survey {survey_id}")
        prepared = prepare_translations(parsed, language=language, translate=translator)
        survey_output = output / "surveys" / survey_id
        write_entities(prepared, survey_output / "entities", format="parquet")
        if create_report:
            render_report(prepared, survey_output / "report.html")
        surveys.append(prepared)
        print(f"{survey_id}: {len(prepared.responses)} responses, {len(prepared.comments)} comments")

    combined = merge_entity_sets(surveys)
    write_entities(combined, output / "combined" / "entities", format="parquet")
    write_semantic_model(build_semantic_model(combined), output / "power-bi", format="parquet")
    if create_report:
        render_report(combined, output / "combined" / "report.html")
    print(f"Combined {len(ids)} surveys into {output / 'combined'} and {output / 'power-bi'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("survey_ids", nargs="+", help="Distinct Qualtrics survey IDs")
    parser.add_argument("--output", type=Path, required=True, help="Fresh output directory")
    parser.add_argument("--from-files", type=Path, help="Reuse ROOT/SV_ID/definition.qsf and export.zip")
    parser.add_argument("--translator", help="Your Python callback as module:function")
    parser.add_argument("--language", help="One target language across all surveys; otherwise each SurveyLanguage")
    parser.add_argument("--report", action="store_true", help="Also create HTML reports")
    args = parser.parse_args()
    run_workflow(
        args.survey_ids,
        args.output,
        source_root=args.from_files,
        translator=_load_translator(args.translator),
        language=args.language,
        create_report=args.report,
    )


if __name__ == "__main__":
    main()
