"""
Folder management service with CRUD operations and Qdrant integration.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, VectorParams, Distance
from fastapi import HTTPException, status

from .folder_models import (
    Folder, FolderDefinition, FolderTree, ContentSummary, 
    Document, ContentType, DeviceInfo
)
from .qdrant_config import (
    QdrantCollectionConfig, DefaultFolderConfig, 
    generate_collection_name, validate_collection_name
)
from .embeddings import embed_text_batch

logger = logging.getLogger(__name__)


class ConfigStore:
    """Simple file-based configuration store for folder metadata."""
    
    def __init__(self, config_dir: str = "backend/storage/folders"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.folders_file = self.config_dir / "folders.json"
    
    async def save_folder(self, folder: Folder) -> None:
        """Save folder configuration to disk."""
        folders = await self.get_all_folders()
        folders[folder.id] = folder.model_dump()
        
        with open(self.folders_file, 'w', encoding='utf-8') as f:
            json.dump(folders, f, indent=2, default=str)
    
    async def get_folder(self, folder_id: str) -> Optional[Folder]:
        """Get folder configuration by ID."""
        folders = await self.get_all_folders()
        folder_data = folders.get(folder_id)
        
        if folder_data:
            return Folder(**folder_data)
        return None
    
    async def get_all_folders(self) -> Dict[str, Any]:
        """Get all folder configurations."""
        if not self.folders_file.exists():
            return {}
        
        try:
            with open(self.folders_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    async def delete_folder(self, folder_id: str) -> bool:
        """Delete folder configuration."""
        folders = await self.get_all_folders()
        if folder_id in folders:
            del folders[folder_id]
            
            with open(self.folders_file, 'w', encoding='utf-8') as f:
                json.dump(folders, f, indent=2, default=str)
            return True
        return False


class FolderService:
    """Manages folder hierarchy and content organization."""
    
    def __init__(self, qdrant_client: QdrantClient, config_store: Optional[ConfigStore] = None):
        self.qdrant_client = qdrant_client
        self.config_store = config_store or ConfigStore()
        self.folder_cache: Dict[str, Folder] = {}
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the folder service and create default folders."""
        if self._initialized:
            return
        
        logger.info("Initializing folder service...")
        
        # Create default folders if they don't exist
        await self._ensure_default_folders()
        
        # Load existing folders into cache
        await self._load_folder_cache()
        
        self._initialized = True
        logger.info("Folder service initialized successfully")
    
    async def _ensure_default_folders(self) -> None:
        """Ensure default folders exist."""
        existing_folders = await self.config_store.get_all_folders()
        
        for folder_key, config in DefaultFolderConfig.get_all_default_folders().items():
            # Check if default folder already exists
            folder_exists = any(
                folder_data.get("metadata", {}).get("is_default") and 
                folder_data.get("name") == config["name"]
                for folder_data in existing_folders.values()
            )
            
            if not folder_exists:
                logger.info(f"Creating default folder: {config['name']}")
                
                folder_def = FolderDefinition(
                    name=config["name"],
                    description=config["description"],
                    content_types=config["content_types"],
                    metadata=config["metadata"]
                )
                
                await self.create_folder(folder_def, collection_name=config["collection_name"])
    
    async def _load_folder_cache(self) -> None:
        """Load all folders into cache."""
        folders_data = await self.config_store.get_all_folders()
        
        for folder_id, folder_data in folders_data.items():
            try:
                folder = Folder(**folder_data)
                self.folder_cache[folder_id] = folder
            except Exception as e:
                logger.error(f"Failed to load folder {folder_id}: {e}")
    
    def _generate_folder_id(self, name: str) -> str:
        """Generate a unique folder ID."""
        return str(uuid4())
    
    def _build_folder_path(self, folder_def: FolderDefinition, parent_folder: Optional[Folder] = None) -> str:
        """Build hierarchical folder path."""
        if parent_folder:
            return f"{parent_folder.path}/{folder_def.name}"
        return f"/{folder_def.name}"
    
    async def _create_qdrant_collection(self, collection_name: str, content_types: List[ContentType]) -> None:
        """Create Qdrant collection for folder."""
        if not validate_collection_name(collection_name):
            raise ValueError(f"Invalid collection name: {collection_name}")
        
        try:
            # Check if collection already exists
            try:
                existing_collection = self.qdrant_client.get_collection(collection_name)
                logger.info(f"Collection {collection_name} already exists")
                return
            except Exception:
                # Collection doesn't exist, create it
                pass
            
            # Create collection with appropriate configuration
            vector_params = QdrantCollectionConfig.create_vector_params(collection_name)
            
            self.qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=vector_params
            )
            
            logger.info(f"Created Qdrant collection: {collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to create Qdrant collection {collection_name}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create collection: {str(e)}"
            )
    
    async def create_folder(
        self, 
        folder_def: FolderDefinition, 
        collection_name: Optional[str] = None
    ) -> Folder:
        """Create new folder with corresponding Qdrant collection."""
        
        # Validate folder hierarchy depth (max 3 levels)
        if folder_def.parent_id:
            parent_folder = await self.get_folder(folder_def.parent_id)
            if not parent_folder:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Parent folder {folder_def.parent_id} not found"
                )
            
            # Count hierarchy depth
            depth = parent_folder.path.count('/') 
            if depth >= 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum folder hierarchy depth (3 levels) exceeded"
                )
        
        # Generate folder ID and collection name
        folder_id = self._generate_folder_id(folder_def.name)
        
        if collection_name is None:
            collection_name = generate_collection_name(folder_def.name, folder_id)
        
        # Create Qdrant collection
        await self._create_qdrant_collection(collection_name, folder_def.content_types)
        
        # Build folder path
        parent_folder = None
        if folder_def.parent_id:
            parent_folder = await self.get_folder(folder_def.parent_id)
        
        folder_path = self._build_folder_path(folder_def, parent_folder)
        
        # Create folder metadata
        folder = Folder(
            id=folder_id,
            name=folder_def.name,
            description=folder_def.description,
            parent_id=folder_def.parent_id,
            path=folder_path,
            content_types=folder_def.content_types,
            qdrant_collection=collection_name,
            metadata=folder_def.metadata,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            content_count=0
        )
        
        # Store folder configuration
        await self.config_store.save_folder(folder)
        self.folder_cache[folder_id] = folder
        
        logger.info(f"Created folder: {folder.name} (ID: {folder_id})")
        return folder
    
    async def get_folder(self, folder_id: str) -> Optional[Folder]:
        """Get folder by ID."""
        if folder_id in self.folder_cache:
            return self.folder_cache[folder_id]
        
        folder = await self.config_store.get_folder(folder_id)
        if folder:
            self.folder_cache[folder_id] = folder
        
        return folder
    
    async def get_folder_by_name(self, name: str) -> Optional[Folder]:
        """Get folder by name."""
        for folder in self.folder_cache.values():
            if folder.name == name:
                return folder
        
        # If not in cache, load from storage
        folders_data = await self.config_store.get_all_folders()
        for folder_data in folders_data.values():
            if folder_data.get("name") == name:
                return Folder(**folder_data)
        
        return None
    
    async def list_folders(self) -> List[Folder]:
        """List all folders."""
        if not self.folder_cache:
            await self._load_folder_cache()
        
        return list(self.folder_cache.values())
    
    async def update_folder(self, folder_id: str, updates: Dict[str, Any]) -> Optional[Folder]:
        """Update folder metadata."""
        folder = await self.get_folder(folder_id)
        if not folder:
            return None
        
        # Update allowed fields
        allowed_fields = {"name", "description", "metadata"}
        for field, value in updates.items():
            if field in allowed_fields:
                setattr(folder, field, value)
        
        folder.updated_at = datetime.now(timezone.utc)
        
        # Save updated folder
        await self.config_store.save_folder(folder)
        self.folder_cache[folder_id] = folder
        
        return folder
    
    async def delete_folder(self, folder_id: str, force: bool = False) -> bool:
        """Delete folder and its Qdrant collection."""
        folder = await self.get_folder(folder_id)
        if not folder:
            return False
        
        # Check if folder has content (unless force delete)
        if not force and folder.content_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete folder with content. Use force=true to override."
            )
        
        # Check if folder has children
        children = await self._get_folder_children(folder_id)
        if children and not force:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete folder with subfolders. Use force=true to override."
            )
        
        try:
            # Delete Qdrant collection
            self.qdrant_client.delete_collection(folder.qdrant_collection)
            logger.info(f"Deleted Qdrant collection: {folder.qdrant_collection}")
        except Exception as e:
            logger.warning(f"Failed to delete Qdrant collection {folder.qdrant_collection}: {e}")
        
        # Delete from storage and cache
        await self.config_store.delete_folder(folder_id)
        if folder_id in self.folder_cache:
            del self.folder_cache[folder_id]
        
        logger.info(f"Deleted folder: {folder.name} (ID: {folder_id})")
        return True
    
    async def _get_folder_children(self, folder_id: str) -> List[Folder]:
        """Get direct children of a folder."""
        children = []
        for folder in self.folder_cache.values():
            if folder.parent_id == folder_id:
                children.append(folder)
        return children
    
    async def get_folder_hierarchy(self) -> List[FolderTree]:
        """Build complete folder hierarchy tree."""
        if not self.folder_cache:
            await self._load_folder_cache()
        
        # Get root folders (no parent)
        root_folders = [f for f in self.folder_cache.values() if f.parent_id is None]
        
        # Build tree for each root folder
        folder_trees = []
        for root_folder in root_folders:
            tree = await self._build_folder_tree(root_folder)
            folder_trees.append(tree)
        
        return folder_trees
    
    async def _build_folder_tree(self, folder: Folder) -> FolderTree:
        """Build folder tree recursively."""
        children = await self._get_folder_children(folder.id)
        child_trees = []
        
        for child in children:
            child_tree = await self._build_folder_tree(child)
            child_trees.append(child_tree)
        
        # Get content summary
        content_summary = await self._get_content_summary(folder)
        
        return FolderTree(
            folder=folder,
            children=child_trees,
            content_summary=content_summary
        )
    
    async def _get_content_summary(self, folder: Folder) -> ContentSummary:
        """Get content summary for a folder."""
        try:
            # Get collection info from Qdrant
            collection_info = self.qdrant_client.get_collection(folder.qdrant_collection)
            point_count = collection_info.points_count or 0
            
            return ContentSummary(
                total_documents=point_count,
                content_type_counts={},  # Could be enhanced to count by content type
                last_updated=folder.updated_at,
                size_bytes=0  # Could be calculated if needed
            )
        except Exception as e:
            logger.warning(f"Failed to get content summary for folder {folder.id}: {e}")
            return ContentSummary()
    
    async def assign_content_to_folder(self, content: Document, folder_id: str) -> None:
        """Assign content to folder and update Qdrant collection."""
        folder = await self.get_folder(folder_id)
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Folder {folder_id} not found"
            )
        
        # Validate content type is supported by folder
        if content.content_type not in folder.content_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Content type {content.content_type} not supported by folder {folder.name}"
            )
        
        # Update content folder assignment
        content.folder_id = folder_id
        
        # Generate embeddings and upsert to appropriate collection
        try:
            embeddings = embed_text_batch([content.content])[0]
            
            point = PointStruct(
                id=content.id,
                vector=embeddings,
                payload={
                    "title": content.title,
                    "content": content.content[:1000],  # Truncate for payload
                    "content_type": content.content_type.value,
                    "folder_id": folder_id,
                    "device_associations": content.device_associations,
                    "tags": content.tags,
                    "indexed_at": content.indexed_at.isoformat(),
                    "metadata": content.metadata.model_dump()
                }
            )
            
            self.qdrant_client.upsert(
                collection_name=folder.qdrant_collection,
                points=[point]
            )
            
            # Update folder content count
            await self._update_folder_content_count(folder_id, 1)
            
            logger.info(f"Assigned content {content.id} to folder {folder.name}")
            
        except Exception as e:
            logger.error(f"Failed to assign content to folder: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to assign content to folder: {str(e)}"
            )
    
    async def _update_folder_content_count(self, folder_id: str, delta: int) -> None:
        """Update folder content count."""
        folder = await self.get_folder(folder_id)
        if folder:
            folder.content_count = max(0, folder.content_count + delta)
            folder.updated_at = datetime.now(timezone.utc)
            
            await self.config_store.save_folder(folder)
            self.folder_cache[folder_id] = folder
    
    async def move_content(self, content_id: str, from_folder_id: str, to_folder_id: str) -> None:
        """Move content between folders."""
        from_folder = await self.get_folder(from_folder_id)
        to_folder = await self.get_folder(to_folder_id)
        
        if not from_folder or not to_folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Source or destination folder not found"
            )
        
        try:
            # Get the point from source collection
            points, _ = self.qdrant_client.scroll(
                collection_name=from_folder.qdrant_collection,
                limit=1,
                with_payload=True,
                with_vectors=True
            )
            
            source_point = None
            for point in points:
                if str(point.id) == content_id:
                    source_point = point
                    break
            
            if not source_point:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Content {content_id} not found in source folder"
                )
            
            # Update payload with new folder ID
            updated_payload = {**source_point.payload, "folder_id": to_folder_id}
            
            # Create new point in destination collection
            new_point = PointStruct(
                id=source_point.id,
                vector=source_point.vector,
                payload=updated_payload
            )
            
            # Upsert to destination collection
            self.qdrant_client.upsert(
                collection_name=to_folder.qdrant_collection,
                points=[new_point]
            )
            
            # Delete from source collection
            self.qdrant_client.delete(
                collection_name=from_folder.qdrant_collection,
                points_selector=[content_id]
            )
            
            # Update folder content counts
            await self._update_folder_content_count(from_folder_id, -1)
            await self._update_folder_content_count(to_folder_id, 1)
            
            logger.info(f"Moved content {content_id} from {from_folder.name} to {to_folder.name}")
            
        except Exception as e:
            logger.error(f"Failed to move content: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to move content: {str(e)}"
            )