from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..models import SurveyPage, SurveySummary, SurveyUpdateRequest
from .base import APIDomain


class SurveysAPI(APIDomain):
    """Survey listing, retrieval, and update endpoints."""

    def list(self, *, offset: int | None = None) -> SurveyPage:
        result = self._client.request("GET", "/surveys", params={"offset": offset} if offset else None)
        return SurveyPage.model_validate(result)

    def iter(self) -> Iterator[SurveySummary]:
        next_path: str | None = "/surveys"
        while next_path:
            result = self._client.request("GET", next_path)
            page = SurveyPage.model_validate(result)
            yield from page.elements
            next_path = page.next_page

    def get(self, survey_id: str) -> dict[str, Any]:
        return self._client.request("GET", f"/surveys/{survey_id}")

    def update(self, survey_id: str, changes: SurveyUpdateRequest | dict[str, Any]) -> dict[str, Any] | None:
        payload = (
            changes.model_dump(by_alias=True, exclude_none=True, mode="json")
            if isinstance(changes, SurveyUpdateRequest)
            else changes
        )
        return self._client.request("PUT", f"/surveys/{survey_id}", json=payload)
