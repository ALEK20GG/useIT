"""
FastAPI application exposing a light wrapper over Qdrant.
"""

import hashlib
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .dependencies import get_qdrant_client
from .embeddings import embed_text_batch
from .pdf_utils import chunk_text, extract_text_from_pdf, extract_text_from_pdf_file, save_pdf
from .schemas import (
    CreateCollectionRequest,
    IngestNotesRequest,
    PDFSearchRequest,
    PDFSearchResult,
    SearchRequest,
    SearchResult,
    SemanticSearchHit,
    SemanticSearchRequest,
    UpsertPointRequest,
)

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


#
# PDF management and search endpoints
#

# Path relativo alla root del progetto
# Get the project root (backend/app/main.py -> backend -> project root)
_BACKEND_DIR = Path(__file__).parent.parent  # backend/
_PROJECT_ROOT = _BACKEND_DIR.parent  # project root
PDFS_DIR = _PROJECT_ROOT / "frontend" / "static" / "pdf-source"
PDF_COLLECTION = "pdfs"

# UUID namespace for deterministic UUID generation (required for embedded Qdrant)
PDF_NAMESPACE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # Standard DNS namespace

# Log the path on module load for debugging
print(f"PDFS_DIR configured as: {PDFS_DIR.absolute()}")
print(f"PDFS_DIR exists: {PDFS_DIR.exists()}")


