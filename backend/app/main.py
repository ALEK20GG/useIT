"""
FastAPI application exposing a light wrapper over Qdrant.
"""

import hashlib
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams

from .config import get_settings
from .dependencies import get_qdrant_client
from .embeddings import embed_text_batch
from .pdf_utils import chunk_text, extract_text_from_pdf, extract_text_from_pdf_file, save_pdf
from .error_handling import (
    ErrorCode,
    log_error_with_context,
    log_operation_timing,
    make_device_recognition_error,
    make_upload_error,
    make_service_degradation_response,
    check_qdrant_health,
)

logger = logging.getLogger(__name__)
from .schemas import (
    CreateCollectionRequest,
    IndexedPDF,
    IngestNotesRequest,
    PDFSearchRequest,
    PDFSearchResult,
    PDFSearchResponse,
    SearchRequest,
    SearchResult,
    SemanticSearchHit,
    SemanticSearchRequest,
    UpsertPointRequest,
    CreateFolderRequest,
    FolderResponse,
    FolderListResponse,
    UpdateFolderRequest,
    AssignContentRequest,
    MoveContentRequest,
    DeviceRecognitionResponse,
    QRCodeResponse,
    AIServiceInfoResponse,
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceListResponse,
    RecognizeAndLookupResponse,
    QRCodeWithDocumentationResponse,
)
from .folder_service import FolderService, ConfigStore
from .folder_models import FolderDefinition, ContentType
from .migration_service import MigrationService, SystemMigrationService
from .device_service import DeviceRecognitionService, get_device_recognition_service
from .device_database import DeviceDatabase, DeviceRecord, get_device_database
from .security import (
    AuditAction,
    RateLimiter,
    RateLimitConfig,
    FileValidationResult,
    get_rate_limiter,
    log_audit_event,
    get_audit_log,
    sanitize_search_query,
    sanitize_filename,
    sanitize_text_input,
    validate_and_scan_file,
    validate_pdf_filename,
    validate_file_id,
    validate_device_id,
    detect_sql_injection,
    detect_path_traversal,
    ALLOWED_DOCUMENT_TYPES,
    ALLOWED_IMAGE_TYPES,
)

_API_DESCRIPTION = """
# UseIt – Intelligent Device Documentation Platform API

**UseIt** is an intelligent device documentation platform that combines AI-powered device
recognition with semantic search over a vector database (Qdrant).

## Key capabilities

| Feature | Description |
|---------|-------------|
| 📷 Device recognition | Identify devices from photos using AI (mock or real model) |
| 🔲 QR code scanning | Decode QR codes to retrieve device documentation |
| 🔍 Semantic search | Natural-language search over indexed documents |
| 📁 Folder management | Hierarchical content organisation (Dispositivi, Appunti, Scuola…) |
| 📄 PDF management | Upload, index, and search PDF documents |
| 👤 User area | Save and export search results |

## Authentication

The API is currently open for local use. For production deployments, add JWT or API-key
authentication via a middleware layer.

## Rate limiting

Upload and recognition endpoints are rate-limited to prevent abuse.
Exceeding the limit returns **HTTP 429** with a `retry_after` hint.

## Error format

All errors follow a structured JSON body:

```json
{
  "error_code": "UPLOAD_FORMAT_UNSUPPORTED",
  "category": "upload",
  "user_message": "Human-readable message",
  "suggestions": [{"action": "...", "description": "...", "can_retry": true}],
  "can_retry": true
}
```

## Multilingual support

User-facing messages are returned in **Italian** by default.
The `Accept-Language` header is not yet implemented; use the frontend i18n layer for
English translations.

---

*Requirement 20.4 – API documentation for developers extending the platform.*
"""

app = FastAPI(
    title="UseIt – Intelligent Device Documentation Platform",
    version="1.0.0",
    description=_API_DESCRIPTION,
    contact={
        "name": "UseIt Development Team",
        "url": "https://github.com/your-org/useit",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {
            "name": "health",
            "description": "Service health and readiness probes.",
        },
        {
            "name": "device",
            "description": (
                "Device recognition via photo or QR code, and device database management. "
                "Implements Requirements 1.x and 2.x."
            ),
        },
        {
            "name": "pdf",
            "description": (
                "Upload, index, and search PDF documents. "
                "Implements Requirements 6.x and 7.x."
            ),
        },
        {
            "name": "semantic",
            "description": (
                "Semantic (embedding-based) search and note ingestion. "
                "Implements Requirements 4.x and 12.x."
            ),
        },
        {
            "name": "folders",
            "description": (
                "Hierarchical folder management for content organisation. "
                "Implements Requirements 5.x."
            ),
        },
        {
            "name": "content",
            "description": (
                "Multi-source content retrieval and management. "
                "Implements Requirements 3.x and 13.x."
            ),
        },
        {
            "name": "user",
            "description": (
                "User area: save, organise, and export search results. "
                "Implements Requirements 8.x."
            ),
        },
        {
            "name": "migration",
            "description": "Data migration utilities from legacy PDF system.",
        },
        {
            "name": "security",
            "description": "Audit log and rate-limit statistics endpoints.",
        },
        {
            "name": "collections",
            "description": "Low-level Qdrant collection and point management.",
        },
    ],
)

# Allow the SvelteKit dev server to talk to this API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
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


@app.get("/health", tags=["health"])
def health(client: QdrantClient = Depends(get_qdrant_client)) -> dict[str, Any]:
    """Basic readiness probe to ensure we can talk to Qdrant."""

    try:
        _ = client.get_collections()
    except Exception as exc:  # pragma: no cover - connectivity guard
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to reach Qdrant: {exc}",
        ) from exc

    return {"status": "ok"}


@app.get("/health/detailed", tags=["health"])
def health_detailed(client: QdrantClient = Depends(get_qdrant_client)) -> dict[str, Any]:
    """
    Detailed health check reporting service availability and degradation status.

    Implements Requirement 17.2: graceful degradation when external services are unavailable.
    """
    qdrant_status = check_qdrant_health(client)

    services = {
        "qdrant": qdrant_status.model_dump(),
    }

    overall_healthy = qdrant_status.is_available
    http_status = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if overall_healthy else "degraded",
        "services": services,
        "user_message": (
            "Tutti i servizi sono operativi."
            if overall_healthy
            else "Alcuni servizi non sono disponibili. Alcune funzionalità potrebbero essere limitate."
        ),
    }


@app.get("/audit/log", tags=["security"])
def get_audit_log_endpoint(
    limit: int = 100,
) -> dict[str, Any]:
    """
    Return recent audit log entries for content management operations.

    Requirement 18.5: audit logging for content management operations.
    """
    entries = get_audit_log(limit=min(limit, 500))
    return {
        "entries": [e.model_dump() for e in entries],
        "total": len(entries),
    }


@app.get("/security/rate-limit-stats", tags=["security"])
def get_rate_limit_stats(
    client_key: str = "default",
) -> dict[str, Any]:
    """
    Return current rate limit counters for a client key.

    Requirement 18.3: rate limiting visibility.
    """
    limiter = get_rate_limiter()
    return limiter.get_stats(client_key)


