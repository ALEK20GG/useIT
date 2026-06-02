"""
Application configuration and settings helpers.
"""

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed configuration sourced from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="QDRANT_",
        case_sensitive=False,
        # backend/.env includes SSO, session, and frontend vars used by SvelteKit only
        extra="ignore",
    )

    url: str = "http://localhost:6333"
    api_key: str | None = None
    # Set to true in local dev to fall back to embedded Qdrant when server is unreachable.
    # Always false in production (Docker) — fail fast instead of silently using local DB.
    allow_embedded: bool = True

    # CORS — comma-separated string from CORS_ORIGINS (not under QDRANT_ prefix)
    cors_origins_env: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_env.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
