"""Prepare and extract release notes from merged GitHub pull requests."""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

import typer

app = typer.Typer(no_args_is_help=True, pretty_exceptions_show_locals=False)

SECTIONS = {
    "feat": ("Features", "✨"),
    "fix": ("Fixes", "🐛"),
    "docs": ("Documentation", "📝"),
    "perf": ("Performance", "⚡"),
    "refactor": ("Refactors", "♻️"),
    "build": ("Internal", "👷"),
    "ci": ("Internal", "👷"),
    "chore": ("Internal", "🔧"),
    "test": ("Internal", "✅"),
    "style": ("Internal", "🎨"),
}
SECTION_ORDER = (
    "Features",
    "Fixes",
    "Performance",
    "Refactors",
    "Documentation",
    "Internal",
    "Other changes",
)
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[a-zA-Z0-9.-]+)?$")
TITLE_PATTERN = re.compile(r"^(?P<kind>[a-z]+)(?:\([^)]+\))?(?:!)?:\s*.+$")
REPOSITORY_PATTERN = re.compile(r"^[^/\s]+/[^/\s]+$")


@dataclass(frozen=True, slots=True)
class PullRequest:
    """Release-note metadata for one merged pull request."""

    number: int
    title: str
    author: str
    url: str
    merged_at: str


def _run(*command: str) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _first_commit() -> str:
    return _run("git", "rev-list", "--max-parents=0", "HEAD").splitlines()[0]


def github_pull_requests(
    repository: str,
    from_ref: str | None,
    to_ref: str = "HEAD",
) -> list[PullRequest]:
    """Return merged PRs associated with commits in a GitHub comparison."""

    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise ValueError(f"Invalid GitHub repository: {repository}")

    base = from_ref or _first_commit()
    comparison = f"{quote(base, safe='')}...{quote(to_ref, safe='')}"
    output = _run(
        "gh",
        "api",
        "--paginate",
        f"repos/{repository}/compare/{comparison}",
        "--jq",
        ".commits[].sha",
    )

    pull_requests: dict[int, PullRequest] = {}
    for commit_sha in output.splitlines():
        response = _run(
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github+json",
            f"repos/{repository}/commits/{commit_sha}/pulls",
        )
        for item in json.loads(response or "[]"):
            if not isinstance(item, dict) or item.get("merged_at") is None:
                continue
            user = item.get("user")
            author = user.get("login") if isinstance(user, dict) else None
            pull_request = PullRequest(
                number=int(item["number"]),
                title=str(item["title"]),
                author=str(author or "ghost"),
                url=str(item["html_url"]),
                merged_at=str(item["merged_at"]),
            )
            pull_requests[pull_request.number] = pull_request

    return sorted(pull_requests.values(), key=lambda pull_request: (pull_request.merged_at, pull_request.number))


def _section_and_icon(title: str) -> tuple[str, str]:
    match = TITLE_PATTERN.match(title)
    kind = match.group("kind") if match else ""
    return SECTIONS.get(kind, ("Other changes", "🔖"))


def render_section(
    version: str,
    release_date: str,
    pull_requests: list[PullRequest],
    repository: str,
) -> str:
    """Render one release section containing merged PRs only."""

    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid release version: {version}")
    dt.date.fromisoformat(release_date)
    if not REPOSITORY_PATTERN.fullmatch(repository):
        raise ValueError(f"Invalid GitHub repository: {repository}")
    if not pull_requests:
        raise ValueError("No merged pull requests were found for this release")

    grouped: dict[str, list[str]] = defaultdict(list)
    for pull_request in pull_requests:
        section, icon = _section_and_icon(pull_request.title)
        title = pull_request.title.rstrip(".")
        pull_request_link = f"[#{pull_request.number}]({pull_request.url})"
        author_link = f"[@{pull_request.author}](https://github.com/{pull_request.author})"
        grouped[section].append(f"* {icon} {title}. PR {pull_request_link} by {author_link}.")

    lines = [f"## {version} ({release_date})", ""]
    for section in SECTION_ORDER:
        if entries := grouped.get(section):
            lines.extend((f"### {section}", "", *entries, ""))
    return "\n".join(lines).rstrip() + "\n"


def prepend_release_notes(path: Path, section: str) -> None:
    """Prepend a generated version section to the cumulative notes file."""

    heading = "# Release Notes\n"
    current = path.read_text(encoding="utf-8") if path.exists() else heading
    if not current.startswith(heading):
        raise ValueError(f"{path} must start with '# Release Notes'")
    remainder = current[len(heading) :].lstrip("\n")
    path.write_text(f"{heading}\n{section}\n{remainder}".rstrip() + "\n", encoding="utf-8")


def extract_release_body(path: Path, version: str) -> str:
    """Extract one version's body, excluding its redundant version heading."""

    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid release version: {version}")
    content = path.read_text(encoding="utf-8")
    heading = re.compile(rf"^## {re.escape(version)} \([^\n]+\)\s*$", re.MULTILINE)
    match = heading.search(content)
    if match is None:
        raise ValueError(f"Release notes do not contain version {version}")
    next_heading = re.search(r"^## \S", content[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(content)
    body = content[match.end() : end].strip()
    if not body:
        raise ValueError(f"Release notes for version {version} are empty")
    return body + "\n"


@app.command()
def generate(
    version: Annotated[str, typer.Option(help="Version being prepared.")],
    release_date: Annotated[str, typer.Option("--date", help="Release date in YYYY-MM-DD format.")],
    repository: Annotated[str, typer.Option(help="GitHub repository in owner/name form.")],
    notes: Annotated[Path, typer.Option(help="Cumulative release-notes file.")] = Path("release-notes.md"),
    from_ref: Annotated[str | None, typer.Option(help="Previous release tag or Git ref.")] = None,
    to_ref: Annotated[str, typer.Option(help="Final Git ref included in the release.")] = "HEAD",
) -> None:
    """Generate and prepend notes from merged PRs between two Git refs."""

    pull_requests = github_pull_requests(repository, from_ref, to_ref)
    section = render_section(version, release_date, pull_requests, repository)
    prepend_release_notes(notes, section)
    typer.echo(f"Added {len(pull_requests)} pull request(s) to {notes}")


@app.command("extract")
def extract_command(
    version: Annotated[str, typer.Option(help="Version to extract.")],
    notes: Annotated[Path, typer.Option(help="Cumulative release-notes file.")] = Path("release-notes.md"),
    output: Annotated[Path | None, typer.Option(help="Destination file; stdout when omitted.")] = None,
) -> None:
    """Extract one version's body for a GitHub Release."""

    body = extract_release_body(notes, version)
    if output is None:
        typer.echo(body, nl=False)
        return
    output.write_text(body, encoding="utf-8")
    typer.echo(f"Wrote release notes for {version} to {output}")


if __name__ == "__main__":
    app()