@app.post("/collections", status_code=status.HTTP_201_CREATED, tags=["collections"])
def create_collection(
    payload: CreateCollectionRequest,
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict[str, str]:
    """Create (or recreate) a Qdrant collection with the provided vector config."""

    try:
        client.delete_collection(collection_name=payload.name)
    except Exception:
        pass
    client.create_collection(
        collection_name=payload.name,
        vectors_config=VectorParams(
            size=payload.vector_size, distance=_distance_from_label(payload.distance)
        ),
    )
    return {"message": f"Collection '{payload.name}' ready."}


@app.post("/points", status_code=status.HTTP_202_ACCEPTED, tags=["collections"])
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


@app.post("/search", response_model=list[SearchResult], tags=["collections"])
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


@app.post("/semantic/ingest", status_code=status.HTTP_202_ACCEPTED, tags=["semantic"])
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
    try:
        collection_info = client.get_collection(body.collection_name)
        existing_size = collection_info.config.params.vectors.size
        if existing_size != vector_size:
            # Vector size mismatch — recreate
            client.delete_collection(collection_name=body.collection_name)
            client.create_collection(
                collection_name=body.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        # else: collection exists with correct size — keep existing data, just upsert
    except Exception:
        # Collection doesn't exist — create it
        client.create_collection(
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


@app.post("/semantic/search", response_model=list[SemanticSearchHit], tags=["semantic"])
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

# Initialize folder service
folder_service = None


async def get_folder_service() -> FolderService:
    """Get or create folder service instance."""
    global folder_service
    if folder_service is None:
        from .dependencies import get_qdrant_client
        client = get_qdrant_client()
        folder_service = FolderService(client)
        await folder_service.initialize()
    return folder_service


async def get_migration_service() -> MigrationService:
    """Get migration service instance."""
    from .dependencies import get_qdrant_client
    client = get_qdrant_client()
    folder_svc = await get_folder_service()
    return MigrationService(client, folder_svc)


async def get_system_migration_service() -> SystemMigrationService:
    """Get system migration service instance."""
    from .dependencies import get_qdrant_client
    client = get_qdrant_client()
    folder_svc = await get_folder_service()
    return SystemMigrationService(client, folder_svc)


@app.post("/pdf/upload", status_code=status.HTTP_201_CREATED, tags=["pdf"])
async def upload_pdf(
    file: UploadFile = File(...),
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict[str, Any]:
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
        err = make_upload_error(
            file.filename or "unknown",
            ErrorCode.UPLOAD_FORMAT_UNSUPPORTED,
            "File must be a PDF (.pdf extension required)",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err.user_message,
        )

    # Sanitize filename (Requirement 18.4)
    safe_filename = sanitize_filename(file.filename)
    if not safe_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    # Rate limiting (Requirement 18.3)
    limiter = get_rate_limiter()
    allowed, rate_info = limiter.check_rate_limit("pdf_upload", limiter.UPLOAD_CONFIG)
    if not allowed:
        log_audit_event(
            AuditAction.PDF_UPLOAD,
            "pdf",
            resource_id=safe_filename,
            details={"rate_limit_info": rate_info},
            success=False,
            error_message="Rate limit exceeded",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please retry after {rate_info.get('retry_after', 60)} seconds.",
        )

    op_start = time.monotonic()
    try:
        # 1) Read file content
        file_content = await file.read()

        # Validate file type and scan for malicious content (Requirement 18.2)
        validation_result = validate_and_scan_file(
            file_content, safe_filename, allowed_types={"application/pdf"}
        )
        if not validation_result.is_valid:
            log_audit_event(
                AuditAction.PDF_UPLOAD,
                "pdf",
                resource_id=safe_filename,
                details={"validation_error": validation_result.error_message},
                success=False,
                error_message=validation_result.error_message,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result.error_message,
            )
        
        # 2) Save PDF to disk
        file_path = save_pdf(file_content, safe_filename, str(PDFS_DIR))
        filename = Path(file_path).name
        
        # 3) Extract text from PDF (per-page)
        try:
            pages = extract_text_from_pdf(file_content)
        except ValueError as e:
            err = make_upload_error(
                filename,
                ErrorCode.UPLOAD_EXTRACTION_FAILED,
                str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err.user_message,
            ) from e

        # 4) Chunk per page, tagging each chunk with its page number
        indexed_at = datetime.now(timezone.utc).isoformat()
        all_chunks: list[tuple[int, str]] = []  # (page_number, chunk_text)
        for page_number, page_text in pages:
            page_chunks = chunk_text(page_text, chunk_size=1000, overlap=200)
            for chunk in page_chunks:
                all_chunks.append((page_number, chunk))

        if not all_chunks:
            err = make_upload_error(
                filename,
                ErrorCode.UPLOAD_NO_TEXT,
                "PDF contains no extractable text",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=err.user_message,
            )

        # 5) Generate embeddings for all chunks
        text_chunks = [chunk for _, chunk in all_chunks]
        try:
            vectors = embed_text_batch(text_chunks)
        except Exception as e:
            err = make_upload_error(
                filename,
                ErrorCode.UPLOAD_INDEXING_FAILED,
                f"Embedding generation failed: {e}",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=err.user_message,
            ) from e

        if not vectors:
            err = make_upload_error(
                filename,
                ErrorCode.UPLOAD_INDEXING_FAILED,
                "Failed to generate embeddings",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=err.user_message,
            )

        # Ensure text_chunks and vectors have the same length
        if len(text_chunks) != len(vectors):
            err = make_upload_error(
                filename,
                ErrorCode.UPLOAD_INDEXING_FAILED,
                f"Mismatch between chunks ({len(text_chunks)}) and vectors ({len(vectors)})",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=err.user_message,
            )

        vector_size = len(vectors[0])
        
        # 6) Ensure collection exists with the embedding model's vector size
        try:
            collection_info = client.get_collection(PDF_COLLECTION)
            if collection_info.config.params.vectors.size != vector_size:
                # Recreate if size doesn't match
                try:
                    client.delete_collection(collection_name=PDF_COLLECTION)
                except Exception:
                    pass
                client.create_collection(
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
        
        for chunk_idx, (page_number, chunk_text_content) in enumerate(all_chunks):
            vector = vectors[chunk_idx]
            # Create deterministic UUID based on filename and chunk index
            unique_name = f"{filename}:{chunk_idx}"
            point_id = str(uuid.uuid5(PDF_NAMESPACE, unique_name))
            
            payload = {
                "filename": filename,
                "file_path": file_path,
                "relative_url": relative_url,
                "chunk_index": chunk_idx,
                "chunk_text": chunk_text_content[:500],
                "total_chunks": len(all_chunks),
                "page_number": page_number,
                "indexed_at": indexed_at,
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
        
        elapsed_ms = log_operation_timing(logger, f"pdf_upload:{filename}", op_start)

        # Audit log successful upload (Requirement 18.5)
        log_audit_event(
            AuditAction.PDF_UPLOAD,
            "pdf",
            resource_id=filename,
            details={"chunks_indexed": len(points), "processing_time_ms": round(elapsed_ms, 1)},
            success=True,
        )

        return {
            "message": f"PDF '{filename}' uploaded and indexed successfully",
            "filename": filename,
            "relative_url": relative_url,
            "chunks_indexed": len(points),
            "processing_time_ms": round(elapsed_ms, 1),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_error_with_context(logger, "Unexpected error during PDF upload", e)
        err = make_upload_error(
            file.filename or "unknown",
            ErrorCode.UPLOAD_INDEXING_FAILED,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=err.user_message,
        ) from e


@app.post("/pdf/index-all", status_code=status.HTTP_200_OK, tags=["pdf"])
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
                try:
                    client.delete_collection(collection_name=PDF_COLLECTION)
                except Exception:
                    pass
                client.create_collection(
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
                
                # Extract text per page
                pages = extract_text_from_pdf_file(pdf_file)

                # Chunk per page, tagging each chunk with its page number
                indexed_at = datetime.now(timezone.utc).isoformat()
                all_chunks: list[tuple[int, str]] = []
                for page_number, page_text in pages:
                    page_chunks = chunk_text(page_text, chunk_size=1000, overlap=200)
                    for chunk in page_chunks:
                        all_chunks.append((page_number, chunk))

                if not all_chunks:
                    errors.append(f"{filename}: No extractable text")
                    continue

                print(f"  Extracted {len(all_chunks)} chunks")

                # Generate embeddings
                text_chunks = [chunk for _, chunk in all_chunks]
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
                
                for chunk_idx, (page_number, chunk_text_content) in enumerate(all_chunks):
                    vector = vectors[chunk_idx]
                    
                    # Create deterministic UUID based on filename and chunk index
                    unique_name = f"{filename}:{chunk_idx}"
                    point_id = str(uuid.uuid5(PDF_NAMESPACE, unique_name))
                    
                    payload = {
                        "filename": filename,
                        "file_path": str(pdf_file.absolute()),
                        "relative_url": relative_url,
                        "chunk_index": chunk_idx,
                        "chunk_text": chunk_text_content[:500],
                        "total_chunks": len(all_chunks),
                        "page_number": page_number,
                        "indexed_at": indexed_at,
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


@app.get("/pdf/list", response_model=list[IndexedPDF], tags=["pdf"])
async def list_pdfs(
    client: QdrantClient = Depends(get_qdrant_client),
) -> list[IndexedPDF]:
    """List all indexed PDFs with metadata."""
    try:
        # Scroll all points from the collection
        all_points = []
        offset = None
        while True:
            result, next_offset = client.scroll(
                collection_name=PDF_COLLECTION,
                limit=100,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            all_points.extend(result)
            if next_offset is None:
                break
            offset = next_offset

        if not all_points:
            return []

        # Group by filename
        pdf_map: dict[str, dict] = {}
        for point in all_points:
            payload = point.payload or {}
            filename = payload.get("filename", "")
            if not filename:
                continue
            if filename not in pdf_map:
                pdf_map[filename] = {
                    "filename": filename,
                    "relative_url": payload.get("relative_url", f"/pdf-source/{filename}"),
                    "chunk_count": 0,
                    "indexed_at": payload.get("indexed_at", ""),
                }
            pdf_map[filename]["chunk_count"] += 1

        return [
            IndexedPDF(
                filename=info["filename"],
                relative_url=info["relative_url"],
                chunk_count=info["chunk_count"],
                indexed_at=info["indexed_at"],
            )
            for info in sorted(pdf_map.values(), key=lambda x: x["filename"])
        ]

    except Exception as e:
        # If collection doesn't exist, return empty list
        if "not found" in str(e).lower() or "doesn't exist" in str(e).lower():
            return []
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing PDFs: {str(e)}",
        ) from e


@app.delete("/pdf/{filename}", status_code=status.HTTP_200_OK, tags=["pdf"])
async def delete_pdf(
    filename: str,
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict[str, str]:
    """Delete a PDF and all its indexed vectors."""
    # Validate and sanitize filename (Requirement 18.1 + 18.4)
    try:
        filename = validate_pdf_filename(filename)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # Check if any points exist for this filename
    has_points = False
    try:
        results, _ = client.scroll(
            collection_name=PDF_COLLECTION,
            scroll_filter=Filter(
                must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
            ),
            limit=1,
            with_payload=False,
            with_vectors=False,
        )
        has_points = len(results) > 0
    except Exception:
        pass

    # Check if file exists on disk
    file_path = PDFS_DIR / filename
    has_file = file_path.exists()

    if not has_points and not has_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No indexed points or file found for '{filename}'",
        )

    # Delete Qdrant points
    if has_points:
        try:
            client.delete(
                collection_name=PDF_COLLECTION,
                points_selector=Filter(
                    must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
                ),
            )
        except Exception as e:
            log_audit_event(
                AuditAction.PDF_DELETE,
                "pdf",
                resource_id=filename,
                success=False,
                error_message=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete indexed points: {str(e)}",
            ) from e

    # Delete file from disk
    if has_file:
        file_path.unlink()

    # Audit log (Requirement 18.5)
    log_audit_event(
        AuditAction.PDF_DELETE,
        "pdf",
        resource_id=filename,
        success=True,
    )

    return {"message": f"PDF '{filename}' deleted successfully"}


@app.post("/pdf/reindex/{filename}", status_code=status.HTTP_200_OK, tags=["pdf"])
async def reindex_pdf(
    filename: str,
    client: QdrantClient = Depends(get_qdrant_client),
) -> dict[str, Any]:
    """Re-index a single PDF: delete existing points and re-extract/re-embed."""
    file_path = PDFS_DIR / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found in pdf-source: '{filename}'",
        )

    try:
        # 1) Delete existing Qdrant points for this filename
        try:
            client.delete(
                collection_name=PDF_COLLECTION,
                points_selector=Filter(
                    must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
                ),
            )
        except Exception:
            pass  # Collection may not exist yet

        # 2) Re-extract text per page
        pages = extract_text_from_pdf_file(file_path)

        # 3) Chunk per page
        indexed_at = datetime.now(timezone.utc).isoformat()
        relative_url = f"/pdf-source/{filename}"
        all_chunks: list[tuple[int, str]] = []
        for page_number, page_text in pages:
            page_chunks = chunk_text(page_text, chunk_size=1000, overlap=200)
            for chunk in page_chunks:
                all_chunks.append((page_number, chunk))

        if not all_chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF contains no extractable text",
            )

        # 4) Generate embeddings
        text_chunks = [chunk for _, chunk in all_chunks]
        vectors = embed_text_batch(text_chunks)
        vector_size = len(vectors[0])

        # 5) Ensure collection exists
        try:
            collection_info = client.get_collection(PDF_COLLECTION)
            if collection_info.config.params.vectors.size != vector_size:
                try:
                    client.delete_collection(collection_name=PDF_COLLECTION)
                except Exception:
                    pass
                client.create_collection(
                    collection_name=PDF_COLLECTION,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
        except Exception:
            client.create_collection(
                collection_name=PDF_COLLECTION,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

        # 6) Upsert new points
        points: list[PointStruct] = []
        for chunk_idx, (page_number, chunk_text_content) in enumerate(all_chunks):
            vector = vectors[chunk_idx]
            unique_name = f"{filename}:{chunk_idx}"
            point_id = str(uuid.uuid5(PDF_NAMESPACE, unique_name))
            payload = {
                "filename": filename,
                "file_path": str(file_path.absolute()),
                "relative_url": relative_url,
                "chunk_index": chunk_idx,
                "chunk_text": chunk_text_content[:500],
                "total_chunks": len(all_chunks),
                "page_number": page_number,
                "indexed_at": indexed_at,
            }
            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        client.upsert(collection_name=PDF_COLLECTION, points=points)

        return {
            "message": f"PDF '{filename}' re-indexed successfully",
            "chunks_indexed": len(points),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error re-indexing PDF: {str(e)}",
        ) from e


@app.post("/pdf/search", response_model=PDFSearchResponse, tags=["pdf"])
async def search_pdfs(
    body: PDFSearchRequest,
    client: QdrantClient = Depends(get_qdrant_client),
) -> PDFSearchResponse:
    """
    Perform hybrid search (semantic + keyword) across indexed PDF documents.

    Given a search query (keywords or natural language), returns a list of unique PDF files
    that contain relevant content, ordered by relevance score.
    
    The search combines:
    - Semantic similarity (using embeddings) - good for concepts and meaning
    - Keyword matching (exact word matches) - good for names and specific terms
    """

    # Sanitize and validate search query (Requirement 18.1 + 18.4)
    sanitized_query = sanitize_search_query(body.query)
    if not sanitized_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty",
        )
    if detect_sql_injection(sanitized_query):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query contains invalid characters",
        )

    # Rate limiting (Requirement 18.3)
    limiter = get_rate_limiter()
    allowed, rate_info = limiter.check_rate_limit("pdf_search", limiter.SEARCH_CONFIG)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please retry after {rate_info.get('retry_after', 60)} seconds.",
        )

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
            return PDFSearchResponse(results=[], total=0, offset=body.offset, limit=body.limit)
        
        # 3) Group hits by filename, apply keyword boost, and keep best match
        pdf_map: dict[str, dict] = {}
        
        for hit in hits:
            payload = hit.payload or {}
            filename = payload.get("filename", "")
            relative_url = payload.get("relative_url", f"/pdf-source/{filename}")
            chunk_text_content = payload.get("chunk_text", "")
            
            if not filename:
                continue
            
            # Normalize cosine similarity from [-1, 1] to [0, 1]
            semantic_score = normalize_cosine_score(hit.score)
            
            # Apply keyword boost if enabled
            keyword_boost = 0.0
            final_score = semantic_score
            if body.use_keyword_boost:
                keyword_boost = calculate_keyword_boost(body.query, chunk_text_content)
                # Combine semantic score with keyword boost (additive, capped at 1.0)
                final_score = min(semantic_score + keyword_boost, 1.0)
            
            # Keep the highest scoring chunk for each PDF
            page_number = payload.get("page_number")
            if filename not in pdf_map or final_score > pdf_map[filename]["score"]:
                pdf_map[filename] = {
                    "filename": filename,
                    "relative_url": relative_url,
                    "score": final_score,
                    "preview_text": chunk_text_content[:500],
                    "semantic_score": semantic_score,
                    "keyword_boost": keyword_boost,
                    "page_number": page_number,
                }
        
        # Apply filename filter if provided
        if body.filename_filter:
            filter_lower = body.filename_filter.lower()
            pdf_map = {
                k: v for k, v in pdf_map.items()
                if filter_lower in k.lower()
            }

        # 4) Sort by score, apply filename filter, then paginate
        all_sorted = sorted(
            pdf_map.values(),
            key=lambda x: x["score"],
            reverse=True,
        )
        total = len(all_sorted)
        paginated = all_sorted[body.offset : body.offset + body.limit]

        return PDFSearchResponse(
            results=[
                PDFSearchResult(
                    filename=result["filename"],
                    relative_url=result["relative_url"],
                    score=result["score"],
                    preview_text=result["preview_text"],
                    page_number=result.get("page_number"),
                )
                for result in paginated
            ],
            total=total,
            offset=body.offset,
            limit=body.limit,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during PDF search: {str(e)}",
        ) from e


#
# Folder management endpoints
#


@app.post("/folders", response_model=FolderResponse, status_code=status.HTTP_201_CREATED, tags=["folders"])
async def create_folder(
    request: CreateFolderRequest,
    service: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    """Create a new folder with Qdrant collection."""
    
    try:
        # Convert content types from strings to enums
        content_types = []
        for ct_str in request.content_types:
            try:
                content_types.append(ContentType(ct_str))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid content type: {ct_str}"
                )
        
        folder_def = FolderDefinition(
            name=request.name,
            description=request.description,
            parent_id=request.parent_id,
            content_types=content_types,
            metadata=request.metadata
        )
        
        folder = await service.create_folder(folder_def)
        
        # Audit log (Requirement 18.5)
        log_audit_event(
            AuditAction.FOLDER_CREATE,
            "folder",
            resource_id=folder.id,
            details={"name": folder.name, "path": folder.path},
            success=True,
        )

        return FolderResponse(
            id=folder.id,
            name=folder.name,
            description=folder.description,
            parent_id=folder.parent_id,
            path=folder.path,
            content_types=[ct.value for ct in folder.content_types],
            qdrant_collection=folder.qdrant_collection,
            metadata=folder.metadata,
            created_at=folder.created_at.isoformat(),
            updated_at=folder.updated_at.isoformat(),
            content_count=folder.content_count
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create folder: {str(e)}"
        )


@app.get("/folders", response_model=FolderListResponse, tags=["folders"])
async def list_folders(
    service: FolderService = Depends(get_folder_service),
) -> FolderListResponse:
    """List all folders."""
    
    try:
        folders = await service.list_folders()
        
        folder_responses = []
        for folder in folders:
            folder_responses.append(FolderResponse(
                id=folder.id,
                name=folder.name,
                description=folder.description,
                parent_id=folder.parent_id,
                path=folder.path,
                content_types=[ct.value for ct in folder.content_types],
                qdrant_collection=folder.qdrant_collection,
                metadata=folder.metadata,
                created_at=folder.created_at.isoformat(),
                updated_at=folder.updated_at.isoformat(),
                content_count=folder.content_count
            ))
        
        return FolderListResponse(
            folders=folder_responses,
            total=len(folder_responses)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list folders: {str(e)}"
        )


@app.get("/folders/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: str,
    service: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    """Get folder by ID."""
    
    folder = await service.get_folder(folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder {folder_id} not found"
        )
    
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        description=folder.description,
        parent_id=folder.parent_id,
        path=folder.path,
        content_types=[ct.value for ct in folder.content_types],
        qdrant_collection=folder.qdrant_collection,
        metadata=folder.metadata,
        created_at=folder.created_at.isoformat(),
        updated_at=folder.updated_at.isoformat(),
        content_count=folder.content_count
    )


@app.put("/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    request: UpdateFolderRequest,
    service: FolderService = Depends(get_folder_service),
) -> FolderResponse:
    """Update folder metadata."""
    
    # Prepare updates dictionary
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.description is not None:
        updates["description"] = request.description
    if request.metadata is not None:
        updates["metadata"] = request.metadata
    
    folder = await service.update_folder(folder_id, updates)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder {folder_id} not found"
        )
    
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        description=folder.description,
        parent_id=folder.parent_id,
        path=folder.path,
        content_types=[ct.value for ct in folder.content_types],
        qdrant_collection=folder.qdrant_collection,
        metadata=folder.metadata,
        created_at=folder.created_at.isoformat(),
        updated_at=folder.updated_at.isoformat(),
        content_count=folder.content_count
    )


@app.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: str,
    force: bool = False,
    service: FolderService = Depends(get_folder_service),
) -> None:
    """Delete folder and its Qdrant collection."""
    success = await service.delete_folder(folder_id, force=force)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Folder {folder_id} not found"
        )
    # Audit log (Requirement 18.5)
    log_audit_event(
        AuditAction.FOLDER_DELETE,
        "folder",
        resource_id=folder_id,
        success=True,
    )


@app.get("/folders/hierarchy", response_model=list[dict])
async def get_folder_hierarchy(
    service: FolderService = Depends(get_folder_service),
) -> list[dict]:
    """Get complete folder hierarchy tree."""
    
    try:
        hierarchy = await service.get_folder_hierarchy()
        
        # Convert to serializable format
        def serialize_tree(tree):
            return {
                "folder": {
                    "id": tree.folder.id,
                    "name": tree.folder.name,
                    "description": tree.folder.description,
                    "parent_id": tree.folder.parent_id,
                    "path": tree.folder.path,
                    "content_types": [ct.value for ct in tree.folder.content_types],
                    "qdrant_collection": tree.folder.qdrant_collection,
                    "metadata": tree.folder.metadata,
                    "created_at": tree.folder.created_at.isoformat(),
                    "updated_at": tree.folder.updated_at.isoformat(),
                    "content_count": tree.folder.content_count
                },
                "children": [serialize_tree(child) for child in tree.children],
                "content_summary": {
                    "total_documents": tree.content_summary.total_documents,
                    "content_type_counts": tree.content_summary.content_type_counts,
                    "last_updated": tree.content_summary.last_updated.isoformat() if tree.content_summary.last_updated else None,
                    "size_bytes": tree.content_summary.size_bytes
                }
            }
        
        return [serialize_tree(tree) for tree in hierarchy]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get folder hierarchy: {str(e)}"
        )


@app.post("/folders/assign-content", status_code=status.HTTP_200_OK)
async def assign_content_to_folder(
    request: AssignContentRequest,
    service: FolderService = Depends(get_folder_service),
) -> dict[str, str]:
    """Assign content to a folder."""
    
    # This is a placeholder - in a full implementation, you would:
    # 1. Retrieve the content by ID
    # 2. Create a Document object
    # 3. Call service.assign_content_to_folder()
    
    # For now, return success message
    return {"message": f"Content {request.content_id} assigned to folder {request.folder_id}"}


@app.post("/folders/move-content", status_code=status.HTTP_200_OK)
async def move_content_between_folders(
    request: MoveContentRequest,
    service: FolderService = Depends(get_folder_service),
) -> dict[str, str]:
    """Move content between folders."""
    
    try:
        await service.move_content(
            request.content_id,
            request.from_folder_id,
            request.to_folder_id
        )
        
        return {
            "message": f"Content {request.content_id} moved from {request.from_folder_id} to {request.to_folder_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to move content: {str(e)}"
        )


#
# Migration endpoints
#


@app.post("/migration/migrate-pdfs", status_code=status.HTTP_200_OK)
async def migrate_existing_pdfs(
    migration_service: MigrationService = Depends(get_migration_service),
) -> dict[str, Any]:
    """Migrate existing PDF collection to Dispositivi folder."""
    
    try:
        result = await migration_service.migrate_existing_pdfs()
        
        return {
            "success": result.success,
            "message": result.message,
            "migrated_count": result.migrated_count,
            "errors": result.errors
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration failed: {str(e)}"
        )


@app.get("/migration/validate", status_code=status.HTTP_200_OK)
async def validate_migration(
    migration_service: MigrationService = Depends(get_migration_service),
) -> dict[str, Any]:
    """Validate migration integrity."""
    
    try:
        validation_result = await migration_service.validate_migration()
        return validation_result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration validation failed: {str(e)}"
        )


