"""
Pydantic models shared across the API surface.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, PositiveInt


class CreateCollectionRequest(BaseModel):
    """Payload used to create or recreate a Qdrant collection."""

    name: str = Field(min_length=1, description="Collection identifier")
    vector_size: PositiveInt = Field(description="Dimensionality of vectors")
    distance: Literal["cosine", "dot", "euclid"] = Field(
        default="cosine",
        description="Distance function Qdrant should use",
    )


class UpsertPointRequest(BaseModel):
    """Payload describing a single point to insert or update."""

    collection_name: str
    point_id: int | str = Field(
        description="Unique identifier for the vector (int or string supported)"
    )
    vector: list[float] = Field(min_length=1, description="Embedding values")
    payload: dict[str, Any] | None = Field(
        default=None, description="Optional metadata stored alongside the vector"
    )


class SearchRequest(BaseModel):
    """Query body for semantic search."""

    collection_name: str
    vector: list[float] = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=100)
    with_payload: bool = True


class SearchResult(BaseModel):
    """Subset of fields returned from Qdrant search."""

    id: int | str
    score: float
    payload: dict[str, Any] | None = None


# ---- Semantic search specific models ----


class NoteDocument(BaseModel):
    """
    A single logical document / note we index in Qdrant.

    For now we keep it simple: just a title, body, and optional tags/type.
    """

    id: int | str | None = Field(
        default=None,
        description="Optional custom identifier; if omitted Qdrant will auto-assign.",
    )
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    type: str | None = Field(
        default=None,
        description="High-level category, e.g. 'component', 'school-note', 'doc'.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags, e.g. ['math', 'algebra'] or ['ui', 'button'].",
    )


class IngestNotesRequest(BaseModel):
    """
    Request body for ingesting one or more notes for semantic search.
    """

    collection_name: str = Field(
        default="notes",
        description="Qdrant collection where notes are stored.",
    )
    # all vectors in a collection must have the same size; we derive it from the model
    notes: list[NoteDocument] = Field(min_length=1)


class SemanticSearchRequest(BaseModel):
    """
    Run a semantic search over the notes collection.
    """

    collection_name: str = Field(default="notes")
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
    # in future we could add tag / type filters here


class SemanticSearchHit(BaseModel):
    """
    Response item returned to the frontend for semantic search.
    """

    id: int | str
    score: float
    title: str
    content: str
    type: str | None = None
    tags: list[str] = Field(default_factory=list)


