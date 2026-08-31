from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class QualtricsSettings(BaseSettings):
    """Qualtrics connection values loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="QUALTRICS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_token: str = ""
    data_center: str | None = None
    base_url: str | None = None
