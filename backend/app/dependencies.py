"""
Shared FastAPI dependencies.
"""

from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from .config import get_settings


@lru_cache
def get_qdrant_client() -> QdrantClient:
    """
    Lazily instantiate and cache a QdrantClient.

    The client is reused across requests to keep connections warm.
    
    Uses embedded Qdrant (local mode) if connection to server fails.
    This allows the app to work without Docker.
    """

    settings = get_settings()
    
    try:
        # Try to connect to Qdrant server first
        client = QdrantClient(url=settings.url, api_key=settings.api_key)
        # Test connection
        client.get_collections()
        print(f"✓ Connected to Qdrant server at {settings.url}")
        return client
    except Exception as e:
        print(f"⚠ Could not connect to Qdrant server at {settings.url}: {e}")
        print("⚠ Falling back to embedded Qdrant (local mode)...")
        
        # Fallback to embedded/local Qdrant
        qdrant_path = Path(__file__).parent.parent.parent / "qdrant_local"
        qdrant_path.mkdir(parents=True, exist_ok=True)
        
        # Use local/embedded Qdrant - no server needed!
        client = QdrantClient(path=str(qdrant_path))
        print(f"✓ Using embedded Qdrant at {qdrant_path.absolute()}")
        return client

