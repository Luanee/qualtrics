from __future__ import annotations

from typing import Any

from ..models import SurveyDefinition
from .base import APIDomain


class SurveyDefinitionsAPI(APIDomain):
    """Survey structure endpoints, separate from Surveys CRUD."""

    def get(self, survey_id: str) -> SurveyDefinition:
        result = self._client.request("GET", f"/survey-definitions/{survey_id}")
        raw_entry = result.get("SurveyEntry") if isinstance(result, dict) else None
        entry = raw_entry if isinstance(raw_entry, dict) else result
        return SurveyDefinition(
            SurveyID=entry.get("SurveyID", survey_id) if isinstance(entry, dict) else survey_id,
            SurveyName=entry.get("SurveyName") if isinstance(entry, dict) else None,
            payload=result if isinstance(result, dict) else {},
        )

    def create(self, definition: dict[str, Any]) -> dict[str, Any]:
        return self._client.request("POST", "/survey-definitions", json=definition)

    def delete(self, survey_id: str) -> dict[str, Any] | None:
        return self._client.request("DELETE", f"/survey-definitions/{survey_id}")

    def get_metadata(self, survey_id: str) -> dict[str, Any]:
        return self._client.request("GET", f"/survey-definitions/{survey_id}/metadata")

    def update_metadata(self, survey_id: str, metadata: dict[str, Any]) -> None:
        self._client.request("PUT", f"/survey-definitions/{survey_id}/metadata", json=metadata)
