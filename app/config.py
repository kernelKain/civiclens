"""Centralized configuration for the CivicLens application."""

from functools import lru_cache
from typing import Literal

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings loaded from environment variables."""

    app_name: str = "CivicLens"
    environment: Literal["development", "preview", "production"] = "development"
    debug: bool = False
    public_base_url: HttpUrl

    model_config = SettingsConfigDict(
        env_prefix="CIVICLENS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Settings are cached so environment variables are parsed once per process.
    return Settings()