@app.post("/migration/rollback", status_code=status.HTTP_200_OK)
async def rollback_migration(
    migration_service: MigrationService = Depends(get_migration_service),
) -> dict[str, Any]:
    """Rollback migration by removing migrated content."""
    
    try:
        result = await migration_service.rollback_migration()
        
        return {
            "success": result.success,
            "message": result.message,
            "errors": result.errors
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration rollback failed: {str(e)}"
        )


@app.post("/migration/execute", status_code=status.HTTP_200_OK)
async def execute_migration(
    system_migration_service: SystemMigrationService = Depends(get_system_migration_service),
) -> dict[str, Any]:
    """
    Execute the complete migration from the existing PDF system to the folder structure.

    This endpoint orchestrates all migration steps:
    1. Create folder infrastructure (Dispositivi folder + Qdrant collection)
    2. Migrate existing PDF data with folder metadata
    3. Validate migration integrity

    The operation is **idempotent** – running it multiple times is safe because
    Qdrant upsert uses the original point IDs and the Dispositivi folder creation
    is guarded by a name lookup.

    On failure, a rollback is automatically attempted to restore the previous state.
    """

    try:
        report = await system_migration_service.execute_migration()

        return {
            "success": report.success,
            "steps_completed": report.steps_completed,
            "migration_time": report.migration_time,
            "details": report.details,
            "errors": report.errors,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Migration execution failed: {str(e)}",
        )


