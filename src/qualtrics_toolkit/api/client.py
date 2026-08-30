from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx

from .domains import ResponseImportsExportsAPI, SurveyDefinitionsAPI, SurveysAPI
from .exceptions import QualtricsAPIError
from .models import (
    ExportProgress,
    ExportResult,
    FilenameStrategy,
    HTTPMethod,
    ResponseExportRequest,
    SurveyPage,
    SurveySummary,
)
from .settings import QualtricsSettings


class QualtricsClient:
    """Authenticated API v3 transport with domain-specific resources."""

    def __init__(
        self,
        api_token: str | None = None,
        *,
        data_center: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        settings = QualtricsSettings()
        overrides: dict[str, Any] = {
            key: value
            for key, value in {
                "api_token": api_token,
                "data_center": data_center,
                "base_url": base_url,
            }.items()
            if value is not None
        }
        settings = settings.model_copy(update=overrides)
        if not settings.api_token:
            raise ValueError("api_token is required")
        if not settings.base_url and not settings.data_center:
            raise ValueError("provide data_center or base_url")
        resolved_url = settings.base_url or (f"https://{settings.data_center}.qualtrics.com/API/v3")
        self._http = httpx.Client(
            base_url=resolved_url.rstrip("/"),
            headers={"X-API-TOKEN": settings.api_token, "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )
        self.surveys = SurveysAPI(self)
        self.survey_definitions = SurveyDefinitionsAPI(self)
        self.responses = ResponseImportsExportsAPI(self)
        self.response_exports = self.responses

    @classmethod
    def from_env(cls, **kwargs: Any) -> QualtricsClient:
        """Compatibility alias; ``QualtricsClient()`` also reads the environment."""
        return cls(**kwargs)

    def __enter__(self) -> QualtricsClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def request(
        self,
        method: HTTPMethod,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Call an arbitrary JSON API endpoint using the configured transport."""
        response = self._http.request(
            method, path, params=params, json=json, content=content, headers=headers
        )
        self._raise_for_error(response)
        if response.status_code == 204:
            return None
        payload = response.json()
        return payload.get("result", payload)

    def download(self, path: str) -> httpx.Response:
        """Download binary content using the configured authentication."""
        response = self._http.get(path)
        self._raise_for_error(response)
        return response

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> None:
        if not response.is_error:
            return
        request_id = None
        message = response.text
        try:
            payload = response.json()
            request_id = payload.get("meta", {}).get("requestId")
            message = payload.get("meta", {}).get("error", {}).get("errorMessage") or message
        except ValueError:
            pass
        raise QualtricsAPIError(
            message or f"Qualtrics returned HTTP {response.status_code}",
            status_code=response.status_code,
            request_id=request_id,
        )

    # Compatibility delegates for the original flat client API.
    def list_surveys(self, *, offset: int | None = None) -> SurveyPage:
        return self.surveys.list(offset=offset)

    def iter_surveys(self) -> Iterator[SurveySummary]:
        return self.surveys.iter()

    def get_survey(self, survey_id: str) -> dict[str, Any]:
        return self.surveys.get(survey_id)

    def start_response_export(
        self, survey_id: str, options: ResponseExportRequest | None = None
    ) -> ExportProgress:
        return self.response_exports.start(survey_id, options)

    def get_response_export_progress(self, survey_id: str, progress_id: str) -> ExportProgress:
        return self.response_exports.progress(survey_id, progress_id)

    def wait_for_response_export(
        self,
        survey_id: str,
        progress_id: str,
        *,
        poll_interval: float = 1.0,
        timeout: float = 900.0,
    ) -> ExportProgress:
        return self.response_exports.wait(
            survey_id, progress_id, poll_interval=poll_interval, timeout=timeout
        )

    def download_response_export(self, survey_id: str, file_id: str) -> httpx.Response:
        return self.response_exports.download(survey_id, file_id)

    def export_responses(
        self,
        survey_id: str,
        output: str | Path,
        *,
        options: ResponseExportRequest | None = None,
        naming: FilenameStrategy = FilenameStrategy.SURVEY_ID,
        filename: str | None = None,
        survey_name: str | None = None,
        poll_interval: float = 1.0,
        timeout: float = 900.0,
    ) -> ExportResult:
        return self.response_exports.export(
            survey_id,
            output,
            options=options,
            naming=naming,
            filename=filename,
            survey_name=survey_name,
            poll_interval=poll_interval,
            timeout=timeout,
        )
