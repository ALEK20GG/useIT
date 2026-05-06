"""
Qdrant collection configuration for folder-based organization.
"""

from typing import Dict, Any
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
from .folder_models import ContentType


class QdrantCollectionConfig:
    """Configuration for Qdrant collections by folder."""
    
    # Default vector size based on the embedding model (sentence-transformers/all-MiniLM-L6-v2)
    DEFAULT_VECTOR_SIZE = 384
    DEFAULT_DISTANCE = Distance.COSINE
    
    # Collection configurations for default folders
    COLLECTION_CONFIGS = {
        "dispositivi": {
            "vector_size": DEFAULT_VECTOR_SIZE,
            "distance": DEFAULT_DISTANCE,
            "payload_schema": {
                "device_id": PayloadSchemaType.KEYWORD,
                "manufacturer": PayloadSchemaType.KEYWORD,
                "category": PayloadSchemaType.KEYWORD,
                "content_type": PayloadSchemaType.KEYWORD,
                "folder_id": PayloadSchemaType.KEYWORD,
                "filename": PayloadSchemaType.KEYWORD,
                "tags": PayloadSchemaType.KEYWORD,
                "indexed_at": PayloadSchemaType.DATETIME,
            }
        },
        "appunti": {
            "vector_size": DEFAULT_VECTOR_SIZE,
            "distance": DEFAULT_DISTANCE,
            "payload_schema": {
                "note_type": PayloadSchemaType.KEYWORD,
                "tags": PayloadSchemaType.KEYWORD,
                "created_by": PayloadSchemaType.KEYWORD,
                "content_type": PayloadSchemaType.KEYWORD,
                "folder_id": PayloadSchemaType.KEYWORD,
                "indexed_at": PayloadSchemaType.DATETIME,
            }
        },
        "scuola": {
            "vector_size": DEFAULT_VECTOR_SIZE,
            "distance": DEFAULT_DISTANCE,
            "payload_schema": {
                "subject": PayloadSchemaType.KEYWORD,
                "grade_level": PayloadSchemaType.KEYWORD,
                "content_format": PayloadSchemaType.KEYWORD,
                "content_type": PayloadSchemaType.KEYWORD,
                "folder_id": PayloadSchemaType.KEYWORD,
                "tags": PayloadSchemaType.KEYWORD,
                "indexed_at": PayloadSchemaType.DATETIME,
            }
        }
    }
    
    @classmethod
    def get_collection_config(cls, collection_name: str) -> Dict[str, Any]:
        """Get configuration for a specific collection."""
        return cls.COLLECTION_CONFIGS.get(collection_name, {
            "vector_size": cls.DEFAULT_VECTOR_SIZE,
            "distance": cls.DEFAULT_DISTANCE,
            "payload_schema": {
                "content_type": PayloadSchemaType.KEYWORD,
                "folder_id": PayloadSchemaType.KEYWORD,
                "tags": PayloadSchemaType.KEYWORD,
                "indexed_at": PayloadSchemaType.DATETIME,
            }
        })
    
    @classmethod
    def create_vector_params(cls, collection_name: str) -> VectorParams:
        """Create VectorParams for a collection."""
        config = cls.get_collection_config(collection_name)
        return VectorParams(
            size=config["vector_size"],
            distance=config["distance"]
        )
    
    @classmethod
    def get_payload_schema(cls, collection_name: str) -> Dict[str, PayloadSchemaType]:
        """Get payload schema for a collection."""
        config = cls.get_collection_config(collection_name)
        return config.get("payload_schema", {})


class DefaultFolderConfig:
    """Configuration for default folder structure."""
    
    DEFAULT_FOLDERS = {
        "dispositivi": {
            "name": "Dispositivi",
            "description": "Device documentation and manuals",
            "content_types": [ContentType.DEVICE_DOCUMENTATION, ContentType.PDF_DOCUMENTS],
            "collection_name": "dispositivi",
            "metadata": {
                "is_default": True,
                "icon": "device",
                "color": "#2563eb"
            }
        },
        "appunti": {
            "name": "Appunti",
            "description": "Personal notes and documentation",
            "content_types": [ContentType.NOTES, ContentType.USER_CONTENT],
            "collection_name": "appunti",
            "metadata": {
                "is_default": True,
                "icon": "note",
                "color": "#059669"
            }
        },
        "scuola": {
            "name": "Scuola",
            "description": "Educational materials and school content",
            "content_types": [ContentType.SCHOOL_MATERIALS, ContentType.PDF_DOCUMENTS],
            "collection_name": "scuola",
            "metadata": {
                "is_default": True,
                "icon": "school",
                "color": "#dc2626"
            }
        }
    }
    
    @classmethod
    def get_default_folder_config(cls, folder_key: str) -> Dict[str, Any]:
        """Get configuration for a default folder."""
        return cls.DEFAULT_FOLDERS.get(folder_key, {})
    
    @classmethod
    def get_all_default_folders(cls) -> Dict[str, Dict[str, Any]]:
        """Get all default folder configurations."""
        return cls.DEFAULT_FOLDERS.copy()


def generate_collection_name(folder_name: str, folder_id: str) -> str:
    """Generate a unique collection name for a folder."""
    # Normalize folder name for collection naming
    normalized_name = folder_name.lower().replace(" ", "_").replace("-", "_")
    # Remove special characters and limit length
    normalized_name = "".join(c for c in normalized_name if c.isalnum() or c == "_")[:20]
    
    # For default folders, use predefined names
    if normalized_name in DefaultFolderConfig.DEFAULT_FOLDERS:
        return normalized_name
    
    # For custom folders, append folder ID to ensure uniqueness
    return f"{normalized_name}_{folder_id[:8]}"


def validate_collection_name(collection_name: str) -> bool:
    """Validate that a collection name meets Qdrant requirements."""
    # Qdrant collection names must be alphanumeric with underscores
    if not collection_name:
        return False
    
    # Check length (Qdrant has limits)
    if len(collection_name) > 64:
        return False
    
    # Check characters
    allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789_")
    return all(c in allowed_chars for c in collection_name.lower())