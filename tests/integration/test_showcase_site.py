from __future__ import annotations

import csv
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import pytest

pytest.importorskip("mkdocs")
from mkdocs.commands.build import build
from mkdocs.config import load_config

REPO = Path(__file__).parents[2]
SITE_URL = "https://example.invalid/qualtrics/"


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.frames: list[dict[str, str | None]] = []
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "iframe":
            self.frames.append(attributes)
        if tag == "a" and attributes.get("href"):
            self.links.append(str(attributes["href"]))


@pytest.mark.parametrize("directory_urls", [True, False])
def test_built_showcase_embeds_current_report_and_downloads_under_project_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory_urls: bool
) -> None:
    site = tmp_path / "site"
    # Building from elsewhere also exercises hook imports and source path resolution.
    monkeypatch.chdir(tmp_path)
    config = load_config(
        config_file=str(REPO / "mkdocs.yml"),
        site_dir=str(site),
        site_url=SITE_URL,
        use_directory_urls=directory_urls,
        strict=True,
    )
    build(config)

    page_path = "examples/question-types/index.html" if directory_urls else "examples/question-types.html"
    page_url = urljoin(SITE_URL, "examples/question-types/" if directory_urls else page_path)
    page = (site / page_path).read_text(encoding="utf-8")
    links = _Links()
    links.feed(page)
    assert len(links.frames) == 1
    assert links.frames[0].get("title")
    report_url = urljoin(page_url, str(links.frames[0]["src"]))
    assert report_url == SITE_URL + "assets/examples/question-types/report.html"

    download_urls = {urljoin(page_url, link) for link in links.links}
    assets = site / "assets/examples/question-types"
    for filename in ("survey.qsf", "responses.csv", "coverage.json", "report.html"):
        assert SITE_URL + f"assets/examples/question-types/{filename}" in download_urls
        assert (assets / filename).stat().st_size > 0

    # Follow the actual iframe URL, rather than assuming its on-disk destination.
    iframe_path = unquote(urlsplit(report_url).path).removeprefix("/qualtrics/")
    report = (site / iframe_path).read_text(encoding="utf-8")
    dashboard = json.loads(report.split("id='dashboard-data' type='application/json'>", 1)[1].split("</script>", 1)[0])
    coverage = json.loads((assets / "coverage.json").read_text(encoding="utf-8"))
    with (assets / "responses.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert coverage["family_count"] == 32
    assert coverage["response_count"] == len(rows) - 3 == 100
    assert sum(survey["responses"] for survey in dashboard["surveys"]) == coverage["response_count"]
    assert {spotlight["kind"] for spotlight in dashboard["spotlights"]} >= {"nps", "numeric", "categorical"}
    assert not (REPO / "docs/assets/examples/question-types/report.html").exists()
