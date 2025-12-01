"""
Shared FastAPI dependencies.
"""

from functools import lru_cache

from qdrant_client import QdrantClient

from .config import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """
    Lazily instantiate and cache a QdrantClient.

    The client is reused across requests to keep connections warm.
    """

    settings = get_settings()
    return QdrantClient(url=settings.url, api_key=settings.api_key)

