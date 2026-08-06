"""Centralized configuration for the CivicLens application."""

from functools import lru_cache
from typing import Literal

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings loaded from environment variables."""

    app_name: str = "CivicLens"
    environment: Literal["development", "preview", "production"] = "development"
    debug: bool = False
    public_base_url: HttpUrl

    supabase_url: HttpUrl
    supabase_publishable_key: SecretStr
    auth_confirmation_redirect: HttpUrl

    access_cookie_name: str = "civiclens_access"
    refresh_cookie_name: str = "civiclens_refresh"
    csrf_cookie_name: str = "civiclens_csrf"

    model_config = SettingsConfigDict(
        env_prefix="CIVICLENS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def secure_cookies(self) -> bool:
        """Require secure cookies outside local development."""
        return self.environment != "development"

    @property
    def supabase_auth_url(self) -> str:
        """Return the base URL for Supabase Auth API requests."""
        return f"{str(self.supabase_url).rstrip('/')}/auth/v1"

    @property
    def supabase_jwks_url(self) -> str:
        """Return the public signing-key endpoint used to verify JWTs."""
        return f"{self.supabase_auth_url}/.well-known/jwks.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Parse and cache environment variables once per process."""
    return Settings()