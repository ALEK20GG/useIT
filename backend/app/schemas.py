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


# ---- Folder management models ----


class CreateFolderRequest(BaseModel):
    """Request to create a new folder."""
    
    name: str = Field(min_length=1, max_length=100, description="Folder name")
    description: str | None = Field(None, max_length=500, description="Folder description")
    parent_id: str | None = Field(None, description="Parent folder ID for nested structure")
    content_types: list[str] = Field(description="Supported content types in this folder")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional folder metadata")


class FolderResponse(BaseModel):
    """Response model for folder information."""
    
    id: str
    name: str
    description: str | None = None
    parent_id: str | None = None
    path: str
    content_types: list[str]
    qdrant_collection: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    content_count: int


class FolderListResponse(BaseModel):
    """Response model for folder listing."""
    
    folders: list[FolderResponse]
    total: int


class UpdateFolderRequest(BaseModel):
    """Request to update folder metadata."""
    
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    metadata: dict[str, Any] | None = None


class AssignContentRequest(BaseModel):
    """Request to assign content to a folder."""
    
    content_id: str = Field(description="Content identifier")
    folder_id: str = Field(description="Target folder identifier")


class MoveContentRequest(BaseModel):
    """Request to move content between folders."""
    
    content_id: str = Field(description="Content identifier")
    from_folder_id: str = Field(description="Source folder identifier")
    to_folder_id: str = Field(description="Destination folder identifier")


# ---- Device recognition models ----


class DeviceRecognitionResponse(BaseModel):
    """Response from device photo recognition endpoint."""

    device_id: str | None = Field(None, description="Unique device identifier")
    device_name: str | None = Field(None, description="Recognized device name")
    manufacturer: str | None = Field(None, description="Device manufacturer")
    model: str | None = Field(None, description="Device model")
    confidence: float = Field(description="Recognition confidence score (0.0–1.0)")
    alternative_matches: list[dict] = Field(
        default_factory=list, description="Alternative device matches"
    )
    processing_time_ms: float = Field(default=0.0, description="Processing time in milliseconds")
    error_message: str | None = Field(None, description="Error message if recognition failed")
    is_mock: bool = Field(default=True, description="Whether mock AI service was used")


class QRCodeResponse(BaseModel):
    """Response from QR code decoding endpoint."""

    content: str = Field(description="Decoded QR code content")
    format: str = Field(description="QR code format")
    confidence: float = Field(description="Detection confidence (0.0–1.0)")
    bounding_box: tuple[int, int, int, int] | None = Field(
        None, description="Bounding box coordinates (x1, y1, x2, y2)"
    )
    is_mock: bool = Field(default=True, description="Whether mock AI service was used")


class AIServiceInfoResponse(BaseModel):
    """Response with AI service status and configuration."""

    model_config = {"protected_namespaces": ()}  # Allow model_* field names

    service_type: str = Field(description="AI service implementation class name")
    is_mock: bool = Field(description="Whether mock service is active")
    initialized: bool = Field(description="Whether service is initialized")
    model_name: str = Field(description="Model name")
    model_type: str = Field(description="Model format type")
    model_version: str = Field(description="Model version")
    supported_devices: list[str] = Field(description="Supported device categories")
    qr_detection_enabled: bool = Field(description="QR detection enabled")
    confidence_threshold: float = Field(description="Minimum confidence threshold")
    max_concurrent_requests: int = Field(description="Maximum concurrent requests")


# ---- Device database models ----


class DeviceCreate(BaseModel):
    """Request body for creating a new device in the database."""

    name: str = Field(min_length=1, description="Human-readable device name")
    manufacturer: str = Field(min_length=1, description="Device manufacturer")
    model: str = Field(min_length=1, description="Device model number/name")
    category: str = Field(default="other", description="Device category")
    specifications: dict[str, Any] = Field(
        default_factory=dict, description="Technical specifications"
    )
    qr_codes: list[str] = Field(
        default_factory=list, description="Associated QR code values"
    )
    documentation_urls: list[str] = Field(
        default_factory=list, description="Links to documentation"
    )


class DeviceUpdate(BaseModel):
    """Request body for updating an existing device (all fields optional)."""

    name: str | None = Field(None, min_length=1, description="Human-readable device name")
    manufacturer: str | None = Field(None, min_length=1, description="Device manufacturer")
    model: str | None = Field(None, min_length=1, description="Device model number/name")
    category: str | None = Field(None, description="Device category")
    specifications: dict[str, Any] | None = Field(None, description="Technical specifications")
    qr_codes: list[str] | None = Field(None, description="Associated QR code values")
    documentation_urls: list[str] | None = Field(None, description="Links to documentation")


class DeviceResponse(BaseModel):
    """Response model for a single device record."""

    id: str = Field(description="Unique device identifier")
    name: str = Field(description="Human-readable device name")
    manufacturer: str = Field(description="Device manufacturer")
    model: str = Field(description="Device model number/name")
    category: str = Field(description="Device category")
    specifications: dict[str, Any] = Field(description="Technical specifications")
    qr_codes: list[str] = Field(description="Associated QR code values")
    documentation_urls: list[str] = Field(description="Links to documentation")
    created_at: str = Field(description="ISO-8601 creation timestamp")
    updated_at: str = Field(description="ISO-8601 last-update timestamp")


