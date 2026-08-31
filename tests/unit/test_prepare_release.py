from pathlib import Path

import pytest
from scripts.prepare_release import PullRequest, extract_release_body, prepend_release_notes, render_section


def pull_request(number: int, title: str, author: str = "octocat") -> PullRequest:
    return PullRequest(
        number=number,
        title=title,
        author=author,
        url=f"https://github.com/Luanee/qualtrics/pull/{number}",
        merged_at=f"2026-08-{number:02d}T12:00:00Z",
    )


def test_render_section_groups_pull_requests_and_attributes_authors() -> None:
    rendered = render_section(
        "0.4.0",
        "2026-08-30",
        [
            pull_request(12, "feat: add exports", "alice"),
            pull_request(15, "fix(api): preserve filenames", "bob"),
        ],
        "Luanee/qualtrics",
    )

    assert "## 0.4.0 (2026-08-30)" in rendered
    assert "### Features" in rendered
    assert (
        "* ✨ feat: add exports. PR [#12](https://github.com/Luanee/qualtrics/pull/12) "
        "by [@alice](https://github.com/alice)."
    ) in rendered
    assert "### Fixes" in rendered
    assert "PR [#15]" in rendered
    assert "/commit/" not in rendered


def test_render_section_rejects_release_without_pull_requests() -> None:
    with pytest.raises(ValueError, match="No merged pull requests"):
        render_section("0.4.0", "2026-08-30", [], "Luanee/qualtrics")


def test_prepend_release_notes_keeps_previous_releases(tmp_path: Path) -> None:
    notes = tmp_path / "release-notes.md"
    notes.write_text("# Release Notes\n\n## 0.3.0 (2026-08-01)\n\n* Initial release.\n", encoding="utf-8")

    prepend_release_notes(notes, "## 0.4.0 (2026-08-30)\n\n* Next release.\n")

    content = notes.read_text(encoding="utf-8")
    assert content.index("## 0.4.0") < content.index("## 0.3.0")


def test_extract_release_body_returns_only_requested_version(tmp_path: Path) -> None:
    notes = tmp_path / "release-notes.md"
    notes.write_text(
        "# Release Notes\n\n"
        "## 0.4.0 (2026-08-30)\n\n### Features\n\n* ✨ New feature. PR #4 by @alice.\n\n"
        "## 0.3.0 (2026-08-01)\n\n* Previous release.\n",
        encoding="utf-8",
    )

    body = extract_release_body(notes, "0.4.0")

    assert body == "### Features\n\n* ✨ New feature. PR #4 by @alice.\n"
    assert "0.3.0" not in body


def test_render_section_rejects_invalid_date() -> None:
    with pytest.raises(ValueError):
        render_section("0.4.0", "30-08-2026", [pull_request(1, "fix: something")], "Luanee/qualtrics")
