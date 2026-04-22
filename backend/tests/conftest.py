"""
Shared pytest fixtures and configuration for the intelligent device documentation platform.

This conftest.py provides:
- Common fixtures for database, service, and API client setup
- Mock AI service fixtures for consistent testing (Requirement 19.2)
- Performance measurement utilities (Requirement 19.4)
- Shared test data and helpers
"""

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Event loop configuration
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use the default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()


# ---------------------------------------------------------------------------
# Temporary directory fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_storage(tmp_path: Path) -> Path:
    """Provide a temporary storage directory for tests."""
    storage = tmp_path / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    return storage


@pytest.fixture
def tmp_config_file(tmp_path: Path) -> Path:
    """Provide a temporary config file path."""
    return tmp_path / "app-config.json"


# ---------------------------------------------------------------------------
# Device database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def device_db(tmp_path: Path):
    """Provide a fresh DeviceDatabase backed by a temporary file."""
    from app.device_database import DeviceDatabase
    return DeviceDatabase(storage_path=str(tmp_path / "devices.json"))


@pytest.fixture
def populated_device_db(device_db):
    """Provide a DeviceDatabase pre-populated with sample devices."""
    device_db.create(
        name="Arduino Uno",
        manufacturer="Arduino",
        model="Uno R3",
        category="microcontroller",
        qr_codes=["https://arduino.cc/en/Main/ArduinoBoardUno"],
        documentation_urls=["https://arduino.cc/en/Reference/HomePage"],
        specifications={"voltage": "5V", "current": "500mA", "flash": "32KB"},
    )
    device_db.create(
        name="Raspberry Pi 4",
        manufacturer="Raspberry Pi Foundation",
        model="Pi 4 Model B",
        category="single-board-computer",
        qr_codes=["https://raspberrypi.org/products/raspberry-pi-4-model-b/"],
        documentation_urls=["https://raspberrypi.org/documentation/"],
        specifications={"ram": "4GB", "cpu": "ARM Cortex-A72", "os": "Raspberry Pi OS"},
    )
    device_db.create(
        name="ESP32 DevKit",
        manufacturer="Espressif",
        model="ESP32-WROOM-32",
        category="microcontroller",
        qr_codes=["DEVICE:ESP32-WROOM-32:SN001"],
        documentation_urls=["https://espressif.com/en/products/socs/esp32"],
        specifications={"wifi": "802.11 b/g/n", "bluetooth": "4.2", "flash": "4MB"},
    )
    return device_db


# ---------------------------------------------------------------------------
# Mock AI service fixtures (Requirement 19.2)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ai_service():
    """
    Provide an initialized MockAIService for consistent testing.

    Requirement 19.2: WHEN AI models are mocked, THE Test_Framework SHALL
    provide consistent and predictable responses.
    """
    from app.device_service import MockAIService
    from app.ai_models import ModelConfiguration, ModelType

    svc = MockAIService()
    config = ModelConfiguration(
        model_name="test-mock",
        model_path="",
        model_type=ModelType.PYTORCH,
        input_size=(640, 640),
        confidence_threshold=0.7,
        batch_size=1,
        device="cpu",
        preprocessing_config={},
    )
    asyncio.get_event_loop().run_until_complete(svc.initialize(config))
    return svc


@pytest.fixture
def device_recognition_service():
    """
    Provide an initialized DeviceRecognitionService using mock AI.

    Requirement 19.2: Consistent mock responses for testing.
    """
    from app.device_service import create_device_recognition_service

    svc = create_device_recognition_service()
    asyncio.get_event_loop().run_until_complete(svc.initialize())
    return svc


# ---------------------------------------------------------------------------
# Content retrieval service fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def content_retrieval_service(device_db):
    """Provide a ContentRetrievalService with a fresh device database."""
    from app.content_retrieval_service import ContentRetrievalService
    return ContentRetrievalService(device_database=device_db)


@pytest.fixture
def content_retrieval_service_with_devices(populated_device_db):
    """Provide a ContentRetrievalService with pre-populated device data."""
    from app.content_retrieval_service import ContentRetrievalService
    return ContentRetrievalService(device_database=populated_device_db)


# ---------------------------------------------------------------------------
# Search service fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_qdrant_client():
    """Provide a mock Qdrant client for search service tests."""
    client = MagicMock()
    client.get_collections.return_value = MagicMock(collections=[])
    client.search.return_value = []
    client.scroll.return_value = ([], None)
    return client


@pytest.fixture
def search_service(mock_qdrant_client):
    """Provide an EnhancedSearchService with a mock Qdrant client."""
    from app.search_service import EnhancedSearchService
    return EnhancedSearchService(mock_qdrant_client)


# ---------------------------------------------------------------------------
# Folder service fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def folder_service(tmp_path: Path):
    """Provide a FolderService with a temporary config store."""
    from app.folder_service import FolderService, ConfigStore

    mock_qdrant = MagicMock()
    mock_qdrant.get_collection.side_effect = Exception("Collection not found")
    mock_qdrant.create_collection = MagicMock()

    config_store = ConfigStore(str(tmp_path))
    return FolderService(mock_qdrant, config_store)


