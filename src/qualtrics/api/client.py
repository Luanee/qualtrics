from __future__ import annotations

import math
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx

from .domains import ResponseImportsExportsAPI, SurveyDefinitionsAPI, SurveyQuotasAPI, SurveysAPI
from .exceptions import QualtricsAPIError
from .models import (
    ExportCallback,
    ExportProgress,
    ExportResult,
    FilenameStrategy,
    HTTPMethod,
    ResponseExportRequest,
    SurveyPage,
    SurveyQuota,
    SurveyQuotaPage,
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
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be nonnegative")
        if not math.isfinite(retry_backoff) or retry_backoff < 0:
            raise ValueError("retry_backoff must be finite and nonnegative")
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
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
        self.survey_quotas = SurveyQuotasAPI(self)
        self.quotas = self.survey_quotas
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
        response = self._request_with_retries(
            method,
            path,
            params=params,
            json=json,
            content=content,
            headers=headers,
        )
        self._raise_for_error(response)
        if response.status_code == 204:
            return None
        payload = response.json()
        return payload.get("result", payload)

    def download(self, path: str) -> httpx.Response:
        """Download binary content using the configured authentication."""
        response = self._request_with_retries("GET", path)
        self._raise_for_error(response)
        return response

    def _request_with_retries(self, method: HTTPMethod, path: str, **kwargs: Any) -> httpx.Response:
        """Retry reads and failures known to occur before a request was sent.

        A mutation's response or read timeout can be ambiguous: retrying could
        create a second export/import or repeat another write operation.
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = self._http.request(method, path, **kwargs)
            except httpx.TransportError as error:
                safe = method == "GET" or isinstance(
                    error, (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)
                )
                if not safe or attempt == self.max_retries:
                    raise
                time.sleep(self._retry_delay(attempt))
                continue
            if method != "GET" or response.status_code not in {408, 429, 500, 502, 503, 504}:
                return response
            if attempt == self.max_retries:
                return response
            delay = self._retry_delay(attempt, response.headers.get("Retry-After"))
            response.close()
            time.sleep(delay)
        raise AssertionError("Retry loop must return a response or raise")  # pragma: no cover

    def _retry_delay(self, attempt: int, retry_after: str | None = None) -> float:
        backoff = min(self.retry_backoff * 2 ** min(attempt, 30), 60.0)
        if retry_after:
            try:
                seconds = float(retry_after)
            except ValueError:
                try:
                    timestamp = parsedate_to_datetime(retry_after)
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=UTC)
                    seconds = (timestamp - datetime.now(UTC)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    return backoff
            if math.isfinite(seconds):
                return max(backoff, seconds)
        return backoff

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

    def list_survey_quotas(self, survey_id: str, *, offset: int | None = None) -> SurveyQuotaPage:
        return self.survey_quotas.list(survey_id, offset=offset)

    def iter_survey_quotas(self, survey_id: str) -> Iterator[SurveyQuota]:
        return self.survey_quotas.iter(survey_id)

    def start_response_export(self, survey_id: str, options: ResponseExportRequest | None = None) -> ExportProgress:
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
        on_progress: ExportCallback | None = None,
    ) -> ExportProgress:
        return self.response_exports.wait(
            survey_id, progress_id, poll_interval=poll_interval, timeout=timeout, on_progress=on_progress
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
        on_progress: ExportCallback | None = None,
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
            on_progress=on_progress,
        )
