"""
Shared FastAPI dependencies.
"""

import logging
from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient

from .config import get_settings

logger = logging.getLogger(__name__)

_QDRANT_LOCAL_DIR = Path(__file__).resolve().parent.parent / "qdrant_local"


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """
    Instantiate and cache a QdrantClient pointed at the configured Qdrant server.

    Set QDRANT_ALLOW_EMBEDDED=true in backend/.env to fall back to a local embedded
    database when the remote server is unreachable (development only).
    """
    settings = get_settings()
    allow_embedded = settings.allow_embedded

    try:
        client = QdrantClient(url=settings.url, api_key=settings.api_key)
        client.get_collections()
        logger.info("Connected to Qdrant server at %s", settings.url)
        return client
    except Exception as e:
        if not allow_embedded:
            raise RuntimeError(
                f"Cannot connect to Qdrant at {settings.url}: {e}\n"
                "Set QDRANT_URL to the correct server address, or set "
                "QDRANT_ALLOW_EMBEDDED=true to use local embedded mode (dev only)."
            ) from e

        logger.warning(
            "Could not connect to Qdrant server at %s: %s",
            settings.url,
            e,
        )
        logger.warning(
            "QDRANT_ALLOW_EMBEDDED=true — using embedded Qdrant at %s",
            _QDRANT_LOCAL_DIR,
        )
        _QDRANT_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=str(_QDRANT_LOCAL_DIR))
        logger.info("Using embedded Qdrant at %s", _QDRANT_LOCAL_DIR.resolve())
        return client
