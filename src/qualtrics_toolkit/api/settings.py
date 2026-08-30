from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class QualtricsSettings(BaseSettings):
    """Qualtrics connection values loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="QUALTRICS_", extra="ignore")

    api_token: str = ""
    data_center: str | None = None
    base_url: str | None = None