# ---------------------------------------------------------------------------
# FastAPI test client fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client(tmp_path: Path):
    """
    Provide a FastAPI TestClient with isolated dependencies.

    Requirement 19.3: Integration tests for end-to-end workflows.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.device_database import DeviceDatabase, get_device_database
    from app.content_retrieval_service import (
        ContentRetrievalService,
        get_content_retrieval_service,
    )

    test_db = DeviceDatabase(storage_path=str(tmp_path / "test_devices.json"))
    test_service = ContentRetrievalService(device_database=test_db)

    app.dependency_overrides[get_device_database] = lambda: test_db
    app.dependency_overrides[get_content_retrieval_service] = lambda: test_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def api_client_with_devices(tmp_path: Path):
    """
    Provide a FastAPI TestClient with pre-populated device data.

    Requirement 19.3: Integration tests for complete workflows.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.device_database import DeviceDatabase, get_device_database
    from app.content_retrieval_service import (
        ContentRetrievalService,
        get_content_retrieval_service,
    )

    test_db = DeviceDatabase(storage_path=str(tmp_path / "test_devices.json"))
    # Pre-populate with sample devices
    test_db.create(
        name="Arduino Uno",
        manufacturer="Arduino",
        model="Uno R3",
        qr_codes=["https://arduino.cc/en/Main/ArduinoBoardUno"],
        documentation_urls=["https://arduino.cc/en/Reference/HomePage"],
    )
    test_db.create(
        name="Raspberry Pi 4",
        manufacturer="Raspberry Pi Foundation",
        model="Pi 4 Model B",
        documentation_urls=["https://raspberrypi.org/documentation/"],
    )

    test_service = ContentRetrievalService(device_database=test_db)

    app.dependency_overrides[get_device_database] = lambda: test_db
    app.dependency_overrides[get_content_retrieval_service] = lambda: test_service

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Performance measurement fixtures (Requirement 19.4)
# ---------------------------------------------------------------------------

@pytest.fixture
def performance_timer():
    """
    Provide a simple performance timer for measuring operation durations.

    Requirement 19.4: Support performance testing for search operations.
    """
    class Timer:
        def __init__(self):
            self.measurements = []
            self._start = None

        def start(self):
            self._start = time.perf_counter()

        def stop(self) -> float:
            if self._start is None:
                raise RuntimeError("Timer not started")
            elapsed_ms = (time.perf_counter() - self._start) * 1000
            self.measurements.append(elapsed_ms)
            self._start = None
            return elapsed_ms

        @property
        def average_ms(self) -> float:
            if not self.measurements:
                return 0.0
            return sum(self.measurements) / len(self.measurements)

        @property
        def max_ms(self) -> float:
            return max(self.measurements) if self.measurements else 0.0

        @property
        def min_ms(self) -> float:
            return min(self.measurements) if self.measurements else 0.0

    return Timer()


@pytest.fixture
def performance_threshold():
    """
    Provide performance thresholds for testing.

    Requirement 19.4: Performance testing for search and content operations.
    """
    return {
        "search_response_ms": 1000,    # Search should respond within 1 second
        "content_retrieval_ms": 5000,  # Content retrieval within 5 seconds
        "device_recognition_ms": 2000, # Device recognition within 2 seconds
        "file_upload_ms": 10000,       # File upload within 10 seconds
    }


# ---------------------------------------------------------------------------
# Sample image data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_jpeg_image() -> bytes:
    """Provide minimal valid JPEG image bytes for testing."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * 200


@pytest.fixture
def sample_png_image() -> bytes:
    """Provide minimal valid PNG image bytes for testing."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 200


@pytest.fixture
def sample_webp_image() -> bytes:
    """Provide minimal valid WebP image bytes for testing."""
    return b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 200


@pytest.fixture
def oversized_image() -> bytes:
    """Provide an oversized image (>10MB) for testing size validation."""
    return b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)


# ---------------------------------------------------------------------------
# Sample document fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_pdf_content() -> bytes:
    """Provide minimal valid PDF content bytes for testing."""
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


@pytest.fixture
def sample_text_content() -> bytes:
    """Provide sample text document content for testing."""
    return b"This is a sample document for testing purposes.\nIt contains multiple lines.\n"


# ---------------------------------------------------------------------------
# Hypothesis settings profiles
# ---------------------------------------------------------------------------

from hypothesis import settings as hypothesis_settings, HealthCheck

# Fast profile for CI/CD
hypothesis_settings.register_profile(
    "ci",
    max_examples=20,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)

# Standard profile for development
hypothesis_settings.register_profile(
    "dev",
    max_examples=50,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)

# Thorough profile for comprehensive testing
hypothesis_settings.register_profile(
    "thorough",
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)

# Load profile from environment variable, default to "dev"
_profile = os.environ.get("HYPOTHESIS_PROFILE", "dev")
hypothesis_settings.load_profile(_profile)