@app.get("/migration/status", status_code=status.HTTP_200_OK)
async def get_migration_status(
    migration_service: MigrationService = Depends(get_migration_service),
) -> dict[str, Any]:
    """
    Get the current migration status without executing any migration.

    Returns information about:
    - Whether the source PDF collection exists and its document count
    - Whether the Dispositivi destination folder exists and its document count
    - The overall migration state: not_started | partial | completed | no_data | source_removed | error
    """

    try:
        return await migration_service.get_migration_status()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve migration status: {str(e)}",
        )


#
# Device recognition endpoints (Requirements 9.1-9.5)
#


@app.post("/device/recognize", response_model=DeviceRecognitionResponse)
async def recognize_device_from_photo(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.7,
    service: DeviceRecognitionService = Depends(get_device_recognition_service),
) -> DeviceRecognitionResponse:
    """
    Recognize a device from an uploaded photo.

    Accepts JPEG, PNG, or WebP images up to 10 MB.
    Returns device identification with confidence score and alternative matches.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Validate content type hint (not strictly enforced – magic bytes are checked in service)
    allowed_content_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type and file.content_type not in allowed_content_types:
        err = make_device_recognition_error(
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            f"Content type: {file.content_type}",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err.user_message,
        )

    op_start = time.monotonic()
    try:
        image_data = await file.read()
    except Exception as exc:
        err = make_device_recognition_error(
            ErrorCode.RECOGNITION_FAILED,
            f"Failed to read uploaded file: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err.user_message,
        ) from exc

    # Rate limiting for device recognition (Requirement 18.3)
    limiter = get_rate_limiter()
    allowed, rate_info = limiter.check_rate_limit("device_recognize", limiter.DEVICE_RECOGNITION_CONFIG)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please retry after {rate_info.get('retry_after', 60)} seconds.",
        )

    result = await service.recognize_device_from_photo(
        image_data=image_data,
        confidence_threshold=confidence_threshold,
    )

    # Log timing for monitoring (Req 17.4)
    log_operation_timing(logger, "device_recognize", op_start)

    # Map validation errors from service to structured responses
    if result.error_message:
        if "size" in result.error_message.lower() or "10 mb" in result.error_message.lower():
            structured_err = make_device_recognition_error(
                ErrorCode.IMAGE_TOO_LARGE, result.error_message
            )
            result.error_message = structured_err.user_message
        elif "format" in result.error_message.lower() or "unsupported" in result.error_message.lower():
            structured_err = make_device_recognition_error(
                ErrorCode.IMAGE_FORMAT_UNSUPPORTED, result.error_message
            )
            result.error_message = structured_err.user_message
        elif "confidence" in result.error_message.lower() or "threshold" in result.error_message.lower():
            structured_err = make_device_recognition_error(
                ErrorCode.RECOGNITION_LOW_CONFIDENCE, result.error_message
            )
            result.error_message = structured_err.user_message

    return DeviceRecognitionResponse(
        device_id=result.device_id,
        device_name=result.device_name,
        manufacturer=result.manufacturer,
        model=result.model,
        confidence=result.confidence,
        alternative_matches=[
            {
                "device_id": m.device_id,
                "device_name": m.device_name,
                "manufacturer": m.manufacturer,
                "model": m.model,
                "confidence": m.confidence,
                "similarity_reasons": m.similarity_reasons,
            }
            for m in result.alternative_matches
        ],
        processing_time_ms=result.processing_time_ms,
        error_message=result.error_message,
        is_mock=service.get_service_info()["is_mock"],
    )


@app.post("/device/scan-qr", response_model=QRCodeWithDocumentationResponse)
async def scan_qr_code(
    file: UploadFile = File(...),
    service: DeviceRecognitionService = Depends(get_device_recognition_service),
    db: DeviceDatabase = Depends(get_device_database),
) -> QRCodeWithDocumentationResponse:
    """
    Decode a QR code from an uploaded image.

    Accepts JPEG, PNG, or WebP images up to 10 MB.
    Returns the decoded QR code content and metadata.

    When the QR code contains device identification data, automatically
    retrieves corresponding documentation from the device database
    (Requirement 2.3).
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    op_start = time.monotonic()
    try:
        image_data = await file.read()
    except Exception as exc:
        err = make_device_recognition_error(
            ErrorCode.RECOGNITION_FAILED,
            f"Failed to read uploaded file: {exc}",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err.user_message,
        ) from exc

    result = await service.decode_qr_code(image_data=image_data)

    # Log timing (Req 17.4)
    log_operation_timing(logger, "qr_scan", op_start)

    if not result.content:
        err = make_device_recognition_error(
            ErrorCode.QR_NOT_DETECTED,
            "No QR code detected in the provided image",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=err.user_message,
        )

    # Requirement 2.3: look up device documentation when QR contains device info
    device_match = db.find_by_qr_code(result.content)
    device_response: DeviceResponse | None = None
    documentation_urls: list[str] = []

    if device_match:
        device_response = DeviceResponse(
            id=device_match.id,
            name=device_match.name,
            manufacturer=device_match.manufacturer,
            model=device_match.model,
            category=device_match.category,
            specifications=device_match.specifications,
            qr_codes=device_match.qr_codes,
            documentation_urls=device_match.documentation_urls,
            created_at=device_match.created_at,
            updated_at=device_match.updated_at,
        )
        documentation_urls = device_match.documentation_urls

    return QRCodeWithDocumentationResponse(
        content=result.content,
        format=result.format.value,
        confidence=result.confidence,
        bounding_box=result.bounding_box,
        is_mock=service.get_service_info()["is_mock"],
        device_match=device_response,
        documentation_urls=documentation_urls,
    )


