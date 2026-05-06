"""
Folder system data models for hierarchical content organization.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Supported content types within folders."""
    
    DEVICE_DOCUMENTATION = "device_documentation"
    PDF_DOCUMENTS = "pdf_documents"
    NOTES = "notes"
    SCHOOL_MATERIALS = "school_materials"
    USER_CONTENT = "user_content"


class DeviceCategory(str, Enum):
    """Device categorization for organization."""
    
    ELECTRONICS = "electronics"
    APPLIANCES = "appliances"
    TOOLS = "tools"
    MEDICAL = "medical"
    AUTOMOTIVE = "automotive"
    OTHER = "other"


class SourceType(str, Enum):
    """Content source types."""
    
    INTERNAL_DATABASE = "internal_database"
    MANUFACTURER_WEBSITE = "manufacturer_website"
    DOCUMENTATION_PORTAL = "documentation_portal"
    VIDEO_PLATFORM = "video_platform"
    USER_UPLOAD = "user_upload"


class FolderDefinition(BaseModel):
    """Definition for creating a new folder."""
    
    name: str = Field(min_length=1, max_length=100, description="Folder name")
    description: Optional[str] = Field(None, max_length=500, description="Folder description")
    parent_id: Optional[str] = Field(None, description="Parent folder ID for nested structure")
    content_types: List[ContentType] = Field(description="Supported content types in this folder")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional folder metadata")


class Folder(BaseModel):
    """Hierarchical folder structure for content organization."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique folder identifier")
    name: str = Field(description="Folder name")
    description: Optional[str] = Field(None, description="Folder description")
    parent_id: Optional[str] = Field(None, description="Parent folder ID")
    path: str = Field(description="Full hierarchical path")
    content_types: List[ContentType] = Field(description="Supported content types")
    qdrant_collection: str = Field(description="Associated Qdrant collection name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_count: int = Field(default=0, description="Number of documents in folder")


class ContentSummary(BaseModel):
    """Summary of content within a folder."""
    
    total_documents: int = Field(default=0)
    content_type_counts: Dict[ContentType, int] = Field(default_factory=dict)
    last_updated: Optional[datetime] = None
    size_bytes: int = Field(default=0)


class FolderTree(BaseModel):
    """Hierarchical folder representation."""
    
    folder: Folder
    children: List['FolderTree'] = Field(default_factory=list)
    content_summary: ContentSummary = Field(default_factory=ContentSummary)


class DeviceIdentifier(BaseModel):
    """Device identification methods."""
    
    type: str = Field(description="Identifier type (qr_code, barcode, model_number, etc.)")
    value: str = Field(description="Identifier value")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence level")
    source: str = Field(description="Source of identification")


class DeviceInfo(BaseModel):
    """Comprehensive device information structure."""
    
    device_id: str = Field(description="Unique device identifier")
    name: str = Field(description="Device name")
    manufacturer: str = Field(description="Device manufacturer")
    model: str = Field(description="Device model")
    category: DeviceCategory = Field(description="Device category")
    specifications: Dict[str, Any] = Field(default_factory=dict, description="Device specifications")
    identifiers: List[DeviceIdentifier] = Field(default_factory=list, description="Device identifiers")
    documentation_sources: List[str] = Field(default_factory=list, description="Documentation source URLs")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DocumentMetadata(BaseModel):
    """Extended metadata for documents."""
    
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    language: str = Field(default="en")
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    extraction_method: str = Field(default="automatic")


class ContentSource(BaseModel):
    """Content source tracking."""
    
    type: SourceType
    url: Optional[str] = None
    api_endpoint: Optional[str] = None
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reliability_score: float = Field(default=1.0, ge=0.0, le=1.0)


class Document(BaseModel):
    """Enhanced document model with folder assignment."""
    
    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique document identifier")
    title: str = Field(description="Document title")
    content: str = Field(description="Document content")
    content_type: ContentType = Field(description="Content type")
    folder_id: str = Field(description="Assigned folder ID")
    device_associations: List[str] = Field(default_factory=list, description="Associated device IDs")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    indexed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: ContentSource


class SavedContent(BaseModel):
    """User-saved content organization."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(description="User identifier for future user system integration")
    content_id: str = Field(description="Reference to original content")
    folder_path: str = Field(description="User's folder organization path")
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    saved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserFolder(BaseModel):
    """User-specific folder organization."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = Field(description="User identifier")
    name: str = Field(description="User folder name")
    parent_id: Optional[str] = None
    content_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Update FolderTree to handle forward references
FolderTree.model_rebuild()