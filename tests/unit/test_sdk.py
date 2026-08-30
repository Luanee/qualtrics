import json
from pathlib import Path

import httpx

from qualtrics import QualtricsClient as RootQualtricsClient
from qualtrics.api import (
    FilenameStrategy,
    QualtricsClient,
    ResponseExportRequest,
    SurveyUpdateRequest,
)


def test_client_is_exported_at_package_root() -> None:
    assert RootQualtricsClient is QualtricsClient


def test_client_reads_environment_and_explicit_values_override(monkeypatch) -> None:
    monkeypatch.setenv("QUALTRICS_API_TOKEN", "environment-token")
    monkeypatch.setenv("QUALTRICS_DATA_CENTER", "fra1")

    with QualtricsClient() as environment_client:
        assert environment_client._http.headers["X-API-TOKEN"] == "environment-token"
        assert str(environment_client._http.base_url) == "https://fra1.qualtrics.com/API/v3/"

    with QualtricsClient(api_token="explicit-token", data_center="ca1") as explicit_client:
        assert explicit_client._http.headers["X-API-TOKEN"] == "explicit-token"
        assert str(explicit_client._http.base_url) == "https://ca1.qualtrics.com/API/v3/"


def test_export_responses_with_survey_id_filename(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "POST":
            assert json.loads(request.content)["useLabels"] is True
            return httpx.Response(
                200,
                json={
                    "result": {"progressId": "ES_1", "percentComplete": 0, "status": "inProgress"}
                },
            )
        if path.endswith("/ES_1"):
            return httpx.Response(
                200,
                json={"result": {"fileId": "FILE_1", "percentComplete": 100, "status": "complete"}},
            )
        if path.endswith("/FILE_1/file"):
            return httpx.Response(
                200, content=b"zip-content", headers={"content-type": "application/zip"}
            )
        raise AssertionError(f"Unexpected request: {request.method} {path}")

    with QualtricsClient(
        "token",
        base_url="https://example.qualtrics.com/API/v3",
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.export_responses(
            "SV_123",
            tmp_path,
            options=ResponseExportRequest(format="csv", useLabels=True),
            poll_interval=0,
        )

    assert Path(result.path).name == "SV_123.zip"
    assert Path(result.path).read_bytes() == b"zip-content"


def test_custom_filename_does_not_duplicate_extension(tmp_path: Path) -> None:
    with QualtricsClient("token", base_url="https://example.qualtrics.com/API/v3") as client:
        target = client.response_exports._export_path(
            tmp_path,
            httpx.Response(200),
            request=ResponseExportRequest(),
            naming=FilenameStrategy.CUSTOM,
            filename="annual-report.zip",
            survey_id="SV_123",
            survey_name=None,
        )
    assert target.name == "annual-report.zip"


def test_surveys_crud_paths_and_update_model() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"result": {"id": "SV_1", "name": "Annual"}})
        assert json.loads(request.content) == {"name": "Renamed", "isActive": True}
        return httpx.Response(200, json={"result": {}})

    with QualtricsClient(
        "token", base_url="https://example.test/API/v3", transport=httpx.MockTransport(handler)
    ) as client:
        assert client.surveys.get("SV_1")["name"] == "Annual"
        client.surveys.update("SV_1", SurveyUpdateRequest(name="Renamed", isActive=True))

    assert seen == [("GET", "/API/v3/surveys/SV_1"), ("PUT", "/API/v3/surveys/SV_1")]


def test_response_filters_and_imports(tmp_path: Path) -> None:
    source = tmp_path / "responses.csv"
    source.write_text("ResponseId,QID1\nR_1,Yes\n", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/filters"):
            return httpx.Response(
                200, json={"result": {"elements": [{"filterId": "FL_1", "name": "Complete"}]}}
            )
        if request.method == "POST" and request.headers["content-type"].startswith("text/csv"):
            assert request.content == source.read_bytes()
            return httpx.Response(
                200, json={"result": {"progressId": "IM_1", "status": "inProgress"}}
            )
        if request.method == "POST":
            assert json.loads(request.content) == {
                "fileUrl": "https://example.test/r.csv",
                "format": "csv",
            }
            return httpx.Response(
                200, json={"result": {"progressId": "IM_2", "status": "inProgress"}}
            )
        return httpx.Response(
            200,
            json={"result": {"progressId": "IM_1", "percentComplete": 100, "status": "complete"}},
        )

    with QualtricsClient(
        "token", base_url="https://example.test/API/v3", transport=httpx.MockTransport(handler)
    ) as client:
        assert client.responses.list_filters("SV_1").elements[0].filter_id == "FL_1"
        assert client.responses.import_file("SV_1", source).progress_id == "IM_1"
        assert (
            client.responses.import_url("SV_1", "https://example.test/r.csv").progress_id == "IM_2"
        )
        assert (
            client.responses.wait_for_import("SV_1", "IM_1", poll_interval=0).status == "complete"
        )