@app.get("/device/ai-info", response_model=AIServiceInfoResponse)
async def get_ai_service_info(
    service: DeviceRecognitionService = Depends(get_device_recognition_service),
) -> AIServiceInfoResponse:
    """
    Return information about the current AI service configuration.

    Useful for verifying whether the mock or a real model is active.
    """
    info = service.get_service_info()
    return AIServiceInfoResponse(**info)


@app.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...)) -> dict[str, str]:
    """
    Accept an image upload and return a placeholder analysis.

    Deprecated: use /device/recognize for device recognition.
    """
    _ = await file.read()

    return {
        "filename": file.filename or "uploaded-image",
        "content_type": file.content_type or "image/*",
        "summary": "Image received correctly. Use /device/recognize for device recognition.",
    }


#
# Device database endpoints (Requirements 1.1-1.4, 2.1-2.4)
#


def _device_record_to_response(record: DeviceRecord) -> DeviceResponse:
    """Convert a DeviceRecord to a DeviceResponse."""
    return DeviceResponse(
        id=record.id,
        name=record.name,
        manufacturer=record.manufacturer,
        model=record.model,
        category=record.category,
        specifications=record.specifications,
        qr_codes=record.qr_codes,
        documentation_urls=record.documentation_urls,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@app.get("/devices/search", response_model=DeviceListResponse)
def search_devices(
    q: str = "",
    db: DeviceDatabase = Depends(get_device_database),
) -> DeviceListResponse:
    """
    Search devices by name, manufacturer, or model.

    Query parameter ``q`` is matched as a case-insensitive substring against
    the name, manufacturer, model, and category fields.  An empty query
    returns all devices.
    """
    records = db.search(q)
    return DeviceListResponse(
        devices=[_device_record_to_response(r) for r in records],
        total=len(records),
    )


@app.get("/devices", response_model=DeviceListResponse)
def list_devices(
    db: DeviceDatabase = Depends(get_device_database),
) -> DeviceListResponse:
    """List all devices in the database."""
    records = db.list_all()
    return DeviceListResponse(
        devices=[_device_record_to_response(r) for r in records],
        total=len(records),
    )


@app.post("/devices", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    payload: DeviceCreate,
    db: DeviceDatabase = Depends(get_device_database),
) -> DeviceResponse:
    """Add a new device to the database."""
    # Sanitize text inputs (Requirement 18.4)
    record = db.create(
        name=sanitize_text_input(payload.name, max_length=200),
        manufacturer=sanitize_text_input(payload.manufacturer, max_length=200),
        model=sanitize_text_input(payload.model, max_length=200),
        category=payload.category,
        specifications=payload.specifications,
        qr_codes=payload.qr_codes,
        documentation_urls=payload.documentation_urls,
    )
    # Audit log (Requirement 18.5)
    log_audit_event(
        AuditAction.DEVICE_CREATE,
        "device",
        resource_id=record.id,
        details={"name": record.name, "manufacturer": record.manufacturer},
        success=True,
    )
    return _device_record_to_response(record)


@app.get("/devices/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: str,
    db: DeviceDatabase = Depends(get_device_database),
) -> DeviceResponse:
    """Get a specific device by ID."""
    record = db.get(device_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found",
        )
    return _device_record_to_response(record)


@app.put("/devices/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: str,
    payload: DeviceUpdate,
    db: DeviceDatabase = Depends(get_device_database),
) -> DeviceResponse:
    """Update device information."""
    # Validate device_id (Requirement 18.1)
    try:
        device_id = validate_device_id(device_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    record = db.update(
        device_id=device_id,
        name=sanitize_text_input(payload.name, max_length=200) if payload.name else None,
        manufacturer=sanitize_text_input(payload.manufacturer, max_length=200) if payload.manufacturer else None,
        model=sanitize_text_input(payload.model, max_length=200) if payload.model else None,
        category=payload.category,
        specifications=payload.specifications,
        qr_codes=payload.qr_codes,
        documentation_urls=payload.documentation_urls,
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found",
        )
    # Audit log (Requirement 18.5)
    log_audit_event(
        AuditAction.DEVICE_UPDATE,
        "device",
        resource_id=device_id,
        success=True,
    )
    return _device_record_to_response(record)


@app.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(
    device_id: str,
    db: DeviceDatabase = Depends(get_device_database),
) -> None:
    """Remove a device from the database."""
    # Validate device_id (Requirement 18.1)
    try:
        device_id = validate_device_id(device_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    deleted = db.delete(device_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found",
        )
    # Audit log (Requirement 18.5)
    log_audit_event(
        AuditAction.DEVICE_DELETE,
        "device",
        resource_id=device_id,
        success=True,
    )


@app.post("/device/recognize-and-lookup", response_model=RecognizeAndLookupResponse)
async def recognize_and_lookup(
    file: UploadFile = File(...),
    confidence_threshold: float = 0.7,
    service: DeviceRecognitionService = Depends(get_device_recognition_service),
    db: DeviceDatabase = Depends(get_device_database),
) -> RecognizeAndLookupResponse:
    """
    Recognize a device from a photo AND look it up in the local database.

    Combines AI-based device recognition (Requirements 1.2, 1.3) with a
    database lookup so that documentation URLs are returned alongside the
    recognition result.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    allowed_content_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type and file.content_type not in allowed_content_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported content type '{file.content_type}'. "
                   f"Supported: {', '.join(sorted(allowed_content_types))}",
        )

    try:
        image_data = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    result = await service.recognize_device_from_photo(
        image_data=image_data,
        confidence_threshold=confidence_threshold,
    )

    recognition_response = DeviceRecognitionResponse(
        device_id=result.device_id,
        device_name=result.device_name,
        manufacturer=result.manufacturer,
        model=result.model,
        confidence=result.confidence,
        alternative_matches=[
            {
                "device_id": m.device_id,
                "device_name": m.device_name,
                "manufacturer": m.manufacturer,
                "model": m.model,
                "confidence": m.confidence,
                "similarity_reasons": m.similarity_reasons,
            }
            for m in result.alternative_matches
        ],
        processing_time_ms=result.processing_time_ms,
        error_message=result.error_message,
        is_mock=service.get_service_info()["is_mock"],
    )

    # Attempt database lookup using the recognised device_id
    db_match: DeviceRecord | None = None
    if result.device_id:
        db_match = db.get(result.device_id)

    # Fallback: search by model name if no direct ID match
    if db_match is None and result.model:
        candidates = db.search(result.model)
        if candidates:
            db_match = candidates[0]

    db_response: DeviceResponse | None = None
    documentation_urls: list[str] = []
    if db_match:
        db_response = _device_record_to_response(db_match)
        documentation_urls = db_match.documentation_urls

    return RecognizeAndLookupResponse(
        recognition=recognition_response,
        database_match=db_response,
        documentation_urls=documentation_urls,
    )

#
# Content retrieval endpoints (Requirements 3.1-3.5, 13.1-13.5)
#

from .content_retrieval_service import (
    ContentRetrievalService,
    ContentSource,
    get_content_retrieval_service,
)


def _get_content_service(
    db: DeviceDatabase = Depends(get_device_database),
) -> ContentRetrievalService:
    """Dependency that returns a ContentRetrievalService wired to the device DB."""
    return get_content_retrieval_service(device_database=db)


@app.post("/content/retrieve", status_code=status.HTTP_200_OK)
async def retrieve_content(
    device_info: dict[str, Any],
    service: ContentRetrievalService = Depends(_get_content_service),
) -> dict[str, Any]:
    """
    Retrieve content for a device from all configured sources.

    Accepts a device_info dict (e.g. ``{"name": "Arduino Uno", "manufacturer": "Arduino"}``).
    Returns aggregated content from the internal database, web search, and YouTube.

    Implements Requirements 3.1-3.4.
    """
    try:
        collection = await service.retrieve_device_content(device_info)
        return collection.to_dict()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content retrieval failed: {exc}",
        ) from exc


@app.get("/content/sources", status_code=status.HTTP_200_OK)
async def list_content_sources(
    service: ContentRetrievalService = Depends(_get_content_service),
) -> dict[str, Any]:
    """
    List configured content sources and their current status / metrics.

    Implements Requirements 13.1, 13.2, 13.5.
    """
    try:
        metrics = service.get_source_metrics()
        return {
            "sources": [s.value for s in ContentSource],
            **metrics,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve source info: {exc}",
        ) from exc


@app.get("/content/cache/stats", status_code=status.HTTP_200_OK)
async def get_cache_stats(
    service: ContentRetrievalService = Depends(_get_content_service),
) -> dict[str, Any]:
    """
    Return content cache statistics.

    Implements Requirement 13.3 (caching visibility).
    """
    try:
        metrics = service.get_source_metrics()
        return metrics["cache_stats"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cache stats: {exc}",
        ) from exc


#
# Enhanced search endpoints (Requirements 4.1-4.5, 12.1-12.5)
#

from .search_service import EnhancedSearchService, SearchType, get_enhanced_search_service
from .schemas import (
    EnhancedSearchRequest,
    EnhancedSearchResult,
    EnhancedSearchResponse,
    DeviceContextSearchRequest,
    SearchSuggestionsResponse,
    SearchHistoryResponse,
)


def _get_search_service(
    client: QdrantClient = Depends(get_qdrant_client),
) -> EnhancedSearchService:
    """Dependency that returns the EnhancedSearchService singleton."""
    return get_enhanced_search_service(client)


def _results_to_response(
    results: list,
    query: str,
    folder_filter: list[str] | None,
    search_type: str,
) -> EnhancedSearchResponse:
    """Convert a list of SearchResult objects to an EnhancedSearchResponse."""
    return EnhancedSearchResponse(
        results=[
            EnhancedSearchResult(
                id=r.id,
                title=r.title,
                content=r.content,
                score=r.score,
                folder_id=r.folder_id,
                source=r.source,
                metadata=r.metadata,
            )
            for r in results
        ],
        total=len(results),
        query=query,
        folder_filter=folder_filter,
        search_type=search_type,
    )


@app.post("/search/semantic", response_model=EnhancedSearchResponse)
async def enhanced_semantic_search(
    body: EnhancedSearchRequest,
    service: EnhancedSearchService = Depends(_get_search_service),
) -> EnhancedSearchResponse:
    """
    Semantic (vector) search with optional folder filtering.

    - When *folder_filter* is provided, restricts results to those collections
      (Requirement 4.3).
    - When *folder_filter* is omitted, searches all available collections
      (Requirement 4.4).
    """
    # Sanitize query (Requirement 18.1 + 18.4)
    sanitized_query = sanitize_search_query(body.query)
    if not sanitized_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty",
        )

    # Rate limiting (Requirement 18.3)
    limiter = get_rate_limiter()
    allowed, rate_info = limiter.check_rate_limit("search", limiter.SEARCH_CONFIG)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please retry after {rate_info.get('retry_after', 60)} seconds.",
        )

    try:
        results = await service.semantic_search(
            query=sanitized_query,
            folder_filter=body.folder_filter,
            limit=body.limit,
            offset=body.offset,
        )
        return _results_to_response(results, sanitized_query, body.folder_filter, SearchType.SEMANTIC)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {exc}",
        ) from exc


@app.post("/search/keyword", response_model=EnhancedSearchResponse)
async def enhanced_keyword_search(
    body: EnhancedSearchRequest,
    service: EnhancedSearchService = Depends(_get_search_service),
) -> EnhancedSearchResponse:
    """
    Keyword (payload text match) search with optional folder filtering.

    Requirement 4.1: natural language / keyword query input.
    """
    try:
        results = await service.keyword_search(
            query=body.query,
            folder_filter=body.folder_filter,
            limit=body.limit,
        )
        return _results_to_response(results, body.query, body.folder_filter, SearchType.KEYWORD)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Keyword search failed: {exc}",
        ) from exc


@app.post("/search/hybrid", response_model=EnhancedSearchResponse)
async def enhanced_hybrid_search(
    body: EnhancedSearchRequest,
    service: EnhancedSearchService = Depends(_get_search_service),
) -> EnhancedSearchResponse:
    """
    Hybrid search combining semantic and keyword strategies.

    The *semantic_weight* parameter (0.0–1.0) controls the balance between
    semantic and keyword scoring (default 0.7 semantic / 0.3 keyword).

    Requirement 4.5: return results from both internal database and external
    sources based on search context.
    """
    try:
        results = await service.hybrid_search(
            query=body.query,
            folder_filter=body.folder_filter,
            limit=body.limit,
            semantic_weight=body.semantic_weight,
        )
        return _results_to_response(results, body.query, body.folder_filter, SearchType.HYBRID)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid search failed: {exc}",
        ) from exc


@app.post("/search/device-context", response_model=EnhancedSearchResponse)
async def device_context_search(
    body: DeviceContextSearchRequest,
    service: EnhancedSearchService = Depends(_get_search_service),
) -> EnhancedSearchResponse:
    """
    Search with device context for enhanced relevance.

    Prepends device information (name, manufacturer, model, category) to the
    query so that the embedding captures device-specific semantics.

    Requirement 12.1: consider device categories and relationships.
    Requirement 12.2: enhance results with related device information.
    Requirement 12.4: support contextual queries like
        "devices similar to [identified device]".
    """
    try:
        results = await service.device_context_search(
            device_info=body.device_info,
            context_query=body.context_query,
            limit=body.limit,
        )
        return _results_to_response(
            results,
            body.context_query,
            None,
            "device_context",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Device context search failed: {exc}",
        ) from exc


@app.get("/search/suggestions", response_model=SearchSuggestionsResponse)
def get_search_suggestions(
    q: str = "",
    limit: int = 5,
    service: EnhancedSearchService = Depends(_get_search_service),
) -> SearchSuggestionsResponse:
    """
    Return query suggestions based on previous searches.

    Requirement 12.5: provide query suggestions based on previous searches.
    """
    suggestions = service.get_search_suggestions(q, limit)
    return SearchSuggestionsResponse(suggestions=suggestions)


@app.get("/search/history", response_model=SearchHistoryResponse)
def get_search_history(
    limit: int = 10,
    service: EnhancedSearchService = Depends(_get_search_service),
) -> SearchHistoryResponse:
    """
    Return recent search history.

    Requirement 12.5: maintain search history.
    """
    history = service.get_search_history(limit)
    return SearchHistoryResponse(history=history)


#
# Content management endpoints (Requirements 6.1-6.5, 7.1-7.5)
#

from .content_management_service import (
    ContentManagementService,
    FileRecord as CMSFileRecord,
    BulkDeleteResult as CMSBulkDeleteResult,
)
from .schemas import (
    FileRecord as FileRecordSchema,
    FileListResponse,
    BulkDeleteRequest,
    BulkDeleteResult as BulkDeleteResultSchema,
)
from fastapi.responses import FileResponse

# Module-level singleton for the content management service
_content_management_service: ContentManagementService | None = None


async def get_content_management_service() -> ContentManagementService:
    """Get or create the ContentManagementService singleton."""
    global _content_management_service
    if _content_management_service is None:
        client = get_qdrant_client()
        folder_svc = await get_folder_service()
        _content_management_service = ContentManagementService(
            qdrant_client=client,
            folder_service=folder_svc,
        )
    return _content_management_service


def _file_record_to_schema(record: CMSFileRecord) -> FileRecordSchema:
    """Convert a CMSFileRecord to the Pydantic FileRecord schema."""
    return FileRecordSchema(
        id=record.id,
        filename=record.filename,
        original_filename=record.original_filename,
        folder_id=record.folder_id,
        file_size=record.file_size,
        content_type=record.content_type,
        upload_date=record.upload_date,
        chunk_count=record.chunk_count,
        status=record.status,
        file_path=record.file_path,
    )


@app.post(
    "/files/upload",
    response_model=FileRecordSchema,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    file: UploadFile = File(...),
    folder_id: str = "",
    service: ContentManagementService = Depends(get_content_management_service),
) -> FileRecordSchema:
    """
    Upload a file and index it in the specified folder.

    Supports PDF, DOC, DOCX, and TXT formats (Requirement 6.1).
    Folder assignment is required (Requirement 6.2).
    Text extraction and embedding generation happen automatically (Requirement 6.3).
    Content is indexed in the folder's Qdrant collection (Requirement 6.4).
    """
    if not folder_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="folder_id is required",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Sanitize folder_id and filename (Requirement 18.1 + 18.4)
    if detect_path_traversal(folder_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid folder_id",
        )
    safe_filename = sanitize_filename(file.filename)
    if not safe_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename",
        )

    # Rate limiting (Requirement 18.3)
    limiter = get_rate_limiter()
    allowed, rate_info = limiter.check_rate_limit("file_upload", limiter.UPLOAD_CONFIG)
    if not allowed:
        log_audit_event(
            AuditAction.FILE_UPLOAD,
            "file",
            resource_id=safe_filename,
            details={"folder_id": folder_id, "rate_limit_info": rate_info},
            success=False,
            error_message="Rate limit exceeded",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please retry after {rate_info.get('retry_after', 60)} seconds.",
        )

    try:
        file_data = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    # Validate file type and scan for malicious content (Requirement 18.2)
    validation_result = validate_and_scan_file(
        file_data, safe_filename, allowed_types=ALLOWED_DOCUMENT_TYPES
    )
    if not validation_result.is_valid:
        log_audit_event(
            AuditAction.FILE_UPLOAD,
            "file",
            resource_id=safe_filename,
            details={"folder_id": folder_id, "validation_error": validation_result.error_message},
            success=False,
            error_message=validation_result.error_message,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_result.error_message,
        )

    try:
        record = await service.upload_file(
            file_data=file_data,
            filename=safe_filename,
            folder_id=folder_id,
            content_type=file.content_type or "application/octet-stream",
        )
    except ValueError as exc:
        log_audit_event(
            AuditAction.FILE_UPLOAD,
            "file",
            resource_id=safe_filename,
            details={"folder_id": folder_id},
            success=False,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        log_audit_event(
            AuditAction.FILE_UPLOAD,
            "file",
            resource_id=safe_filename,
            details={"folder_id": folder_id},
            success=False,
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {exc}",
        ) from exc

    # Audit log successful upload (Requirement 18.5)
    log_audit_event(
        AuditAction.FILE_UPLOAD,
        "file",
        resource_id=record.id,
        details={"folder_id": folder_id, "filename": safe_filename, "file_size": record.file_size},
        success=True,
    )

    return _file_record_to_schema(record)


@app.get("/files", response_model=FileListResponse)
async def list_files(
    folder_id: str | None = None,
    service: ContentManagementService = Depends(get_content_management_service),
) -> FileListResponse:
    """
    List all uploaded files, optionally filtered by folder.

    Requirement 7.1: display files organised by folder structure.
    Requirement 7.2: show file metadata (name, size, upload date, folder).
    """
    records = await service.list_files(folder_id=folder_id)
    return FileListResponse(
        files=[_file_record_to_schema(r) for r in records],
        total=len(records),
    )


@app.get("/files/{file_id}", response_model=FileRecordSchema)
async def get_file(
    file_id: str,
    service: ContentManagementService = Depends(get_content_management_service),
) -> FileRecordSchema:
    """
    Get file metadata by ID.

    Requirement 7.2: show file metadata.
    """
    record = await service.get_file(file_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_id}' not found",
        )
    return _file_record_to_schema(record)


@app.delete("/files/{file_id}", status_code=status.HTTP_200_OK)
async def delete_file(
    file_id: str,
    service: ContentManagementService = Depends(get_content_management_service),
) -> dict[str, str]:
    """
    Delete a file from disk storage and its Qdrant index.

    Requirement 7.3: remove file from both disk and Qdrant index.
    Requirement 7.4: the frontend should confirm before calling this endpoint.
    """
    # Validate file_id (Requirement 18.1)
    try:
        file_id = validate_file_id(file_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    success = await service.delete_file(file_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_id}' not found",
        )

    # Audit log (Requirement 18.5)
    log_audit_event(
        AuditAction.FILE_DELETE,
        "file",
        resource_id=file_id,
        success=True,
    )

    return {"message": f"File '{file_id}' deleted successfully"}


@app.post("/files/bulk-delete", response_model=BulkDeleteResultSchema)
async def bulk_delete_files(
    body: BulkDeleteRequest,
    service: ContentManagementService = Depends(get_content_management_service),
) -> BulkDeleteResultSchema:
    """
    Delete multiple files at once.

    Requirement 7.5: support bulk operations for selecting and deleting multiple files.
    """
    # Validate all file IDs (Requirement 18.1)
    validated_ids: list[str] = []
    for fid in body.file_ids:
        try:
            validated_ids.append(validate_file_id(fid))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file ID '{fid}': {exc}",
            ) from exc

    result = await service.bulk_delete_files(validated_ids)

    # Audit log (Requirement 18.5)
    log_audit_event(
        AuditAction.FILE_BULK_DELETE,
        "file",
        details={
            "requested": len(validated_ids),
            "deleted": len(result.deleted),
            "failed": len(result.failed),
        },
        success=len(result.failed) == 0,
    )

    return BulkDeleteResultSchema(
        deleted=result.deleted,
        failed=result.failed,
        errors=result.errors,
        deleted_count=len(result.deleted),
        failed_count=len(result.failed),
    )


@app.get("/files/{file_id}/download")
async def download_file(
    file_id: str,
    service: ContentManagementService = Depends(get_content_management_service),
) -> FileResponse:
    """
    Download the original uploaded file.

    Returns the file as a binary download with the original filename.
    """
    record = await service.get_file(file_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File '{file_id}' not found",
        )

    file_path = Path(record.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File data for '{file_id}' not found on disk",
        )

    return FileResponse(
        path=str(file_path),
        filename=record.original_filename,
        media_type=record.content_type,
    )


#
# User Area endpoints (Requirements 8.1-8.5)
#

from .user_area_service import UserAreaService, SavedItem, get_user_area_service
from fastapi import Body, Query
from fastapi.responses import Response


def _saved_item_to_dict(item: SavedItem) -> dict[str, Any]:
    return item.to_dict()


@app.post("/user/saved", status_code=status.HTTP_201_CREATED)
def save_content_item(
    body: dict[str, Any] = Body(...),
    service: UserAreaService = Depends(get_user_area_service),
) -> dict[str, Any]:
    """
    Save a content item to the user area.

    Body fields:
    - title (required)
    - content (required)
    - content_id (optional, used as item ID)
    - source (optional)
    - notes (optional)
    - tags (optional list of strings)
    - folder_path (optional, default "")

    Requirement 8.1: save functionality for search results and database content.
    Requirement 8.2: allow users to organize items into personal folder structures.
    Requirement 8.3: maintain user-specific saved content collections.
    """
    title = body.get("title", "").strip()
    content = body.get("content", "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'title' is required",
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'content' is required",
        )

    item = service.create(
        title=title,
        content=content,
        source=body.get("source", ""),
        notes=body.get("notes", ""),
        tags=body.get("tags", []),
        folder_path=body.get("folder_path", ""),
        content_id=body.get("content_id"),
    )
    return _saved_item_to_dict(item)


@app.get("/user/saved")
def list_saved_items(
    search: str = Query(default="", description="Search within saved items"),
    folder_path: str | None = Query(default=None, description="Filter by folder path"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service: UserAreaService = Depends(get_user_area_service),
) -> dict[str, Any]:
    """
    List saved items with optional search and folder filtering.

    Requirement 8.4: quick search and filtering within saved items.
    """
    items, total = service.list_items(
        search=search,
        folder_path=folder_path,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [_saved_item_to_dict(i) for i in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/user/saved/folders")
def list_user_folders(
    service: UserAreaService = Depends(get_user_area_service),
) -> dict[str, Any]:
    """
    List all personal folder paths currently in use.

    Requirement 8.2: personal folder organization system.
    """
    folders = service.list_folders()
    return {"folders": folders}


@app.get("/user/saved/export")
def export_saved_items(
    format: str = Query(default="json", description="Export format: 'json' or 'pdf'"),
    service: UserAreaService = Depends(get_user_area_service),
) -> Response:
    """
    Export all saved items.

    - format=json  → application/json download
    - format=pdf   → PDF download (falls back to plain text if reportlab is unavailable)

    Requirement 8.5: export functionality for saved content in PDF and JSON formats.
    """
    if format == "json":
        data = service.export_json()
        return Response(
            content=data,
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=area_personale.json"
            },
        )
    elif format == "pdf":
        pdf_bytes = service.export_pdf()
        if pdf_bytes is not None:
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": "attachment; filename=area_personale.pdf"
                },
            )
        else:
            # Fallback: plain text
            text = service.export_text()
            return Response(
                content=text.encode("utf-8"),
                media_type="text/plain; charset=utf-8",
                headers={
                    "Content-Disposition": "attachment; filename=area_personale.txt"
                },
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported export format '{format}'. Use 'json' or 'pdf'.",
        )


@app.get("/user/saved/{item_id}")
def get_saved_item(
    item_id: str,
    service: UserAreaService = Depends(get_user_area_service),
) -> dict[str, Any]:
    """Get a single saved item by ID."""
    item = service.get(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved item '{item_id}' not found",
        )
    return _saved_item_to_dict(item)


@app.put("/user/saved/{item_id}")
def update_saved_item(
    item_id: str,
    body: dict[str, Any] = Body(...),
    service: UserAreaService = Depends(get_user_area_service),
) -> dict[str, Any]:
    """
    Update notes, tags, folder_path, or title of a saved item.

    Requirement 8.2: organize items into personal folder structures.
    """
    item = service.update(
        item_id=item_id,
        notes=body.get("notes"),
        tags=body.get("tags"),
        folder_path=body.get("folder_path"),
        title=body.get("title"),
    )
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved item '{item_id}' not found",
        )
    return _saved_item_to_dict(item)


@app.delete("/user/saved/{item_id}", status_code=status.HTTP_200_OK)
def delete_saved_item(
    item_id: str,
    service: UserAreaService = Depends(get_user_area_service),
) -> dict[str, str]:
    """Delete a saved item by ID."""
    deleted = service.delete(item_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saved item '{item_id}' not found",
        )
    return {"message": f"Item '{item_id}' deleted successfully"}


#
# Performance optimization endpoints (Requirements 14.1-14.5)
#

from .search_cache import SearchCache, get_search_cache
from .content_cache import ContentCache, get_content_cache
from .performance_tracker import PerformanceTracker, get_performance_tracker, timed_search


def _get_search_cache() -> SearchCache:
    return get_search_cache()


def _get_content_cache() -> ContentCache:
    return get_content_cache()


def _get_perf_tracker() -> PerformanceTracker:
    return get_performance_tracker()


@app.get("/performance/stats")
def get_performance_stats(
    search_cache: SearchCache = Depends(_get_search_cache),
    content_cache: ContentCache = Depends(_get_content_cache),
    tracker: PerformanceTracker = Depends(_get_perf_tracker),
) -> dict[str, Any]:
    """
    Return aggregate performance statistics.

    Includes:
    - Cache hit rate for search and content caches
    - Average search response time (rolling window)
    - Total cached entries across both caches

    Requirement 14.4: caching strategies visibility.
    """
    search_stats = search_cache.get_stats()
    content_stats = content_cache.get_stats()
    perf_stats = tracker.get_stats()

    total_cached = search_stats["size"] + content_stats["size"]

    return {
        "search_cache": search_stats,
        "content_cache": content_stats,
        "response_times": perf_stats,
        "summary": {
            "total_cached_entries": total_cached,
            "search_cache_hit_rate": search_stats["hit_rate"],
            "content_cache_hit_rate": content_stats["hit_rate"],
            "average_search_response_ms": perf_stats["average_response_ms"],
        },
    }


@app.post("/search/record-interaction")
def record_search_interaction(
    body: dict[str, Any],
    service: EnhancedSearchService = Depends(_get_search_service),
) -> dict[str, str]:
    """
    Record that the user interacted with (clicked or saved) a search result.

    Body: {"result_id": "<id>"}

    Subsequent searches will apply a small relevance boost to this result.

    Requirement 14.5: ranking based on user interaction patterns.
    """
    result_id = body.get("result_id", "").strip()
    if not result_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'result_id' is required",
        )
    service.record_interaction(result_id)
    return {"message": f"Interaction recorded for result '{result_id}'"}


@app.post("/performance/cache/invalidate-search")
def invalidate_search_cache(
    cache: SearchCache = Depends(_get_search_cache),
) -> dict[str, str]:
    """
    Manually invalidate the entire search cache.

    This is called automatically when new content is indexed, but can also
    be triggered manually for testing or maintenance.
    """
    cache.invalidate_all()
    return {"message": "Search cache cleared"}


@app.post("/performance/cache/invalidate-content")
def invalidate_content_cache(
    folder_id: str | None = None,
    cache: ContentCache = Depends(_get_content_cache),
) -> dict[str, str]:
    """
    Invalidate content cache for a specific folder or all folders.

    Requirement 14.4: cache invalidation on content changes.
    """
    if folder_id:
        cache.invalidate_folder(folder_id)
        return {"message": f"Content cache cleared for folder '{folder_id}'"}
    cache.invalidate_all()
    return {"message": "Content cache fully cleared"}