class DeviceListResponse(BaseModel):
    """Response model for listing devices."""

    devices: list[DeviceResponse]
    total: int = Field(description="Total number of devices")


class RecognizeAndLookupResponse(BaseModel):
    """Response from the recognize-and-lookup endpoint."""

    recognition: DeviceRecognitionResponse = Field(
        description="AI recognition result"
    )
    database_match: DeviceResponse | None = Field(
        None, description="Matching device from the local database (if found)"
    )
    documentation_urls: list[str] = Field(
        default_factory=list,
        description="Documentation URLs from the database match",
    )


class QRCodeWithDocumentationResponse(BaseModel):
    """Extended QR code response that includes documentation lookup (Req 2.3)."""

    content: str = Field(description="Decoded QR code content")
    format: str = Field(description="QR code format")
    confidence: float = Field(description="Detection confidence (0.0–1.0)")
    bounding_box: tuple[int, int, int, int] | None = Field(
        None, description="Bounding box coordinates (x1, y1, x2, y2)"
    )
    is_mock: bool = Field(default=True, description="Whether mock AI service was used")
    device_match: DeviceResponse | None = Field(
        None, description="Device found in database matching this QR code"
    )
    documentation_urls: list[str] = Field(
        default_factory=list,
        description="Documentation URLs retrieved from the database match",
    )


# ---- Enhanced search models (Requirements 4.1-4.5, 12.1-12.5) ----


class EnhancedSearchRequest(BaseModel):
    """Request body for enhanced search endpoints."""

    query: str = Field(min_length=1, description="Natural language search query")
    folder_filter: list[str] | None = Field(
        default=None,
        description="Optional list of Qdrant collection names to restrict search to",
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results to return")
    offset: int = Field(default=0, ge=0, description="Number of results to skip")
    search_type: str = Field(
        default="semantic",
        description="Search strategy: 'semantic', 'keyword', or 'hybrid'",
    )
    semantic_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Weight for semantic component in hybrid search (0.0–1.0)",
    )


class EnhancedSearchResult(BaseModel):
    """A single result returned by the enhanced search service."""

    id: str = Field(description="Unique result identifier")
    title: str = Field(description="Result title or filename")
    content: str = Field(description="Matching content excerpt")
    score: float = Field(description="Relevance score")
    folder_id: str | None = Field(None, description="Folder the result belongs to")
    source: str = Field(default="qdrant", description="Data source identifier")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional result metadata"
    )


class EnhancedSearchResponse(BaseModel):
    """Response wrapper for enhanced search endpoints."""

    results: list[EnhancedSearchResult]
    total: int = Field(description="Total number of results returned")
    query: str = Field(description="Original search query")
    folder_filter: list[str] | None = Field(
        None, description="Applied folder filter (if any)"
    )
    search_type: str = Field(description="Search strategy used")


class DeviceContextSearchRequest(BaseModel):
    """Request body for device-context search."""

    device_info: dict[str, Any] = Field(
        description="Device information dict (name, manufacturer, model, category, …)"
    )
    context_query: str = Field(
        min_length=1, description="Contextual query to run alongside device info"
    )
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results to return")


class SearchSuggestionsResponse(BaseModel):
    """Response for search suggestion endpoint."""

    suggestions: list[str] = Field(description="List of query suggestions")


class SearchHistoryResponse(BaseModel):
    """Response for search history endpoint."""

    history: list[dict[str, Any]] = Field(description="Recent search history entries")


# ---- Content management models (Requirements 6.1-6.5, 7.1-7.5) ----


class FileRecord(BaseModel):
    """Metadata for an uploaded file."""

    id: str = Field(description="Unique file identifier")
    filename: str = Field(description="Stored filename (UUID-based)")
    original_filename: str = Field(description="Original filename as uploaded")
    folder_id: str = Field(description="Folder the file belongs to")
    file_size: int = Field(description="File size in bytes")
    content_type: str = Field(description="MIME content type")
    upload_date: str = Field(description="ISO-8601 upload timestamp")
    chunk_count: int = Field(description="Number of indexed chunks")
    status: str = Field(description="Processing status: processing | indexed | failed")
    file_path: str = Field(description="Absolute path to the stored file")


class FileListResponse(BaseModel):
    """Response model for listing files."""

    files: list[FileRecord]
    total: int = Field(description="Total number of files")


class BulkDeleteRequest(BaseModel):
    """Request body for bulk file deletion."""

    file_ids: list[str] = Field(min_length=1, description="List of file IDs to delete")


class BulkDeleteResult(BaseModel):
    """Result of a bulk delete operation."""

    deleted: list[str] = Field(description="Successfully deleted file IDs")
    failed: list[str] = Field(description="File IDs that could not be deleted")
    errors: dict[str, str] = Field(
        default_factory=dict, description="Error messages keyed by file ID"
    )
    deleted_count: int = Field(description="Number of successfully deleted files")
    failed_count: int = Field(description="Number of files that failed to delete")
