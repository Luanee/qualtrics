import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pytest

pytest.importorskip("mkdocs")

from mkdocs.config import load_config  # noqa: E402
from mkdocs.config.defaults import MkDocsConfig  # noqa: E402
from mkdocs.plugins import BasePlugin  # noqa: E402
from mkdocs.structure.files import File, Files  # noqa: E402
from mkdocs.structure.pages import Page  # noqa: E402
from scripts import docs_showcase  # noqa: E402


class ShowcaseHook(BasePlugin):
    on_files = staticmethod(docs_showcase.on_files)


@pytest.fixture
def generated_showcase(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    coverage = {
        "response_count": 100,
        "family_count": 2,
        "case_count": 2,
        "cases": [
            {
                "case_id": "single-choice",
                "question_id": "QID1",
                "label": "Team <survey> | selection",
                "question_type": "MC",
                "selector": "SAVR",
                "sub_selector": "TX",
                "canonical_type": "multiple_choice_single",
                "field_count": 1,
                "presentation": "Categorical chart",
                "limitations": "Choose one.\nSynthetic values only.",
                "source_url": "https://www.qualtrics.com/support/",
            },
            {
                "case_id": "intro",
                "question_id": "QID2",
                "label": "Introduction",
                "question_type": "DB",
                "selector": "TB",
                "sub_selector": "",
                "canonical_type": "descriptive_text",
                "field_count": 0,
                "presentation": "Definition only",
                "limitations": "No response output.",
                "source_url": "",
            },
        ],
    }
    state: dict[str, Any] = {"coverage": coverage}

    def build_showcase(output_dir: Path) -> dict[str, Path]:
        state["output_dir"] = output_dir
        contents = {
            "survey": ("survey.qsf", b'{"SurveyEntry":{}}'),
            "responses": ("responses.csv", b'ResponseId,Answer\nR_FAKE,"Hello, world"\n'),
            "coverage": ("coverage.json", json.dumps(coverage).encode()),
            "report": ("report.html", b"<!doctype html><html><body>Synthetic report</body></html>"),
        }
        paths = {}
        for key, (name, content) in contents.items():
            path = output_dir / name
            path.write_bytes(content)
            paths[key] = path
        return paths

    monkeypatch.setattr(docs_showcase, "build_showcase", build_showcase)
    return state


def showcase_config(tmp_path: Path, use_directory_urls: bool = True) -> MkDocsConfig:
    docs = tmp_path / "docs"
    docs.mkdir()
    config_path = tmp_path / "mkdocs.yml"
    config_path.write_text("site_name: Test\ndocs_dir: docs\nplugins: []\n", encoding="utf-8")
    config = load_config(
        config_file=str(config_path),
        use_directory_urls=use_directory_urls,
        site_url="https://example.org/qualtrics/",
    )
    config.plugins["showcase"] = ShowcaseHook()
    return config


def test_assets_outlive_temporary_generation_without_writing_docs(
    tmp_path: Path, generated_showcase: dict[str, Any]
) -> None:
    config = showcase_config(tmp_path)
    files = Files([])

    result = config.plugins.on_files(files, config=config)

    assert result is files
    assert sorted(file.src_uri for file in files) == [
        f"assets/examples/question-types/{filename}"
        for filename in ("coverage.json", "report.html", "responses.csv", "survey.qsf")
    ]
    assert not generated_showcase["output_dir"].exists()
    assert list(Path(config.docs_dir).rglob("*")) == []
    for file in files:
        file.copy_file()
        assert Path(file.abs_dest_path).read_bytes() == file.content_bytes
    report = files.get_file_from_path("assets/examples/question-types/report.html")
    assert report is not None
    assert "Synthetic report" in report.content_string


@pytest.mark.parametrize("use_directory_urls", [True, False])
def test_embed_and_download_urls_resolve_inside_project_site(
    tmp_path: Path, generated_showcase: dict[str, Any], use_directory_urls: bool
) -> None:
    config = showcase_config(tmp_path, use_directory_urls)
    files = config.plugins.on_files(Files([]), config=config)
    page_file = File("examples/question-types.md", config.docs_dir, config.site_dir, use_directory_urls)
    page = Page("Question types", page_file, config)
    markdown = "\n".join(f"{{{{ showcase_{key}_url }}}}" for key in ("survey", "responses", "coverage", "report"))

    rendered = docs_showcase.on_page_markdown(markdown, page=page, config=config, files=files)

    assert config.site_url is not None
    page_url = urljoin(config.site_url, page.url)
    assert [urljoin(page_url, url) for url in rendered.splitlines()] == [
        f"https://example.org/qualtrics/assets/examples/question-types/{filename}"
        for filename in ("survey.qsf", "responses.csv", "coverage.json", "report.html")
    ]


def test_coverage_comes_from_manifest_and_keeps_definition_only_cases(
    tmp_path: Path, generated_showcase: dict[str, Any]
) -> None:
    config = showcase_config(tmp_path)
    files = config.plugins.on_files(Files([]), config=config)
    page = Page("Question types", File("examples/question-types.md", config.docs_dir, config.site_dir, True), config)

    rendered = docs_showcase.on_page_markdown(
        "{{ showcase_counts }}\n\n{{ showcase_coverage }}", page=page, config=config, files=files
    )

    assert "100 fictional responses" in rendered
    assert "2 question families" in rendered
    assert "2 cases" in rendered
    assert "QID1" in rendered
    assert "Team &lt;survey&gt; &#124; selection" in rendered
    assert "MC / SAVR / TX" in rendered
    assert "No response output." in rendered
    assert "Definition only" in rendered
    assert "QID2" in rendered
    assert "{{" not in rendered


def test_other_pages_are_unchanged(tmp_path: Path) -> None:
    config = showcase_config(tmp_path)
    page = Page("Other", File("other.md", config.docs_dir, config.site_dir, True), config)
    original = "A literal {{ showcase_counts }} example."

    assert docs_showcase.on_page_markdown(original, page=page, config=config, files=Files([])) == original
