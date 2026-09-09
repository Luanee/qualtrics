"""Generate and embed the fictional flow example during MkDocs builds."""

import html
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from mkdocs.config.defaults import MkDocsConfig
from mkdocs.exceptions import PluginError
from mkdocs.structure.files import File, Files
from mkdocs.structure.pages import Page
from mkdocs.utils import get_relative_url

_ASSETS = "assets/examples/survey-flow"
_FILES = {"survey": "survey.qsf", "flow": "flow.json", "responses": "responses.csv", "report": "report.html"}


def on_files(files: Files, *, config: MkDocsConfig) -> Files:
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        value for value in (str(root / "src"), environment.get("PYTHONPATH", "")) if value
    )
    with TemporaryDirectory(prefix="qualtrics-flow-example-") as directory:
        try:
            subprocess.run(
                [sys.executable, "-m", "scripts.survey_flow_showcase", "--output", directory],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            raise PluginError(f"Could not generate survey flow example:\n{error.stderr or error.stdout}") from error
        for filename in _FILES.values():
            files.append(
                File.generated(config, f"{_ASSETS}/{filename}", content=(Path(directory) / filename).read_bytes())
            )
    return files


def on_page_markdown(markdown: str, *, page: Page, config: MkDocsConfig, files: Files) -> str:
    if page.file.src_uri != "examples/survey-flow.md":
        return markdown
    for key, filename in _FILES.items():
        asset = files.get_file_from_path(f"{_ASSETS}/{filename}")
        if asset is None:
            raise PluginError(f"Missing survey flow example asset: {filename}")
        url = html.escape(get_relative_url(asset.url, page.url), quote=True)
        markdown = markdown.replace("{{ flow_" + key + "_url }}", url)
    return markdown
