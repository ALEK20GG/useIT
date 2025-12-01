"""
Application configuration and settings helpers.
"""

from functools import lru_cache
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


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()

