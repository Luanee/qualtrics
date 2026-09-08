from __future__ import annotations

import json
import threading
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from qualtrics.api import QualtricsClient
from qualtrics.cli import api
from qualtrics.cli.app import app


def install_client(monkeypatch, handler) -> None:
    monkeypatch.setattr(
        api,
        "_client",
        lambda *args, **kwargs: QualtricsClient(
            "token",
            base_url="https://example.test",
            retry_backoff=0,
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )


def test_cli_export_passes_controls_to_api_and_keeps_stdout_for_paths(tmp_path: Path, monkeypatch) -> None:
    sent = []

    def handler(request):
        if request.method == "POST":
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={"result": {"progressId": "ES_1", "status": "inProgress"}})
        if request.url.path.endswith("/file"):
            return httpx.Response(200, content=b"data")
        return httpx.Response(
            200,
            json={
                "result": {
                    "fileId": "FILE_1",
                    "status": "complete",
                    "percentComplete": 100,
                    "continuationToken": "NEXT",
                }
            },
        )

    install_client(monkeypatch, handler)
    result = CliRunner().invoke(
        app,
        [
            "api",
            "export",
            "SV_1",
            "-o",
            str(tmp_path),
            "--format",
            "json",
            "--no-compress",
            "--codes",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-02-01",
            "--question-id",
            "QID1",
            "--question-id",
            "QID2",
            "--embedded-data-id",
            "Department",
            "--metadata-id",
            "recordedDate",
            "--filter-id",
            "FL_1",
            "--limit",
            "10",
            "--display-order",
            "--label-columns",
            "--allow-continuation",
            "--continuation-token",
            "PREVIOUS",
            "--sort-by-last-modified-date",
            "--newline-replacement",
            "//",
            "--no-progress",
            "--retries",
            "0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert sent == [
        {
            "format": "json",
            "compress": False,
            "useLabels": False,
            "startDate": "2026-01-01T00:00:00Z",
            "endDate": "2026-02-01T00:00:00Z",
            "questionIds": ["QID1", "QID2"],
            "embeddedDataIds": ["Department"],
            "surveyMetadataIds": ["recordedDate"],
            "filterId": "FL_1",
            "limit": 10,
            "includeDisplayOrder": True,
            "includeLabelColumns": True,
            "allowContinuation": True,
            "continuationToken": "PREVIOUS",
            "sortByLastModifiedDate": True,
            "newlineReplacement": "//",
        }
    ]
    assert result.stdout.strip() == str(tmp_path / "SV_1.json")
    assert "NEXT" in result.stderr
    assert (tmp_path / "SV_1.json").read_bytes() == b"data"


@pytest.mark.parametrize(
    "arguments",
    [
        ["--batch-size", "0"],
        ["--retries", "-1"],
        ["--start-date", "yesterday"],
        ["--start-date", "2026-02-01", "--end-date", "2026-01-01"],
        ["--limit", "0"],
        ["--naming", "custom"],
        ["--question-id", ""],
        ["--timeout", "0"],
    ],
)
def test_bad_cli_options_fail_before_client_creation(tmp_path: Path, monkeypatch, arguments) -> None:
    def fail(*args, **kwargs):
        raise AssertionError("Client should not be created")

    monkeypatch.setattr(api, "_client", fail)
    result = CliRunner().invoke(app, ["api", "export", "SV_1", "-o", str(tmp_path), *arguments])
    assert result.exit_code == 2, result.output
    assert "Client should not be created" not in str(result.exception)


@pytest.mark.parametrize(
    "ids,arguments",
    [
        (["SV_1", "SV_1"], []),
        (["../escape"], []),
        (["SV_1", "SV_2"], ["--continuation-token", "SHARED"]),
    ],
)
def test_invalid_multi_survey_selection_is_rejected(tmp_path: Path, monkeypatch, ids, arguments) -> None:
    monkeypatch.setattr(api, "_client", lambda *args, **kwargs: pytest.fail("Unexpected client"))
    result = CliRunner().invoke(app, ["api", "export", *ids, "-o", str(tmp_path), *arguments])
    assert result.exit_code == 2, result.output


def test_concurrent_exports_do_not_overwrite_matching_remote_names(tmp_path: Path, monkeypatch) -> None:
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    active = 0
    highest = 0

    def handler(request):
        nonlocal active, highest
        survey_id = request.url.path.split("/")[2]
        if request.method == "POST":
            with lock:
                active += 1
                highest = max(highest, active)
            if survey_id in {"SV_1", "SV_2"}:
                barrier.wait(timeout=3)
            return httpx.Response(200, json={"result": {"progressId": "ES_1", "status": "inProgress"}})
        if request.url.path.endswith("/file"):
            with lock:
                active -= 1
            return httpx.Response(
                200, content=survey_id.encode(), headers={"Content-Disposition": 'filename="same.zip"'}
            )
        return httpx.Response(200, json={"result": {"fileId": "FILE_1", "status": "complete", "percentComplete": 100}})

    install_client(monkeypatch, handler)
    result = CliRunner().invoke(
        app,
        [
            "api",
            "export",
            "SV_1",
            "SV_2",
            "SV_3",
            "-o",
            str(tmp_path),
            "--naming",
            "qualtrics",
            "--batch-size",
            "2",
            "--no-progress",
        ],
    )
    assert result.exit_code == 0, result.output
    assert highest == 2
    for survey_id in ("SV_1", "SV_2", "SV_3"):
        assert (tmp_path / survey_id / "same.zip").read_text() == survey_id
    assert len(result.stdout.strip().splitlines()) == 3


def test_partial_failure_keeps_successful_download_and_exits_nonzero(tmp_path: Path, monkeypatch) -> None:
    def handler(request):
        if "/SV_BAD/" in request.url.path:
            return httpx.Response(403, json={"meta": {"error": {"errorMessage": "Access denied"}}})
        if request.method == "POST":
            return httpx.Response(200, json={"result": {"progressId": "ES_1", "status": "inProgress"}})
        if request.url.path.endswith("/file"):
            return httpx.Response(200, content=b"good")
        return httpx.Response(200, json={"result": {"fileId": "FILE_1", "status": "complete", "percentComplete": 100}})

    install_client(monkeypatch, handler)
    result = CliRunner().invoke(app, ["api", "export", "SV_BAD", "SV_GOOD", "-o", str(tmp_path)])
    assert result.exit_code == 1, result.output
    assert (tmp_path / "SV_GOOD.zip").read_bytes() == b"good"
    assert "SV_BAD" in result.stderr and "Access denied" in result.stderr
    assert "1/2" in result.stderr and "1 failed" in result.stderr
    assert "\x1b[" not in result.stderr
    assert result.stdout.strip() == str(tmp_path / "SV_GOOD.zip")


def test_default_batch_exports_surveys_one_at_a_time(tmp_path: Path, monkeypatch) -> None:
    active = None
    order = []

    def handler(request):
        nonlocal active
        survey_id = request.url.path.split("/")[2]
        if request.method == "POST":
            assert active is None
            active = survey_id
            order.append(survey_id)
            return httpx.Response(200, json={"result": {"progressId": "ES_1", "status": "inProgress"}})
        assert active == survey_id
        if request.url.path.endswith("/file"):
            active = None
            return httpx.Response(200, content=b"archive")
        return httpx.Response(200, json={"result": {"fileId": "FILE_1", "status": "complete", "percentComplete": 100}})

    install_client(monkeypatch, handler)
    result = CliRunner().invoke(app, ["api", "export", "SV_1", "SV_2", "SV_3", "-o", str(tmp_path), "--no-progress"])
    assert result.exit_code == 0, result.output
    assert order == ["SV_1", "SV_2", "SV_3"]
    assert result.stderr == ""


def test_progress_never_counts_worker_failure_as_success() -> None:
    from io import StringIO

    from rich.console import Console

    from qualtrics.api import ExportEvent
    from qualtrics.cli.export_progress import run_surveys

    output = StringIO()

    def worker(survey_id, on_progress):
        on_progress(ExportEvent(survey_id, "exporting", 100))
        on_progress(ExportEvent(survey_id, "downloading"))
        raise OSError("Disk full")

    results, failures = run_surveys(["SV_1"], worker, console=Console(file=output, force_terminal=False))
    assert not results and "SV_1" in failures
    assert "0/1 complete; 1 failed" in output.getvalue()
    assert "100%" not in output.getvalue()


def test_terminal_progress_includes_counts_elapsed_and_remaining() -> None:
    from io import StringIO

    from rich.console import Console

    from qualtrics.api import ExportEvent
    from qualtrics.cli.export_progress import run_surveys

    output = StringIO()

    def worker(survey_id, on_progress):
        on_progress(ExportEvent(survey_id, "starting"))
        on_progress(ExportEvent(survey_id, "exporting", 50))
        on_progress(ExportEvent(survey_id, "downloading"))
        on_progress(ExportEvent(survey_id, "complete", 100))
        return "path"

    results, failures = run_surveys(["SV_1"], worker, console=Console(file=output, force_terminal=True, width=140))
    assert results == {"SV_1": "path"} and not failures
    rendered = output.getvalue()
    assert "elapsed" in rendered and "remaining" in rendered and "1/1" in rendered
    assert "SV_1: complete" in rendered


def test_keyboard_interrupt_cancels_pending_surveys_and_active_polling(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent("""
        import os
        import signal
        import threading
        import time
        from concurrent.futures import CancelledError
        from qualtrics.api import ExportEvent
        from qualtrics.cli.export_progress import run_surveys

        started = []
        cancelled = []

        def worker(survey_id, on_progress):
            started.append(survey_id)
            if survey_id == "SV_1":
                threading.Timer(0.03, lambda: os.kill(os.getpid(), signal.SIGINT)).start()
            deadline = time.monotonic() + 0.3
            try:
                while time.monotonic() < deadline:
                    time.sleep(0.01)
                    on_progress(ExportEvent(survey_id, "exporting", 30))
            except CancelledError:
                cancelled.append(survey_id)
                raise
            return survey_id

        try:
            run_surveys(["SV_1", "SV_2", "SV_3", "SV_4"], worker, show_progress=False)
        except KeyboardInterrupt:
            assert started == ["SV_1"], started
            assert cancelled == ["SV_1"], cancelled
            print("interrupted; no later surveys started")
        else:
            raise AssertionError("KeyboardInterrupt was swallowed")
    """)
    environment = dict(os.environ, PYTHONPATH=str(Path(api.__file__).parents[2]))
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no later surveys started" in result.stdout
