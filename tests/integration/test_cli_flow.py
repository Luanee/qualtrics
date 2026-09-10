import json
from pathlib import Path

import httpx
import pytest
from click import unstyle
from typer import rich_utils
from typer.testing import CliRunner

from qualtrics.api import QualtricsClient
from qualtrics.cli import api
from qualtrics.cli.app import app

FLOW = {"Type": "Root", "FlowID": "FL_1", "Flow": [{"Type": "Block", "ID": "BL_1", "FlowID": "FL_2"}]}


def install_client(monkeypatch, handler) -> None:
    monkeypatch.setattr(
        api,
        "_client",
        lambda *args, **kwargs: QualtricsClient(
            "test-token",
            base_url="https://example.test/API/v3",
            retry_backoff=0,
            transport=httpx.MockTransport(handler),
            **kwargs,
        ),
    )


def test_flow_read_uses_authenticated_retry_transport() -> None:
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.path == "/API/v3/survey-definitions/SV_1/flow"
        assert request.headers["X-API-TOKEN"] == "test-token"
        return httpx.Response(503) if len(requests) == 1 else httpx.Response(200, json={"result": FLOW})

    with QualtricsClient(
        "test-token",
        base_url="https://example.test/API/v3",
        retry_backoff=0,
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.survey_definitions.get_flow("SV_1") == FLOW
    assert len(requests) == 2


def test_flow_cli_writes_nested_definition(tmp_path: Path, monkeypatch) -> None:
    install_client(monkeypatch, lambda request: httpx.Response(200, json={"result": FLOW}))
    output = tmp_path / "download" / "flow.json"
    result = CliRunner().invoke(app, ["api", "flow", "--survey-id", "SV_1", "-o", str(output)])
    assert result.exit_code == 0, result.output
    assert json.loads(output.read_text()) == FLOW
    assert result.stdout.strip() == str(output)


@pytest.mark.parametrize("response", [httpx.Response(403), httpx.Response(200, json={"result": []})])
def test_flow_cli_failure_preserves_existing_file(tmp_path: Path, monkeypatch, response) -> None:
    install_client(monkeypatch, lambda request: response)
    output = tmp_path / "flow.json"
    output.write_text("keep existing definition")
    result = CliRunner().invoke(app, ["api", "flow", "--survey-id", "SV_1", "-o", str(output), "--retries", "0"])
    assert result.exit_code == 1
    assert "Could not download survey flow" in result.output
    assert output.read_text() == "keep existing definition"


def test_build_accepts_flow_download_alongside_qsf(tmp_path: Path, survey_files) -> None:
    csv_path, qsf_path = survey_files
    flow = tmp_path / "flow.json"
    flow.write_text(json.dumps(FLOW))
    output = tmp_path / "entities"
    result = CliRunner().invoke(
        app, ["build", str(csv_path), "--qsf", str(qsf_path), "--flow", str(flow), "-o", str(output)]
    )
    assert result.exit_code == 0, result.output
    surveys = json.loads((output / "surveys.json").read_text())
    assert json.loads(surveys[0]["flow_definition_json"])["root"]["children"][0]["config"]["ID"] == "BL_1"


@pytest.mark.parametrize("force_terminal", [False, True], ids=["plain", "styled"])
def test_build_rejects_one_flow_for_multiple_surveys(tmp_path: Path, survey_files, monkeypatch, force_terminal) -> None:
    monkeypatch.setattr(rich_utils, "FORCE_TERMINAL", force_terminal)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    csv_path, _ = survey_files
    flow = tmp_path / "flow.json"
    flow.write_text(json.dumps(FLOW))
    output = tmp_path / "entities"
    result = CliRunner().invoke(app, ["build", str(csv_path), str(csv_path), "--flow", str(flow), "-o", str(output)])
    assert result.exit_code == 2
    assert "--flow can only be used with one CSV or ZIP" in unstyle(result.output)
    assert not output.exists()
