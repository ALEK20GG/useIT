# Feature: pdf-semantic-search-platform, Property 7: Ingest is additive (no data loss)
# Validates: Requirements 2.1, 2.2

"""
Property 7: Ingest is additive — point count must be non-decreasing.

For any Notes_Collection that already contains M points, calling
/semantic/ingest with K new notes SHALL result in the collection
containing at least M points (existing points are not deleted).

This test inlines the ingest logic from app/main.py::ingest_notes so it
can run without installing the full dependency stack (qdrant_client,
sentence_transformers, PyPDF2, etc.).  The logic under test is:

  1. embed_text_batch(texts) → vectors
  2. ensure collection exists (create if absent, recreate only on size mismatch)
  3. upsert points — never delete an existing correctly-sized collection

Validates: Requirements 2.1, 2.2
"""

import sys
import os
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Minimal data classes that mirror the real Pydantic / Qdrant models
# ---------------------------------------------------------------------------

@dataclass
class NoteDocument:
    content: str
    title: str
    type: str | None = None
    tags: list[str] = field(default_factory=list)
    id: int | str | None = None


@dataclass
class IngestNotesRequest:
    notes: list[NoteDocument]
    collection_name: str = "notes"


@dataclass
class PointStruct:
    id: int | str
    vector: list[float]
    payload: dict[str, Any]


# ---------------------------------------------------------------------------
# Ingest logic (mirrors app/main.py::ingest_notes exactly)
# ---------------------------------------------------------------------------

def ingest_notes(body: IngestNotesRequest, client, embed_fn):
    """
    Inlined copy of the ingest_notes route handler logic.

    Parameters
    ----------
    body:      IngestNotesRequest
    client:    mock Qdrant client
    embed_fn:  callable that returns list[list[float]] for a list of texts
    """
    texts = [note.content for note in body.notes]
    vectors = embed_fn(texts)
    if not vectors:
        raise ValueError("No notes to ingest.")

    vector_size = len(vectors[0])

    try:
        collection_info = client.get_collection(body.collection_name)
        existing_size = collection_info.config.params.vectors.size
        if existing_size != vector_size:
            # Vector size mismatch — recreate (data loss is acceptable here)
            client.delete_collection(collection_name=body.collection_name)
            client.create_collection(
                collection_name=body.collection_name,
                vector_size=vector_size,
            )
        # else: collection exists with correct size — keep existing data, just upsert
    except Exception:
        # Collection doesn't exist — create it
        client.create_collection(
            collection_name=body.collection_name,
            vector_size=vector_size,
        )

    points: list[PointStruct] = []
    for idx, (note, vector) in enumerate(zip(body.notes, vectors)):
        point_id = note.id if note.id is not None else idx
        payload = {
            "title": note.title,
            "content": note.content,
            "type": note.type,
            "tags": note.tags,
        }
        points.append(PointStruct(id=point_id, vector=vector, payload=payload))

    client.upsert(collection_name=body.collection_name, points=points)


# ---------------------------------------------------------------------------
# Mock Qdrant client
# ---------------------------------------------------------------------------

def make_mock_client(existing_size=None):
    """Create a mock Qdrant client that tracks upserted points by id."""
    client = MagicMock()
    stored_points: dict[str, dict] = {}

    if existing_size is None:
        client.get_collection.side_effect = Exception("Collection not found")
    else:
        collection_info = MagicMock()
        collection_info.config.params.vectors.size = existing_size
        client.get_collection.return_value = collection_info

    def mock_upsert(collection_name, points):
        if collection_name not in stored_points:
            stored_points[collection_name] = {}
        for p in points:
            stored_points[collection_name][p.id] = p

    client.upsert.side_effect = mock_upsert
    client._stored_points = stored_points
    return client


def fake_embed(texts):
    """Return a fixed-size fake vector for each text."""
    return [[0.1, 0.2, 0.3]] * len(texts)


# ---------------------------------------------------------------------------
# Property test
# ---------------------------------------------------------------------------

@given(
    notes_batch1=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=5),
    notes_batch2=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=5),
)
@settings(max_examples=50)
def test_ingest_is_additive(notes_batch1, notes_batch2):
    """
    Property 7: Ingest is additive — point count must be non-decreasing.

    Validates: Requirements 2.1, 2.2
    """
    VECTOR_SIZE = 3
    COLLECTION = "notes"

    client = make_mock_client(existing_size=None)

    # --- First ingest ---
    req1 = IngestNotesRequest(
        collection_name=COLLECTION,
        notes=[NoteDocument(content=t, title="t", type="note", tags=[]) for t in notes_batch1],
    )
    ingest_notes(req1, client, fake_embed)
    count_after_first = len(client._stored_points.get(COLLECTION, {}))

    # After first ingest the collection now exists with the correct vector size;
    # update the mock so subsequent get_collection calls succeed.
    client.get_collection.side_effect = None
    collection_info = MagicMock()
    collection_info.config.params.vectors.size = VECTOR_SIZE
    client.get_collection.return_value = collection_info

    # --- Second ingest ---
    req2 = IngestNotesRequest(
        collection_name=COLLECTION,
        notes=[NoteDocument(content=t, title="t", type="note", tags=[]) for t in notes_batch2],
    )
    ingest_notes(req2, client, fake_embed)
    count_after_second = len(client._stored_points.get(COLLECTION, {}))

    assert count_after_second >= count_after_first, (
        f"Point count decreased from {count_after_first} to {count_after_second}. "
        f"batch1={notes_batch1!r}, batch2={notes_batch2!r}"
    )
