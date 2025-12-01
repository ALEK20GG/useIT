"""
FastAPI application exposing a light wrapper over Qdrant.
"""

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .dependencies import get_qdrant_client
from .schemas import (
    CreateCollectionRequest,
    IngestNotesRequest,
    SearchRequest,
    SearchResult,
    SemanticSearchHit,
    SemanticSearchRequest,
    UpsertPointRequest,
)
from .embeddings import embed_text_batch

app = FastAPI(
    title="UseIt Qdrant Backend",
    version="0.1.0",
    description="Simple FastAPI backend that proxies read/write operations to Qdrant.",
)

# Allow the SvelteKit dev server to talk to this API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _distance_from_label(label: str) -> Distance:
    """Map human readable labels to Qdrant Distance enums."""

    mapping = {
        "cosine": Distance.COSINE,
        "dot": Distance.DOT,
        "euclid": Distance.EUCLID,
    }
    if label not in mapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported distance '{label}'. Expected one of {list(mapping.keys())}.",
        )
    return mapping[label]


@app.get("/health")
def health(client: QdrantClient = Depends(get_qdrant_client)) -> dict[str, str]:
    """Basic readiness probe to ensure we can talk to Qdrant."""

    try:
        _ = client.get_collections()
    except Exception as exc:  # pragma: no cover - connectivity guard
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to reach Qdrant: {exc}",
        ) from exc

    return {"status": "ok"}


@app.post("/collections", status_code=status.HTTP_201_CREATED)
def create_collection(
    payload: CreateCollectionRequest,
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict[str, str]:
    """Create (or recreate) a Qdrant collection with the provided vector config."""

    client.recreate_collection(
        collection_name=payload.name,
        vectors_config=VectorParams(
            size=payload.vector_size, distance=_distance_from_label(payload.distance)
        ),
    )
    return {"message": f"Collection '{payload.name}' ready."}


@app.post("/points", status_code=status.HTTP_202_ACCEPTED)
def upsert_point(
    body: UpsertPointRequest, client: QdrantClient = Depends(get_qdrant_client)
) -> dict[str, str]:
    """Insert or update a single vector in Qdrant."""

    point = PointStruct(
        id=body.point_id,
        vector=body.vector,
        payload=body.payload or {},
    )
    client.upsert(collection_name=body.collection_name, points=[point])
    return {"message": f"Point '{body.point_id}' queued for upsert."}


@app.post("/search", response_model=list[SearchResult])
def search(
    query: SearchRequest,
    client: QdrantClient = Depends(get_qdrant_client),
) -> list[SearchResult]:
    """Run a vector similarity search against Qdrant."""

    hits = client.search(
        collection_name=query.collection_name,
        query_vector=query.vector,
        limit=query.limit,
        with_payload=query.with_payload,
    )
    return [
        SearchResult(id=hit.id, score=hit.score, payload=hit.payload) for hit in hits
    ]


#
# Semantic search endpoints (embeddings + Qdrant)
#


@app.post("/semantic/ingest", status_code=status.HTTP_202_ACCEPTED)
def ingest_notes(
    body: IngestNotesRequest,
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict[str, str]:
    """
    Ingest one or more notes/documents into Qdrant for later semantic search.

    We:
    - ensure the target collection exists with the right vector size
    - create embeddings for each note's content
    - upsert them into Qdrant with rich payload metadata
    """

    # 1) Generate embeddings
    texts = [note.content for note in body.notes]
    vectors = embed_text_batch(texts)
    if not vectors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No notes to ingest.",
        )

    vector_size = len(vectors[0])

    # 2) Ensure collection exists with the embedding model's vector size
    client.recreate_collection(
        collection_name=body.collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    # 3) Prepare points
    points: list[PointStruct] = []
    for idx, (note, vector) in enumerate(zip(body.notes, vectors)):
        point_id = note.id if note.id is not None else idx
        payload = {
            "title": note.title,
            "content": note.content,
            "type": note.type,
            "tags": note.tags,
        }
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        )

    client.upsert(collection_name=body.collection_name, points=points)
    return {
        "message": f"Ingested {len(points)} notes into collection '{body.collection_name}'."
    }


@app.post("/semantic/search", response_model=list[SemanticSearchHit])
def semantic_search(
    body: SemanticSearchRequest,
    client: QdrantClient = Depends(get_qdrant_client),
) -> list[SemanticSearchHit]:
    """
    Run a semantic search over the notes collection using embeddings.
    """

    query_vector = embed_text_batch([body.query])[0]
    hits = client.search(
        collection_name=body.collection_name,
        query_vector=query_vector,
        limit=body.limit,
        with_payload=True,
    )

    results: list[SemanticSearchHit] = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            SemanticSearchHit(
                id=hit.id,
                score=hit.score,
                title=payload.get("title", ""),
                content=payload.get("content", ""),
                type=payload.get("type"),
                tags=payload.get("tags") or [],
            )
        )

    return results

