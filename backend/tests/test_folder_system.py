"""
Tests for the folder system infrastructure.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from app.folder_service import FolderService, ConfigStore
from app.folder_models import FolderDefinition, ContentType, Folder
from app.qdrant_config import DefaultFolderConfig, QdrantCollectionConfig


class TestConfigStore:
    """Test the configuration store."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_store = ConfigStore(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_save_and_get_folder(self):
        """Test saving and retrieving folder configuration."""
        
        folder = Folder(
            id="test-folder-1",
            name="Test Folder",
            description="A test folder",
            path="/Test Folder",
            content_types=[ContentType.NOTES],
            qdrant_collection="test_collection"
        )
        
        # Save folder
        await self.config_store.save_folder(folder)
        
        # Retrieve folder
        retrieved_folder = await self.config_store.get_folder("test-folder-1")
        
        assert retrieved_folder is not None
        assert retrieved_folder.id == folder.id
        assert retrieved_folder.name == folder.name
        assert retrieved_folder.description == folder.description
        assert retrieved_folder.content_types == folder.content_types
    
    @pytest.mark.asyncio
    async def test_get_all_folders(self):
        """Test retrieving all folders."""
        
        folder1 = Folder(
            id="folder-1",
            name="Folder 1",
            path="/Folder 1",
            content_types=[ContentType.NOTES],
            qdrant_collection="collection1"
        )
        
        folder2 = Folder(
            id="folder-2",
            name="Folder 2",
            path="/Folder 2",
            content_types=[ContentType.PDF_DOCUMENTS],
            qdrant_collection="collection2"
        )
        
        await self.config_store.save_folder(folder1)
        await self.config_store.save_folder(folder2)
        
        all_folders = await self.config_store.get_all_folders()
        
        assert len(all_folders) == 2
        assert "folder-1" in all_folders
        assert "folder-2" in all_folders
    
    @pytest.mark.asyncio
    async def test_delete_folder(self):
        """Test deleting folder configuration."""
        
        folder = Folder(
            id="delete-test",
            name="Delete Test",
            path="/Delete Test",
            content_types=[ContentType.NOTES],
            qdrant_collection="delete_collection"
        )
        
        await self.config_store.save_folder(folder)
        
        # Verify folder exists
        retrieved = await self.config_store.get_folder("delete-test")
        assert retrieved is not None
        
        # Delete folder
        success = await self.config_store.delete_folder("delete-test")
        assert success is True
        
        # Verify folder is gone
        retrieved = await self.config_store.get_folder("delete-test")
        assert retrieved is None


class TestQdrantConfig:
    """Test Qdrant configuration utilities."""
    
    def test_get_collection_config(self):
        """Test getting collection configuration."""
        
        # Test default folder config
        dispositivi_config = QdrantCollectionConfig.get_collection_config("dispositivi")
        assert dispositivi_config["vector_size"] == 384
        assert "device_id" in dispositivi_config["payload_schema"]
        
        # Test unknown collection gets default config
        unknown_config = QdrantCollectionConfig.get_collection_config("unknown")
        assert unknown_config["vector_size"] == 384
        assert "content_type" in unknown_config["payload_schema"]
    
    def test_default_folder_config(self):
        """Test default folder configurations."""
        
        all_defaults = DefaultFolderConfig.get_all_default_folders()
        
        assert "dispositivi" in all_defaults
        assert "appunti" in all_defaults
        assert "scuola" in all_defaults
        
        dispositivi = all_defaults["dispositivi"]
        assert dispositivi["name"] == "Dispositivi"
        assert ContentType.DEVICE_DOCUMENTATION in dispositivi["content_types"]


