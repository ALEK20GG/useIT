"""
Embedding utilities for semantic search.
"""

from functools import lru_cache
from typing import Iterable, List

from openai import OpenAI


EMBEDDING_MODEL = "text-embedding-3-small"


@lru_cache
def get_openai_client() -> OpenAI:
    """Return a cached OpenAI client, configured via OPENAI_API_KEY env var."""

    return OpenAI()


def embed_text_batch(texts: Iterable[str]) -> List[List[float]]:
    """
    Generate embeddings for a batch of texts.

    This keeps the interface simple for the rest of the app.
    """

    client = get_openai_client()
    # OpenAI client expects a list; we also force materialization to safely reuse
    inputs = list(texts)
    if not inputs:
        return []

    response = client.embeddings.create(model=EMBEDDING_MODEL, input=inputs)
    # The API returns embeddings in the same order as inputs
    return [item.embedding for item in response.data]


