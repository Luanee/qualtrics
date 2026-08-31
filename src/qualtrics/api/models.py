from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ResponseMeta(APIModel):
    request_id: str | None = Field(default=None, alias="requestId")
    http_status: str | None = Field(default=None, alias="httpStatus")


class SurveySummary(APIModel):
    id: str
    name: str
    owner_id: str | None = Field(default=None, alias="ownerId")
    is_active: bool | None = Field(default=None, alias="isActive")
    creation_date: str | None = Field(default=None, alias="creationDate")
    last_modified: str | None = Field(default=None, alias="lastModified")


class SurveyPage(APIModel):
    elements: list[SurveySummary] = Field(default_factory=list)
    next_page: str | None = Field(default=None, alias="nextPage")


class SurveyExpiration(APIModel):
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")


class SurveyUpdateRequest(APIModel):
    name: str | None = None
    is_active: bool | None = Field(default=None, alias="isActive")
    expiration: SurveyExpiration | None = None
    owner_id: str | None = Field(default=None, alias="ownerId")


class SurveyQuotaCombination(APIModel):
    count: int
    quota: int
    description: str


class SurveyQuota(APIModel):
    id: str
    name: str
    count: int
    quota: int
    logic_type: str = Field(alias="logicType")
    combinations: list[SurveyQuotaCombination] = Field(default_factory=list)


class SurveyQuotaPage(APIModel):
    elements: list[SurveyQuota] = Field(default_factory=list)
    next_page: str | None = Field(default=None, alias="nextPage")


class SurveyDefinition(APIModel):
    survey_id: str | None = Field(default=None, alias="SurveyID")
    survey_name: str | None = Field(default=None, alias="SurveyName")
    payload: dict[str, Any] = Field(default_factory=dict)


ExportFormat = Literal["csv", "tsv", "json", "ndjson", "xml", "spss"]


class ExportStatus(StrEnum):
    IN_PROGRESS = "inProgress"
    COMPLETE = "complete"
    FAILED = "failed"


class ImportFormat(StrEnum):
    CSV = "csv"
    JSON = "json"


class ResponseImportRequest(APIModel):
    file_url: str = Field(alias="fileUrl")
    format: ImportFormat = ImportFormat.CSV


class ImportProgress(APIModel):
    progress_id: str | None = Field(default=None, alias="progressId")
    percent_complete: float = Field(default=0, alias="percentComplete")
    status: ExportStatus


class SurveyFilter(APIModel):
    filter_id: str = Field(alias="filterId")
    name: str | None = None


class SurveyFilterPage(APIModel):
    elements: list[SurveyFilter] = Field(default_factory=list)
    next_page: str | None = Field(default=None, alias="nextPage")


class FilenameStrategy(StrEnum):
    QUALTRICS = "qualtrics"
    SURVEY_ID = "survey_id"
    SURVEY_NAME = "survey_name"
    CUSTOM = "custom"


class ResponseExportRequest(APIModel):
    format: ExportFormat = "csv"
    compress: bool = True
    use_labels: bool = Field(default=True, alias="useLabels")
    new_line_replacement: str | None = Field(default=None, alias="newlineReplacement")
    include_display_order: bool = Field(default=False, alias="includeDisplayOrder")
    include_label_columns: bool = Field(default=False, alias="includeLabelColumns")
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    filter_id: str | None = Field(default=None, alias="filterId")
    question_ids: list[str] | None = Field(default=None, alias="questionIds")
    survey_metadata_ids: list[str] | None = Field(default=None, alias="surveyMetadataIds")
    embedded_data_ids: list[str] | None = Field(default=None, alias="embeddedDataIds")
    limit: int | None = None
    continuation_token: str | None = Field(default=None, alias="continuationToken")
    allow_continuation: bool = Field(default=False, alias="allowContinuation")
    sort_by_last_modified_date: bool = Field(default=False, alias="sortByLastModifiedDate")


class ExportProgress(APIModel):
    progress_id: str | None = Field(default=None, alias="progressId")
    file_id: str | None = Field(default=None, alias="fileId")
    percent_complete: float = Field(default=0, alias="percentComplete")
    status: ExportStatus
    continuation_token: str | None = Field(default=None, alias="continuationToken")


class ExportResult(APIModel):
    survey_id: str
    progress_id: str
    file_id: str
    path: str
    format: ExportFormat
    continuation_token: str | None = None


JSONValue = dict[str, Any] | list[Any] | str | int | float | bool | None
HTTPMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
