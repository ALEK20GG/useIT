"""
Embedding utilities for semantic search using sentence-transformers.
"""

from functools import lru_cache
from typing import Iterable, List

from sentence_transformers import SentenceTransformer


# Using a multilingual model that works well for Italian and English
# This model will be downloaded automatically on first use
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@lru_cache
def get_embedding_model() -> SentenceTransformer:
    """
    Return a cached SentenceTransformer model.
    
    The model will be downloaded automatically on first use.
    This model supports multiple languages including Italian and English.
    """
    print(f"Loading embedding model: {EMBEDDING_MODEL}")
    print("Note: This will download the model (~500MB) on first use. Please wait...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print("Model loaded successfully!")
    return model


def embed_text_batch(texts: Iterable[str]) -> List[List[float]]:
    """
    Generate embeddings for a batch of texts using sentence-transformers.

    This keeps the interface simple for the rest of the app.
    No API key required - runs locally and is completely free!
    """

    model = get_embedding_model()
    # Convert to list and filter empty strings
    inputs = [text for text in texts if text and text.strip()]
    
    if not inputs:
        return []

    # Generate embeddings - this returns a numpy array
    embeddings = model.encode(
        inputs,
        convert_to_numpy=True,
        show_progress_bar=False,
        normalize_embeddings=True  # Normalize for better cosine similarity
    )
    
    # Convert numpy array to list of lists
    return embeddings.tolist()


