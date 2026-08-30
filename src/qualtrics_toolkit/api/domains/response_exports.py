from __future__ import annotations

import re
import time
from collections.abc import Iterator
from pathlib import Path

import httpx

from ..exceptions import QualtricsExportError
from ..models import (
    ExportProgress,
    ExportResult,
    FilenameStrategy,
    ImportFormat,
    ImportProgress,
    ResponseExportRequest,
    ResponseImportRequest,
    SurveyFilter,
    SurveyFilterPage,
)
from .base import APIDomain


class ResponseImportsExportsAPI(APIDomain):
    """Survey-response import/export jobs and saved export filters."""

    def list_filters(self, survey_id: str, *, offset: int | None = None) -> SurveyFilterPage:
        result = self._client.request(
            "GET", f"/surveys/{survey_id}/filters", params={"offset": offset} if offset else None
        )
        return SurveyFilterPage.model_validate(result)

    def iter_filters(self, survey_id: str) -> Iterator[SurveyFilter]:
        next_path: str | None = f"/surveys/{survey_id}/filters"
        while next_path:
            page = SurveyFilterPage.model_validate(self._client.request("GET", next_path))
            yield from page.elements
            next_path = page.next_page

    def import_file(
        self,
        survey_id: str,
        source: str | Path,
        *,
        format: ImportFormat = ImportFormat.CSV,
    ) -> ImportProgress:
        path = Path(source)
        result = self._client.request(
            "POST",
            f"/surveys/{survey_id}/import-responses",
            content=path.read_bytes(),
            headers={"Content-Type": f"text/{format.value}; charset=utf-8"},
        )
        return ImportProgress.model_validate(result)

    def import_url(
        self,
        survey_id: str,
        file_url: str,
        *,
        format: ImportFormat = ImportFormat.CSV,
    ) -> ImportProgress:
        request = ResponseImportRequest(fileUrl=file_url, format=format)
        result = self._client.request(
            "POST",
            f"/surveys/{survey_id}/import-responses",
            json=request.model_dump(by_alias=True, mode="json"),
        )
        return ImportProgress.model_validate(result)

    def import_progress(self, survey_id: str, progress_id: str) -> ImportProgress:
        result = self._client.request("GET", f"/surveys/{survey_id}/import-responses/{progress_id}")
        return ImportProgress.model_validate(result)

    def wait_for_import(
        self,
        survey_id: str,
        progress_id: str,
        *,
        poll_interval: float = 1.0,
        timeout: float = 900.0,
    ) -> ImportProgress:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            progress = self.import_progress(survey_id, progress_id)
            if progress.status == "complete":
                return progress
            if progress.status == "failed":
                raise QualtricsExportError(f"Import {progress_id} failed")
            time.sleep(poll_interval)
        raise QualtricsExportError(f"Import {progress_id} did not finish within {timeout:g}s")

    def start(self, survey_id: str, options: ResponseExportRequest | None = None) -> ExportProgress:
        request = options or ResponseExportRequest()
        result = self._client.request(
            "POST",
            f"/surveys/{survey_id}/export-responses",
            json=request.model_dump(by_alias=True, exclude_none=True, mode="json"),
        )
        return ExportProgress.model_validate(result)

    def progress(self, survey_id: str, progress_id: str) -> ExportProgress:
        result = self._client.request("GET", f"/surveys/{survey_id}/export-responses/{progress_id}")
        return ExportProgress.model_validate(result)

    def wait(
        self,
        survey_id: str,
        progress_id: str,
        *,
        poll_interval: float = 1.0,
        timeout: float = 900.0,
    ) -> ExportProgress:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            progress = self.progress(survey_id, progress_id)
            if progress.status == "complete" and progress.file_id:
                return progress
            if progress.status == "failed":
                raise QualtricsExportError(f"Export {progress_id} failed")
            time.sleep(poll_interval)
        raise QualtricsExportError(f"Export {progress_id} did not finish within {timeout:g}s")

    def download(self, survey_id: str, file_id: str) -> httpx.Response:
        return self._client.download(f"/surveys/{survey_id}/export-responses/{file_id}/file")

    def export(
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
        request = options or ResponseExportRequest()
        started = self.start(survey_id, request)
        if not started.progress_id:
            raise QualtricsExportError("Qualtrics did not return a progressId")
        progress = self.wait(
            survey_id, started.progress_id, poll_interval=poll_interval, timeout=timeout
        )
        if not progress.file_id:
            raise QualtricsExportError("Completed export did not contain a fileId")
        response = self.download(survey_id, progress.file_id)
        if naming == FilenameStrategy.SURVEY_NAME and not survey_name:
            survey = self._client.surveys.get(survey_id)
            survey_name = survey.get("name") or survey.get("SurveyName")
        target = self._export_path(
            Path(output),
            response,
            request=request,
            naming=naming,
            filename=filename,
            survey_id=survey_id,
            survey_name=survey_name,
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        return ExportResult(
            survey_id=survey_id,
            progress_id=started.progress_id,
            file_id=progress.file_id,
            path=str(target),
            format=request.format,
            continuation_token=progress.continuation_token,
        )

    @staticmethod
    def _export_path(
        output: Path,
        response: httpx.Response,
        *,
        request: ResponseExportRequest,
        naming: FilenameStrategy,
        filename: str | None,
        survey_id: str,
        survey_name: str | None,
    ) -> Path:
        if output.suffix:
            return output
        disposition = response.headers.get("content-disposition", "")
        remote_match = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)', disposition, re.I)
        remote_name = remote_match.group(1) if remote_match else None
        if naming == FilenameStrategy.CUSTOM:
            if not filename:
                raise ValueError("filename is required when naming='custom'")
            stem = filename
        elif naming == FilenameStrategy.SURVEY_NAME:
            stem = survey_name or survey_id
        elif naming == FilenameStrategy.QUALTRICS and remote_name:
            return output / Path(remote_name).name
        else:
            stem = survey_id
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or survey_id
        suffix = ".zip" if request.compress else f".{request.format}"
        return output / (
            safe_stem if safe_stem.casefold().endswith(suffix) else f"{safe_stem}{suffix}"
        )


# Compatibility name for callers that only use the export workflow.
ResponseExportsAPI = ResponseImportsExportsAPI
