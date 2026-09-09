"""Build the public, synthetic report example as virtual MkDocs assets."""

import html
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page
from mkdocs.utils import get_relative_url

_PAGE = "examples/question-types.md"
_ASSET_ROOT = "assets/examples/question-types"
_FILENAMES = {
    "survey": "survey.qsf",
    "responses": "responses.csv",
    "coverage": "coverage.json",
    "report": "report.html",
}


def build_showcase(output_dir: Path) -> dict[str, Path]:
    """Use a fresh interpreter so `mkdocs serve` also picks up Python code edits."""
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(root / "src"), environment.get("PYTHONPATH", "")) if value
    )
    try:
        subprocess.run(
            [sys.executable, "-m", "scripts.question_type_showcase", "--output", str(output_dir)],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise PluginError(
            f"Could not generate the synthetic report showcase:\n{error.stderr or error.stdout}"
        ) from error
    return {key: output_dir / filename for key, filename in _FILENAMES.items()}


def on_files(files: Files, *, config: MkDocsConfig) -> Files:
    """Keep generated data in memory; the temporary sources can be removed now."""
    with TemporaryDirectory(prefix="qualtrics-docs-showcase-") as directory:
        generated = build_showcase(Path(directory))
        for key, filename in _FILENAMES.items():
            files.append(File.generated(config, f"{_ASSET_ROOT}/{filename}", content=generated[key].read_bytes()))
    return files


def _cell(value: object) -> str:
    """Keep fixture labels readable without creating Markdown cells or HTML."""
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return html.escape(str(value), quote=False).replace("|", "&#124;").replace("\n", "<br>")


def _coverage_table(coverage: dict[str, Any]) -> str:
    rows = [
        "| Example question | Toolkit family | QSF type / selector / sub-selector |"
        " Exported fields | Report view | Notes |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for case in coverage["cases"]:
        layout = " / ".join(str(case[key] or "—") for key in ("question_type", "selector", "sub_selector"))
        notes = _cell(case["limitations"] or "—")
        if case["source_url"]:
            source_url = html.escape(str(case["source_url"]), quote=True)
            notes += f' <a href="{source_url}">Qualtrics guide</a>'
        rows.append(
            "| "
            + " | ".join((
                f"{_cell(case['label'])}<br>{_cell(case['question_id'])}",
                _cell(case["canonical_type"]),
                _cell(layout),
                _cell(case["field_count"]),
                _cell(case["presentation"]),
                notes,
            ))
            + " |"
        )
    return "\n".join(rows)


def on_page_markdown(markdown: str, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    """Resolve the embed against the actual output URL, including flat URL builds."""
    if page.file.src_uri != _PAGE:
        return markdown
    assets = {}
    for key, filename in _FILENAMES.items():
        asset = files.get_file_from_path(f"{_ASSET_ROOT}/{filename}")
        if asset is None:
            raise PluginError(f"Missing generated showcase asset: {filename}")
        assets[key] = asset
        url = html.escape(get_relative_url(asset.url, page.url), quote=True)
        markdown = markdown.replace("{{ showcase_" + key + "_url }}", url)

    coverage = json.loads(assets["coverage"].content_string)
    counts = (
        f"**{coverage['response_count']} fictional responses**, "
        f"**{coverage['family_count']} question families**, and **{coverage['case_count']} cases**."
    )
    return markdown.replace("{{ showcase_counts }}", counts).replace(
        "{{ showcase_coverage }}", _coverage_table(coverage)
    )
