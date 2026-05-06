"""
Application configuration and settings helpers.
"""

import os
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QDRANT_",
        case_sensitive=False,
    )

    url: str = "http://localhost:6333"
    api_key: str | None = None

    # CORS (Requirement 7) — read from CORS_ORIGINS env var (no QDRANT_ prefix)
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> object:
        env_val = os.environ.get("CORS_ORIGINS")
        if env_val:
            return [origin.strip() for origin in env_val.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