@app.post("/pdf/upload", status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict[str, str]:
    """
    Upload a PDF file, save it to disk, extract text, and index it in Qdrant.

    The PDF is:
    1. Saved to the 'pdfs' directory
    2. Text is extracted from all pages
    3. Text is split into chunks for better semantic search
    4. Embeddings are generated for each chunk
    5. Chunks are indexed in Qdrant with metadata (filename, file_path, chunk_index)
    """

    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a PDF (.pdf extension required)",
        )

    try:
        # 1) Read file content
        file_content = await file.read()
        
        # 2) Save PDF to disk
        file_path = save_pdf(file_content, file.filename, str(PDFS_DIR))
        filename = Path(file_path).name
        
        # 3) Extract text from PDF
        try:
            full_text = extract_text_from_pdf(file_content)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to extract text from PDF: {e}",
            ) from e
        
        # 4) Split text into chunks
        text_chunks = chunk_text(full_text, chunk_size=1000, overlap=200)
        
        if not text_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF contains no extractable text",
            )
        
        # 5) Generate embeddings for chunks
        vectors = embed_text_batch(text_chunks)
        if not vectors:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate embeddings",
            )
        
        # Ensure text_chunks and vectors have the same length
        if len(text_chunks) != len(vectors):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Mismatch between chunks ({len(text_chunks)}) and vectors ({len(vectors)})",
            )
        
        vector_size = len(vectors[0])
        
        # 6) Ensure collection exists with the embedding model's vector size
        try:
            collection_info = client.get_collection(PDF_COLLECTION)
            if collection_info.config.params.vectors.size != vector_size:
                # Recreate if size doesn't match
                client.recreate_collection(
                    collection_name=PDF_COLLECTION,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
        except Exception:
            # Collection doesn't exist, create it
            client.create_collection(
                collection_name=PDF_COLLECTION,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        
        # 7) Prepare points with metadata
        # URL relativo per il frontend
        relative_url = f"/pdf-source/{filename}"
        points: list[PointStruct] = []
        
        for chunk_idx in range(len(text_chunks)):
            chunk_text = text_chunks[chunk_idx]
            vector = vectors[chunk_idx]
            # Create deterministic UUID based on filename and chunk index
            # This ensures the same PDF always gets the same IDs
            # Convert to string for Qdrant compatibility
            unique_name = f"{filename}:{chunk_idx}"
            point_id = str(uuid.uuid5(PDF_NAMESPACE, unique_name))
            
            payload = {
                "filename": filename,
                "file_path": file_path,
                "relative_url": relative_url,  # URL relativo per il frontend
                "chunk_index": chunk_idx,
                "chunk_text": chunk_text[:500],  # Store preview of chunk
                "total_chunks": len(text_chunks),
            }
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )
        
        # 8) Upsert into Qdrant
        client.upsert(collection_name=PDF_COLLECTION, points=points)
        
        return {
            "message": f"PDF '{filename}' uploaded and indexed successfully",
            "filename": filename,
            "relative_url": relative_url,
            "chunks_indexed": len(points),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing PDF: {str(e)}",
        ) from e


@app.post("/pdf/index-all", status_code=status.HTTP_200_OK)
async def index_all_pdfs(
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict[str, Any]:
    """
    Index all PDF files in the pdf-source directory.
    
    This scans the pdf-source directory and indexes any PDFs that aren't already indexed.
    """
    try:
        # Ensure directory exists
        PDFS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Debug: log the directory path
        print(f"Searching for PDFs in: {PDFS_DIR.absolute()}")
        
        # Find all PDF files
        pdf_files = list(PDFS_DIR.glob("*.pdf"))
        
        print(f"Found {len(pdf_files)} PDF files")
        
        if not pdf_files:
            return {
                "message": f"No PDF files found in pdf-source directory ({PDFS_DIR.absolute()})",
                "indexed": 0,
                "total": 0,
                "directory": str(PDFS_DIR.absolute()),
            }
        
        indexed_count = 0
        errors: list[str] = []
        
        # Get vector size from existing collection or generate a sample embedding
        try:
            sample_vector = embed_text_batch(["sample"])[0]
            vector_size = len(sample_vector)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate sample embedding: {str(e)}",
            ) from e
        
        # Ensure collection exists
        try:
            collection_info = client.get_collection(PDF_COLLECTION)
            if collection_info.config.params.vectors.size != vector_size:
                client.recreate_collection(
                    collection_name=PDF_COLLECTION,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
        except Exception as e:
            # Collection doesn't exist, create it
            try:
                client.create_collection(
                    collection_name=PDF_COLLECTION,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
            except Exception as create_error:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create collection: {str(create_error)}",
                ) from create_error
        
        # Index each PDF
        for pdf_file in pdf_files:
            filename = pdf_file.name
            relative_url = f"/pdf-source/{filename}"
            
            try:
                print(f"Processing PDF: {filename}")
                
                # Extract text
                full_text = extract_text_from_pdf_file(pdf_file)
                
                # Split into chunks
                text_chunks = chunk_text(full_text, chunk_size=1000, overlap=200)
                
                if not text_chunks:
                    errors.append(f"{filename}: No extractable text")
                    continue
                
                print(f"  Extracted {len(text_chunks)} chunks")
                
                # Generate embeddings
                vectors = embed_text_batch(text_chunks)
                
                if not vectors:
                    errors.append(f"{filename}: Failed to generate embeddings")
                    continue
                
                # Ensure text_chunks and vectors have the same length
                if len(text_chunks) != len(vectors):
                    errors.append(f"{filename}: Mismatch between chunks ({len(text_chunks)}) and vectors ({len(vectors)})")
                    continue
                
                print(f"  Generated {len(vectors)} embeddings")
                
                # Prepare points
                points: list[PointStruct] = []
                
                for chunk_idx in range(len(text_chunks)):
                    chunk_text_content = text_chunks[chunk_idx]
                    vector = vectors[chunk_idx]
                    
                    # Create deterministic UUID based on filename and chunk index
                    # Convert to string for Qdrant compatibility
                    unique_name = f"{filename}:{chunk_idx}"
                    point_id = str(uuid.uuid5(PDF_NAMESPACE, unique_name))
                    
                    payload = {
                        "filename": filename,
                        "file_path": str(pdf_file.absolute()),
                        "relative_url": relative_url,
                        "chunk_index": chunk_idx,
                        "chunk_text": chunk_text_content[:500],
                        "total_chunks": len(text_chunks),
                    }
                    
                    points.append(
                        PointStruct(
                            id=point_id,
                            vector=vector,
                            payload=payload,
                        )
                    )
                
                # Upsert into Qdrant
                client.upsert(collection_name=PDF_COLLECTION, points=points)
                indexed_count += 1
                print(f"  ✓ Indexed {filename}")
                
            except Exception as e:
                error_msg = f"{filename}: {str(e)}"
                errors.append(error_msg)
                print(f"  ✗ Error with {filename}: {str(e)}")
                continue
        
        return {
            "message": f"Indexed {indexed_count} PDF files",
            "indexed": indexed_count,
            "total": len(pdf_files),
            "errors": errors if errors else None,
            "directory": str(PDFS_DIR.absolute()),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in index_all_pdfs: {error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error indexing PDFs: {str(e)}",
        ) from e


def normalize_cosine_score(score: float) -> float:
    """
    Normalize cosine similarity score from [-1, 1] to [0, 1].
    
    Cosine similarity can range from -1 (opposite) to 1 (identical).
    We normalize to [0, 1] where 0 = no similarity, 1 = maximum similarity.
    """
    # Normalize: (score + 1) / 2
    # This maps -1 -> 0, 0 -> 0.5, 1 -> 1.0
    return (score + 1.0) / 2.0


def calculate_keyword_boost(query: str, text: str) -> float:
    """
    Calculate a boost score based on exact keyword matches.
    
    Returns a boost value between 0.0 and 0.3 (30% boost max).
    """
    if not query or not text:
        return 0.0
    
    query_lower = query.lower()
    text_lower = text.lower()
    
    # Split query into words
    query_words = [w.strip() for w in query_lower.split() if len(w.strip()) > 2]  # Ignore short words
    
    if not query_words:
        return 0.0
    
    # Count how many query words appear in the text
    matches = sum(1 for word in query_words if word in text_lower)
    match_ratio = matches / len(query_words)
    
    # Boost is proportional to match ratio, capped at 0.3 (30%)
    return min(match_ratio * 0.3, 0.3)


@app.post("/pdf/search", response_model=list[PDFSearchResult])
async def search_pdfs(
    body: PDFSearchRequest,
    client: QdrantClient = Depends(get_qdrant_client),
) -> list[PDFSearchResult]:
    """
    Perform hybrid search (semantic + keyword) across indexed PDF documents.

    Given a search query (keywords or natural language), returns a list of unique PDF files
    that contain relevant content, ordered by relevance score.
    
    The search combines:
    - Semantic similarity (using embeddings) - good for concepts and meaning
    - Keyword matching (exact word matches) - good for names and specific terms
    """

    try:
        # 1) Generate embedding for the search query
        query_vector = embed_text_batch([body.query])[0]
        
        # 2) Search in Qdrant (semantic search)
        # Search for more results than needed to ensure we get diverse PDFs
        hits = client.search(
            collection_name=body.collection_name,
            query_vector=query_vector,
            limit=body.limit * 10,  # Get more hits to apply keyword boost
            with_payload=True,
        )
        
        if not hits:
            return []
        
        # 3) Group hits by filename, apply keyword boost, and keep best match
        pdf_map: dict[str, dict] = {}
        
        for hit in hits:
            payload = hit.payload or {}
            filename = payload.get("filename", "")
            relative_url = payload.get("relative_url", f"/pdf-source/{filename}")
            chunk_text = payload.get("chunk_text", "")
            
            if not filename:
                continue
            
            # Normalize cosine similarity from [-1, 1] to [0, 1]
            semantic_score = normalize_cosine_score(hit.score)
            
            # Apply keyword boost if enabled
            final_score = semantic_score
            if body.use_keyword_boost:
                keyword_boost = calculate_keyword_boost(body.query, chunk_text)
                # Combine semantic score with keyword boost (additive, capped at 1.0)
                final_score = min(semantic_score + keyword_boost, 1.0)
            
            # Keep the highest scoring chunk for each PDF
            if filename not in pdf_map or final_score > pdf_map[filename]["score"]:
                pdf_map[filename] = {
                    "filename": filename,
                    "relative_url": relative_url,
                    "score": final_score,
                    "preview_text": chunk_text[:200],
                    "semantic_score": semantic_score,
                    "keyword_boost": keyword_boost if body.use_keyword_boost else 0.0,
                }
        
        # 4) Convert to response model, sorted by score (highest first)
        results = sorted(
            pdf_map.values(),
            key=lambda x: x["score"],
            reverse=True,
        )[:body.limit]
        
        return [
            PDFSearchResult(
                filename=result["filename"],
                relative_url=result["relative_url"],
                score=result["score"],
                preview_text=result["preview_text"],
            )
            for result in results
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during PDF search: {str(e)}",
        ) from e


#
# Image analysis (placeholder) – receives an image file from the frontend.
#


@app.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...)) -> dict[str, str]:
    """
    Accept an image upload and return a placeholder analysis.

    Later, this can be wired to a vision model or external service.
    """

    # We read the bytes now so that in future we can pass them to a model.
    _ = await file.read()

    return {
        "filename": file.filename or "uploaded-image",
        "content_type": file.content_type or "image/*",
        "summary": "Image received correctly. Analysis model is not implemented yet.",
    }

