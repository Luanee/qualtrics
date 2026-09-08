from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from qualtrics.api import FilenameStrategy, QualtricsAPIError, QualtricsClient


def test_get_retries_rate_limits_then_service_failures(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("qualtrics.api.client.time.sleep", sleeps.append)
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        if attempts == 2:
            return httpx.Response(503)
        return httpx.Response(200, json={"result": {"name": "Survey"}})

    with QualtricsClient("token", base_url="https://example.test", transport=httpx.MockTransport(handler)) as client:
        assert client.surveys.get("SV_1")["name"] == "Survey"
    assert attempts == 3
    assert sleeps == [7, 2]


@pytest.mark.parametrize(
    "method,status,expected",
    [("GET", 503, 4), ("GET", 401, 1), ("GET", 403, 1), ("POST", 503, 1), ("PATCH", 429, 1), ("DELETE", 500, 1)],
)
def test_retries_are_bounded_and_do_not_repeat_mutations(method, status, expected) -> None:
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, json={"meta": {"error": {"errorMessage": "unavailable"}}})

    with (
        QualtricsClient(
            "token", base_url="https://example.test", retry_backoff=0, transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(QualtricsAPIError),
    ):
        client.request(method, "/resource")
    assert attempts == expected


@pytest.mark.parametrize(
    "method,exception,expected",
    [
        ("GET", httpx.ReadTimeout, 2),
        ("POST", httpx.ReadTimeout, 1),
        ("POST", httpx.ConnectTimeout, 2),
        ("GET", httpx.ConnectError, 2),
    ],
)
def test_retry_transport_errors_only_when_safe(method, exception, expected) -> None:
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise exception("temporary failure", request=request)
        return httpx.Response(200, json={"result": {}})

    with QualtricsClient(
        "token", base_url="https://example.test", retry_backoff=0, transport=httpx.MockTransport(handler)
    ) as client:
        if expected == 1:
            with pytest.raises(exception):
                client.request(method, "/resource")
        else:
            assert client.request(method, "/resource") == {}
    assert attempts == expected


def test_download_retries_and_complete_event_only_after_writing(tmp_path: Path) -> None:
    downloads = 0
    events = []

    def handler(request):
        nonlocal downloads
        if request.method == "POST":
            return httpx.Response(200, json={"result": {"progressId": "ES_1", "status": "inProgress"}})
        if request.url.path.endswith("/file"):
            downloads += 1
            return httpx.Response(502) if downloads == 1 else httpx.Response(200, content=b"archive")
        return httpx.Response(200, json={"result": {"fileId": "FILE_1", "status": "complete", "percentComplete": 100}})

    def callback(event):
        events.append(event)
        if event.stage == "complete":
            assert (tmp_path / "SV_1.zip").read_bytes() == b"archive"

    with QualtricsClient(
        "token", base_url="https://example.test", retry_backoff=0, transport=httpx.MockTransport(handler)
    ) as client:
        result = client.export_responses("SV_1", tmp_path, on_progress=callback, poll_interval=0)
    assert result.path == str(tmp_path / "SV_1.zip")
    assert downloads == 2
    assert [event.stage for event in events] == ["starting", "exporting", "downloading", "complete"]
    assert all(event.survey_id == "SV_1" for event in events)


def test_invalid_export_options_fail_before_starting() -> None:
    calls = []

    def handler(request):
        calls.append(request)
        raise AssertionError("Unexpected API call")

    with QualtricsClient("token", base_url="https://example.test", transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="filename"):
            client.export_responses("SV_1", "data", naming=FilenameStrategy.CUSTOM)
        with pytest.raises(ValueError, match="timeout"):
            client.export_responses("SV_1", "data", timeout=0)
    assert not calls


def test_retry_after_http_date_and_invalid_headers() -> None:
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    with QualtricsClient("token", base_url="https://example.test") as client:
        future = format_datetime(datetime.now(UTC) + timedelta(seconds=20), usegmt=True)
        assert 18 < client._retry_delay(0, future) <= 20
        assert client._retry_delay(2, "invalid") == 4
        assert client._retry_delay(2, "nan") == 4
        assert client._retry_delay(2, "-8") == 4


@pytest.mark.parametrize("options", [{"max_retries": -1}, {"retry_backoff": -1}, {"retry_backoff": float("nan")}])
def test_invalid_retry_settings_are_rejected(options) -> None:
    with pytest.raises(ValueError):
        QualtricsClient("token", base_url="https://example.test", **options)


def test_exhausted_download_retries_preserve_previous_output_and_emit_no_completion(tmp_path: Path) -> None:
    target = tmp_path / "SV_1.zip"
    target.write_bytes(b"previous snapshot")
    events = []
    downloads = 0

    def handler(request):
        nonlocal downloads
        if request.method == "POST":
            return httpx.Response(200, json={"result": {"progressId": "ES_1", "status": "inProgress"}})
        if request.url.path.endswith("/file"):
            downloads += 1
            return httpx.Response(503)
        return httpx.Response(200, json={"result": {"fileId": "FILE_1", "status": "complete", "percentComplete": 100}})

    with (
        QualtricsClient(
            "token", base_url="https://example.test", retry_backoff=0, transport=httpx.MockTransport(handler)
        ) as client,
        pytest.raises(QualtricsAPIError),
    ):
        client.export_responses("SV_1", target, on_progress=events.append)
    assert downloads == 4
    assert target.read_bytes() == b"previous snapshot"
    assert events[-1].stage == "downloading"
    assert "complete" not in [event.stage for event in events]


def test_failed_local_replace_preserves_previous_export_and_removes_partial_file(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "SV_1.zip"
    target.write_bytes(b"previous snapshot")
    events = []

    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"result": {"progressId": "ES_1", "status": "inProgress"}})
        if request.url.path.endswith("/file"):
            return httpx.Response(200, content=b"new snapshot")
        return httpx.Response(200, json={"result": {"fileId": "FILE_1", "status": "complete", "percentComplete": 100}})

    def fail_replace(*args):
        raise PermissionError("Cannot replace the export")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with (
        QualtricsClient("token", base_url="https://example.test", transport=httpx.MockTransport(handler)) as client,
        pytest.raises(PermissionError),
    ):
        client.export_responses("SV_1", target, on_progress=events.append)
    assert target.read_bytes() == b"previous snapshot"
    assert list(tmp_path.iterdir()) == [target]
    assert "complete" not in [event.stage for event in events]
