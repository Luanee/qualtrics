from pathlib import Path

import pytest
from scripts.prepare_release import prepend_release_notes, render_section


def test_render_section_groups_conventional_commits() -> None:
    rendered = render_section(
        "0.4.0",
        "2026-08-30",
        [("a" * 40, "feat: add exports"), ("b" * 40, "fix(api): preserve filenames")],
        "Luanee/qualtrics",
    )

    assert "## 0.4.0 (2026-08-30)" in rendered
    assert "### Features" in rendered
    assert "✨ add exports" in rendered
    assert "### Fixes" in rendered
    assert "https://github.com/Luanee/qualtrics/commit/" in rendered


def test_prepend_release_notes_keeps_previous_releases(tmp_path: Path) -> None:
    notes = tmp_path / "release-notes.md"
    notes.write_text("# Release Notes\n\n## 0.3.0 (2026-08-01)\n\n* Initial release.\n", encoding="utf-8")

    prepend_release_notes(notes, "## 0.4.0 (2026-08-30)\n\n* Next release.\n")

    content = notes.read_text(encoding="utf-8")
    assert content.index("## 0.4.0") < content.index("## 0.3.0")


def test_render_section_rejects_invalid_date() -> None:
    with pytest.raises(ValueError):
        render_section("0.4.0", "30-08-2026", [], "Luanee/qualtrics")
