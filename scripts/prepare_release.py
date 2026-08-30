"""Generate a dated release-notes section from conventional commit subjects."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from collections import defaultdict
from pathlib import Path

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
SECTION_ORDER = ("Features", "Fixes", "Performance", "Refactors", "Documentation", "Internal", "Other changes")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[a-zA-Z0-9.-]+)?$")
COMMIT_PATTERN = re.compile(r"^(?P<kind>[a-z]+)(?:\([^)]+\))?(?:!)?:\s*(?P<message>.+)$")


def git_commits(from_ref: str | None) -> list[tuple[str, str]]:
    revision = f"{from_ref}..HEAD" if from_ref else "HEAD"
    result = subprocess.run(
        ["git", "log", "--reverse", "--format=%H%x1f%s", revision],
        check=True,
        capture_output=True,
        text=True,
    )
    commits: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        commit_hash, separator, subject = line.partition("\x1f")
        if separator and subject:
            commits.append((commit_hash, subject))
    return commits


def render_section(version: str, release_date: str, commits: list[tuple[str, str]], repository: str) -> str:
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid release version: {version}")
    dt.date.fromisoformat(release_date)
    grouped: dict[str, list[str]] = defaultdict(list)
    for commit_hash, subject in commits:
        match = COMMIT_PATTERN.match(subject)
        kind = match.group("kind") if match else ""
        message = match.group("message") if match else subject
        section, emoji = SECTIONS.get(kind, ("Other changes", "🔖"))
        message = message.rstrip(".")
        link = f"https://github.com/{repository}/commit/{commit_hash}"
        grouped[section].append(f"* {emoji} {message}. [{commit_hash[:7]}]({link})")
    if not grouped:
        grouped["Other changes"].append("* 🔖 Prepare release.")
    lines = [f"## {version} ({release_date})", ""]
    for section in SECTION_ORDER:
        if entries := grouped.get(section):
            lines.extend((f"### {section}", "", *entries, ""))
    return "\n".join(lines).rstrip() + "\n"


def prepend_release_notes(path: Path, section: str) -> None:
    heading = "# Release Notes\n"
    current = path.read_text(encoding="utf-8") if path.exists() else heading
    if not current.startswith(heading):
        raise ValueError(f"{path} must start with '# Release Notes'")
    remainder = current[len(heading) :].lstrip("\n")
    path.write_text(f"{heading}\n{section}\n{remainder}".rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--notes", type=Path, default=Path("release-notes.md"))
    parser.add_argument("--from-ref")
    args = parser.parse_args()
    section = render_section(args.version, args.date, git_commits(args.from_ref), args.repository)
    prepend_release_notes(args.notes, section)


if __name__ == "__main__":
    main()