class TestFolderService:
    """Test the folder service."""
    
    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_qdrant = Mock()
        self.config_store = ConfigStore(self.temp_dir)
        self.folder_service = FolderService(self.mock_qdrant, self.config_store)
    
    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_create_folder(self):
        """Test creating a new folder."""
        
        # Mock Qdrant operations
        self.mock_qdrant.get_collection.side_effect = Exception("Collection not found")
        self.mock_qdrant.create_collection = Mock()
        
        folder_def = FolderDefinition(
            name="Test Folder",
            description="A test folder",
            content_types=[ContentType.NOTES],
            metadata={"test": True}
        )
        
        folder = await self.folder_service.create_folder(folder_def)
        
        assert folder.name == "Test Folder"
        assert folder.description == "A test folder"
        assert folder.content_types == [ContentType.NOTES]
        assert folder.metadata["test"] is True
        assert folder.path == "/Test Folder"
        
        # Verify Qdrant collection was created
        self.mock_qdrant.create_collection.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_nested_folder(self):
        """Test creating nested folders."""
        
        # Mock Qdrant operations
        self.mock_qdrant.get_collection.side_effect = Exception("Collection not found")
        self.mock_qdrant.create_collection = Mock()
        
        # Create parent folder
        parent_def = FolderDefinition(
            name="Parent",
            content_types=[ContentType.NOTES]
        )
        parent_folder = await self.folder_service.create_folder(parent_def)
        
        # Create child folder
        child_def = FolderDefinition(
            name="Child",
            parent_id=parent_folder.id,
            content_types=[ContentType.NOTES]
        )
        child_folder = await self.folder_service.create_folder(child_def)
        
        assert child_folder.parent_id == parent_folder.id
        assert child_folder.path == "/Parent/Child"
    
    @pytest.mark.asyncio
    async def test_folder_hierarchy_depth_limit(self):
        """Test that folder hierarchy depth is limited to 3 levels."""
        
        # Mock Qdrant operations
        self.mock_qdrant.get_collection.side_effect = Exception("Collection not found")
        self.mock_qdrant.create_collection = Mock()
        
        # Create folder hierarchy: Level 1 -> Level 2 -> Level 3
        level1_def = FolderDefinition(name="Level1", content_types=[ContentType.NOTES])
        level1 = await self.folder_service.create_folder(level1_def)
        
        level2_def = FolderDefinition(name="Level2", parent_id=level1.id, content_types=[ContentType.NOTES])
        level2 = await self.folder_service.create_folder(level2_def)
        
        level3_def = FolderDefinition(name="Level3", parent_id=level2.id, content_types=[ContentType.NOTES])
        level3 = await self.folder_service.create_folder(level3_def)
        
        # Trying to create Level 4 should fail
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            level4_def = FolderDefinition(name="Level4", parent_id=level3.id, content_types=[ContentType.NOTES])
            await self.folder_service.create_folder(level4_def)
        
        assert exc_info.value.status_code == 400
        assert "Maximum folder hierarchy depth" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_list_folders(self):
        """Test listing all folders."""
        
        # Mock Qdrant operations
        self.mock_qdrant.get_collection.side_effect = Exception("Collection not found")
        self.mock_qdrant.create_collection = Mock()
        
        # Create multiple folders
        folder1_def = FolderDefinition(name="Folder1", content_types=[ContentType.NOTES])
        folder2_def = FolderDefinition(name="Folder2", content_types=[ContentType.PDF_DOCUMENTS])
        
        folder1 = await self.folder_service.create_folder(folder1_def)
        folder2 = await self.folder_service.create_folder(folder2_def)
        
        folders = await self.folder_service.list_folders()
        
        assert len(folders) == 2
        folder_names = [f.name for f in folders]
        assert "Folder1" in folder_names
        assert "Folder2" in folder_names
    
    @pytest.mark.asyncio
    async def test_get_folder_by_name(self):
        """Test getting folder by name."""
        
        # Mock Qdrant operations
        self.mock_qdrant.get_collection.side_effect = Exception("Collection not found")
        self.mock_qdrant.create_collection = Mock()
        
        folder_def = FolderDefinition(name="FindMe", content_types=[ContentType.NOTES])
        created_folder = await self.folder_service.create_folder(folder_def)
        
        found_folder = await self.folder_service.get_folder_by_name("FindMe")
        
        assert found_folder is not None
        assert found_folder.id == created_folder.id
        assert found_folder.name == "FindMe"
        
        # Test non-existent folder
        not_found = await self.folder_service.get_folder_by_name("DoesNotExist")
        assert not_found is None


if __name__ == "__main__":
    pytest.main([__file__])
