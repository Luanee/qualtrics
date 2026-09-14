import json
import subprocess
from pathlib import Path

import pytest
from scripts import prepare_release
from scripts.prepare_release import (
    PullRequest,
    extract_release_body,
    github_pull_requests,
    prepend_release_notes,
    render_section,
    suggest_release_label,
)
from typer.testing import CliRunner


def pull_request(
    number: int,
    title: str,
    author: str = "octocat",
    labels: tuple[str, ...] = (),
) -> PullRequest:
    return PullRequest(
        number=number,
        title=title,
        author=author,
        url=f"https://github.com/Luanee/qualtrics/pull/{number}",
        merged_at=f"2026-08-{number:02d}T12:00:00Z",
        labels=labels,
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


def test_render_section_uses_plain_pr_label_before_title_prefix() -> None:
    rendered = render_section(
        "0.4.0",
        "2026-08-30",
        [pull_request(12, "fix: add a new export", labels=("enhancement",))],
        "Luanee/qualtrics",
    )

    assert "### Features" in rendered
    assert "### Fixes" not in rendered
    assert "PR [#12]" in rendered


def test_render_section_rejects_conflicting_category_labels() -> None:
    with pytest.raises(ValueError, match=r"PR #12 has conflicting release labels: bug, enhancement"):
        render_section(
            "0.4.0",
            "2026-08-30",
            [pull_request(12, "Add a new export", labels=("bug", "enhancement"))],
            "Luanee/qualtrics",
        )


def test_render_section_groups_existing_dependency_and_actions_labels_as_internal() -> None:
    rendered = render_section(
        "0.4.0",
        "2026-08-30",
        [pull_request(12, "Update CI dependencies", labels=("dependencies", "github_actions"))],
        "Luanee/qualtrics",
    )

    assert "### Internal" in rendered
    assert "### Other changes" not in rendered


def test_render_section_prefers_specific_category_to_dependency_label() -> None:
    rendered = render_section(
        "0.4.0",
        "2026-08-30",
        [pull_request(12, "Fix dependency loading", labels=("bug", "dependencies"))],
        "Luanee/qualtrics",
    )

    assert "### Fixes" in rendered
    assert "### Internal" not in rendered


def test_github_pull_requests_retains_pr_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([
        "abc123",
        json.dumps([
            {
                "number": 12,
                "title": "Update guide",
                "html_url": "https://github.com/Luanee/qualtrics/pull/12",
                "merged_at": "2026-08-12T12:00:00Z",
                "user": {"login": "alice"},
                "labels": [{"name": "documentation"}, {"name": "needs-review"}],
            }
        ]),
    ])
    monkeypatch.setattr(prepare_release, "_run", lambda *command: next(responses))

    pull_requests = github_pull_requests("Luanee/qualtrics", "v0.3.0")

    assert pull_requests[0].labels == ("documentation", "needs-review")
    assert "### Documentation" in render_section("0.4.0", "2026-08-30", pull_requests, "Luanee/qualtrics")


@pytest.mark.parametrize(
    ("title", "branch", "files", "expected"),
    [
        ("feat(ui): add export filters", "work/change", ["src/qualtrics/ui/report.py"], "enhancement"),
        ("Improve API errors", "fix/api-errors", ["src/qualtrics/api/client.py"], "bug"),
        ("Update guide", "work/guide", ["docs/index.md", "README.md"], "documentation"),
        ("Update guide and parser", "work/mixed", ["docs/index.md", "src/qualtrics/api/client.py"], None),
    ],
)
def test_suggest_release_label_uses_clear_pr_evidence(
    title: str,
    branch: str,
    files: list[str],
    expected: str | None,
) -> None:
    assert suggest_release_label(title, branch, files) == expected


def test_apply_release_label_assigns_an_inferred_category(monkeypatch: pytest.MonkeyPatch) -> None:
    assigned: list[str] = []

    def fake_gh(*command: str) -> str:
        if command[:3] == ("gh", "label", "list"):
            return json.dumps([
                {"name": label}
                for label in ("enhancement", "bug", "performance", "refactor", "documentation", "internal")
            ])
        if command[:3] == ("gh", "api", "--paginate"):
            return ""
        if command[:4] == ("gh", "api", "--method", "POST"):
            assigned.append(command[-1].removeprefix("labels[]="))
            return "[]"
        raise AssertionError(f"Unexpected GitHub command: {command}")

    monkeypatch.setattr(prepare_release, "_run", fake_gh)
    event = {
        "pull_request": {
            "number": 12,
            "title": "feat: add export filters",
            "head": {"ref": "work/export-filters"},
            "labels": [],
        }
    }

    label = prepare_release.apply_release_label(event, "Luanee/qualtrics")

    assert label == "enhancement"
    assert assigned == ["enhancement"]


def test_apply_release_label_keeps_manual_category(monkeypatch: pytest.MonkeyPatch) -> None:
    assigned: list[str] = []

    def fake_gh(*command: str) -> str:
        if command[:3] == ("gh", "label", "list"):
            return json.dumps([
                {"name": label}
                for label in ("enhancement", "bug", "performance", "refactor", "documentation", "internal")
            ])
        if command[:4] == ("gh", "api", "--method", "POST"):
            assigned.append(command[-1].removeprefix("labels[]="))
            return "[]"
        raise AssertionError(f"Unexpected GitHub command: {command}")

    monkeypatch.setattr(prepare_release, "_run", fake_gh)
    event = {
        "pull_request": {
            "number": 12,
            "title": "feat: add export filters",
            "head": {"ref": "feat/export-filters"},
            "labels": [{"name": "bug"}],
        }
    }

    assert prepare_release.apply_release_label(event, "Luanee/qualtrics") is None
    assert assigned == []


def test_apply_release_label_respects_category_added_after_event(monkeypatch: pytest.MonkeyPatch) -> None:
    assigned: list[str] = []

    def fake_gh(*command: str) -> str:
        if command[:3] == ("gh", "label", "list"):
            return json.dumps([
                {"name": label}
                for label in ("enhancement", "bug", "performance", "refactor", "documentation", "internal")
            ])
        if command[:3] == ("gh", "api", "--paginate"):
            return "bug"
        if command[:4] == ("gh", "api", "--method", "POST"):
            assigned.append(command[-1].removeprefix("labels[]="))
            return "[]"
        raise AssertionError(f"Unexpected GitHub command: {command}")

    monkeypatch.setattr(prepare_release, "_run", fake_gh)
    event = {
        "pull_request": {
            "number": 12,
            "title": "feat: add export filters",
            "head": {"ref": "work/export-filters"},
            "labels": [],
        }
    }

    assert prepare_release.apply_release_label(event, "Luanee/qualtrics") is None
    assert assigned == []


def test_apply_release_label_reuses_existing_documentation_label(monkeypatch: pytest.MonkeyPatch) -> None:
    labels = {"enhancement", "bug", "documentation", "dependencies", "github_actions", "release"}
    created: list[str] = []
    assigned: list[str] = []

    def fake_gh(*command: str) -> str:
        if command[:3] == ("gh", "api", "--paginate"):
            return "docs/index.md\nREADME.md" if command[3].endswith("/files") else "needs-review"
        if command[:3] == ("gh", "label", "list"):
            return json.dumps([{"name": label} for label in labels])
        if command[:3] == ("gh", "label", "create"):
            created.append(command[3])
            labels.add(command[3])
            return ""
        if command[:4] == ("gh", "api", "--method", "POST"):
            assigned.append(command[-1].removeprefix("labels[]="))
            return "[]"
        raise AssertionError(f"Unexpected GitHub command: {command}")

    monkeypatch.setattr(prepare_release, "_run", fake_gh)
    event = {
        "pull_request": {
            "number": 12,
            "title": "Update documentation",
            "head": {"ref": "work/docs-update"},
            "labels": [{"name": "needs-review"}],
        }
    }

    label = prepare_release.apply_release_label(event, "Luanee/qualtrics")

    assert label == "documentation"
    assert created == ["performance", "refactor", "internal"]
    assert assigned == ["documentation"]


def test_apply_release_label_seeds_categories_without_guessing_pr_type(monkeypatch: pytest.MonkeyPatch) -> None:
    labels = {"enhancement", "bug", "documentation", "dependencies", "github_actions", "release"}
    created: list[str] = []
    assigned: list[str] = []

    def fake_gh(*command: str) -> str:
        if command[:3] == ("gh", "api", "--paginate"):
            return "docs/index.md\nsrc/qualtrics/api/client.py" if command[3].endswith("/files") else ""
        if command[:3] == ("gh", "label", "list"):
            return json.dumps([{"name": label} for label in labels])
        if command[:3] == ("gh", "label", "create"):
            created.append(command[3])
            labels.add(command[3])
            return ""
        if command[:4] == ("gh", "api", "--method", "POST"):
            assigned.append(command[-1].removeprefix("labels[]="))
            return "[]"
        raise AssertionError(f"Unexpected GitHub command: {command}")

    monkeypatch.setattr(prepare_release, "_run", fake_gh)
    event = {
        "pull_request": {
            "number": 12,
            "title": "Update the toolkit",
            "head": {"ref": "work/toolkit"},
            "labels": [],
        }
    }

    assert prepare_release.apply_release_label(event, "Luanee/qualtrics") is None
    assert created == ["performance", "refactor", "internal"]
    assert assigned == []


def test_ensure_release_labels_accepts_a_label_created_by_another_run(monkeypatch: pytest.MonkeyPatch) -> None:
    labels = {"enhancement", "bug", "performance", "refactor", "documentation"}

    def fake_gh(*command: str) -> str:
        if command[:3] == ("gh", "label", "list"):
            return json.dumps([{"name": label} for label in labels])
        if command[:3] == ("gh", "label", "create"):
            labels.add("internal")
            raise subprocess.CalledProcessError(1, command, stderr="already exists")
        raise AssertionError(f"Unexpected GitHub command: {command}")

    monkeypatch.setattr(prepare_release, "_run", fake_gh)

    prepare_release.ensure_release_labels("Luanee/qualtrics")

    assert "internal" in labels


def test_label_pr_command_reads_event_and_assigns_label(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps({
            "pull_request": {
                "number": 12,
                "title": "fix: preserve filenames",
                "head": {"ref": "work/filenames"},
                "labels": [],
            }
        }),
        encoding="utf-8",
    )
    assigned: list[str] = []

    def fake_gh(*command: str) -> str:
        if command[:3] == ("gh", "label", "list"):
            return json.dumps([
                {"name": label}
                for label in ("enhancement", "bug", "performance", "refactor", "documentation", "internal")
            ])
        if command[:3] == ("gh", "api", "--paginate"):
            return ""
        if command[:4] == ("gh", "api", "--method", "POST"):
            assigned.append(command[-1].removeprefix("labels[]="))
            return "[]"
        raise AssertionError(f"Unexpected GitHub command: {command}")

    monkeypatch.setattr(prepare_release, "_run", fake_gh)

    result = CliRunner().invoke(
        prepare_release.app,
        ["label-pr", "--event", str(event_path), "--repository", "Luanee/qualtrics"],
    )

    assert result.exit_code == 0, result.output
    assert assigned == ["bug"]


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
