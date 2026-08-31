from __future__ import annotations

from collections.abc import Iterator

from ..models import SurveyQuota, SurveyQuotaPage
from .base import APIDomain


class SurveyQuotasAPI(APIDomain):
    """Read quota progress and definitions for a survey."""

    def list(self, survey_id: str, *, offset: int | None = None) -> SurveyQuotaPage:
        """Return one page of quotas for ``survey_id``."""
        if offset is not None and offset < 0:
            raise ValueError("offset must be greater than or equal to zero")
        params = {"offset": offset} if offset is not None else None
        result = self._client.request("GET", f"/surveys/{survey_id}/quotas", params=params)
        return SurveyQuotaPage.model_validate(result)

    def iter(self, survey_id: str) -> Iterator[SurveyQuota]:
        """Yield all quotas across every page returned by Qualtrics."""
        next_path: str | None = f"/surveys/{survey_id}/quotas"
        while next_path:
            page = SurveyQuotaPage.model_validate(self._client.request("GET", next_path))
            yield from page.elements
            next_path = page.next_page
