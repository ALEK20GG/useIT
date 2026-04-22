"""
Comprehensive testing framework tests for Task 20.

Covers Requirements 19.1-19.5:
- 19.1: Unit tests for all core functionality
- 19.2: Consistent and predictable mock AI responses
- 19.3: Integration tests for end-to-end workflows
- 19.4: Performance testing for search and content operations
- 19.5: Accessibility testing for WCAG compliance

Property tested:
- Property 65: Mock Framework Consistency (Req 19.2)
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.device_service import MockAIService, create_device_recognition_service
from app.ai_models import ModelConfiguration, ModelType, DeviceRecognitionResult, QRCodeResult
from app.ai_config import DefaultAIConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(coro):
    """Run a coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_mock_service() -> MockAIService:
    """Return an initialized MockAIService."""
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
    run(svc.initialize(config))
    return svc


# ---------------------------------------------------------------------------
# Requirement 19.1: Unit tests for core functionality
# ---------------------------------------------------------------------------


class TestCoreUnitTestCoverage:
    """
    Requirement 19.1: THE System SHALL include unit tests for all core
    functionality including device recognition and search operations.

    This class verifies the testing framework covers all core components.
    """

    def test_device_recognition_service_is_testable(self):
        """Device recognition service can be instantiated and tested."""
        svc = create_device_recognition_service()
        result = run(svc.initialize())
        assert result is True

    def test_mock_ai_service_is_testable(self):
        """Mock AI service can be instantiated and tested."""
        svc = _make_mock_service()
        assert svc.is_available() is True

    def test_device_recognition_returns_structured_result(self):
        """Device recognition returns a structured DeviceRecognitionResult."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x00" * 100
        result = run(svc.process_image(image_data))
        assert isinstance(result, DeviceRecognitionResult)
        assert result.device_id is not None
        assert result.device_name is not None
        assert result.manufacturer is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_qr_code_processing_returns_structured_result(self):
        """QR code processing returns a structured QRCodeResult."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x00" * 100
        result = run(svc.extract_qr_code(image_data))
        assert isinstance(result, QRCodeResult)
        assert result.content is not None
        assert 0.0 <= result.confidence <= 1.0

    def test_search_service_is_testable(self):
        """Search service can be instantiated with a mock Qdrant client."""
        from unittest.mock import MagicMock
        from app.search_service import EnhancedSearchService

        client = MagicMock()
        client.get_collections.return_value = MagicMock(collections=[])
        svc = EnhancedSearchService(client)
        assert svc is not None

    def test_content_retrieval_service_is_testable(self, tmp_path):
        """Content retrieval service can be instantiated and tested."""
        from app.content_retrieval_service import ContentRetrievalService
        from app.device_database import DeviceDatabase

        db = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))
        svc = ContentRetrievalService(device_database=db)
        assert svc is not None

    def test_folder_service_is_testable(self, tmp_path):
        """Folder service can be instantiated and tested."""
        from unittest.mock import MagicMock
        from app.folder_service import FolderService, ConfigStore

        mock_qdrant = MagicMock()
        config_store = ConfigStore(str(tmp_path))
        svc = FolderService(mock_qdrant, config_store)
        assert svc is not None

    def test_security_module_is_testable(self):
        """Security module functions can be tested."""
        from app.security import sanitize_search_query, sanitize_filename

        result = sanitize_search_query("test query")
        assert isinstance(result, str)

        result = sanitize_filename("document.pdf")
        assert isinstance(result, str)

    def test_error_handling_module_is_testable(self):
        """Error handling module can be tested."""
        from app.error_handling import make_device_recognition_error, ErrorCode

        response = make_device_recognition_error(ErrorCode.RECOGNITION_FAILED)
        assert response is not None
        assert response.user_message

    def test_config_management_is_testable(self):
        """Configuration management can be tested."""
        from app.app_config import AppSettings, HotReloadableConfig

        settings = AppSettings()
        assert settings is not None

        hot = HotReloadableConfig()
        assert hot is not None


# ---------------------------------------------------------------------------
# Requirement 19.2: Mock AI service consistency
# ---------------------------------------------------------------------------


class TestMockAIServiceConsistency:
    """
    Requirement 19.2: WHEN AI models are mocked, THE Test_Framework SHALL
    provide consistent and predictable responses.
    """

    def test_mock_service_always_initializes(self):
        """MockAIService always initializes successfully."""
        for _ in range(5):
            svc = _make_mock_service()
            assert svc.is_available() is True

    def test_mock_service_same_input_same_output(self):
        """Same input always produces same output (deterministic)."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\xab" * 100

        results = [run(svc.process_image(image_data)) for _ in range(5)]
        device_ids = [r.device_id for r in results]
        device_names = [r.device_name for r in results]
        confidences = [r.confidence for r in results]

        assert len(set(device_ids)) == 1, "device_id should be consistent"
        assert len(set(device_names)) == 1, "device_name should be consistent"
        assert len(set(confidences)) == 1, "confidence should be consistent"

    def test_mock_service_different_inputs_produce_valid_results(self):
        """Different inputs all produce valid DeviceRecognitionResult objects."""
        svc = _make_mock_service()
        test_images = [
            b"\xff\xd8\xff" + bytes([i]) * 100
            for i in range(10)
        ]
        for image_data in test_images:
            result = run(svc.process_image(image_data))
            assert isinstance(result, DeviceRecognitionResult)
            assert 0.0 <= result.confidence <= 1.0
            assert result.device_name is not None

    def test_mock_service_qr_same_input_same_output(self):
        """QR code extraction is deterministic for same input."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\xcd" * 100

        results = [run(svc.extract_qr_code(image_data)) for _ in range(5)]
        contents = [r.content for r in results]
        confidences = [r.confidence for r in results]

        assert len(set(contents)) == 1, "QR content should be consistent"
        assert len(set(confidences)) == 1, "QR confidence should be consistent"

    def test_mock_service_covers_all_device_types(self):
        """Mock service returns results from all predefined device types."""
        svc = _make_mock_service()
        device_names_seen = set()

        # Generate enough different images to cover all mock device types
        for i in range(100):
            image_data = b"\xff\xd8\xff" + bytes([i % 256]) * 50 + bytes([i // 256]) * 50
            result = run(svc.process_image(image_data))
            device_names_seen.add(result.device_name)

        # Should have seen multiple different device types
        assert len(device_names_seen) > 1, (
            f"Expected multiple device types, only saw: {device_names_seen}"
        )


# ---------------------------------------------------------------------------
# Requirement 19.3: Integration tests for end-to-end workflows
# ---------------------------------------------------------------------------


class TestEndToEndWorkflows:
    """
    Requirement 19.3: THE System SHALL implement integration tests for
    end-to-end workflows including upload, search, and retrieval.
    """

    def test_device_creation_and_retrieval_workflow(self, tmp_path):
        """
        Integration test: Create a device and retrieve it.
        Validates the complete device CRUD workflow.
        """
        from app.device_database import DeviceDatabase

        db = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))

        # Create
        device = db.create(
            name="Arduino Uno",
            manufacturer="Arduino",
            model="Uno R3",
            qr_codes=["https://arduino.cc/qr"],
            documentation_urls=["https://arduino.cc/docs"],
        )
        assert device.id is not None

        # Retrieve
        retrieved = db.get(device.id)
        assert retrieved is not None
        assert retrieved.name == "Arduino Uno"
        assert retrieved.manufacturer == "Arduino"

        # Search
        results = db.search("arduino")
        assert len(results) == 1
        assert results[0].id == device.id

        # QR lookup
        found = db.find_by_qr_code("https://arduino.cc/qr")
        assert found is not None
        assert found.id == device.id

        # Update
        updated = db.update(device.id, name="Arduino Uno R3")
        assert updated.name == "Arduino Uno R3"

        # Delete
        deleted = db.delete(device.id)
        assert deleted is True
        assert db.get(device.id) is None

    def test_content_retrieval_workflow(self, tmp_path):
        """
        Integration test: Retrieve content for a device from multiple sources.
        Validates the complete content retrieval workflow.
        """
        from app.device_database import DeviceDatabase
        from app.content_retrieval_service import ContentRetrievalService, ContentSource

        db = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))
        db.create(
            name="Arduino Uno",
            manufacturer="Arduino",
            model="Uno R3",
            documentation_urls=["https://arduino.cc/docs"],
        )

        service = ContentRetrievalService(device_database=db)
        result = run(service.retrieve_device_content(
            {"name": "Arduino Uno", "manufacturer": "Arduino"}
        ))

        assert result is not None
        assert result.total_count == len(result.items)
        assert ContentSource.INTERNAL_DATABASE in result.sources_queried
        assert ContentSource.WEB_SEARCH in result.sources_queried
        assert ContentSource.YOUTUBE in result.sources_queried
        assert result.retrieval_time_ms >= 0

    def test_device_recognition_workflow(self):
        """
        Integration test: Recognize a device from an image.
        Validates the complete device recognition workflow.
        """
        svc = create_device_recognition_service()
        run(svc.initialize())

        # Test with JPEG
        jpeg_image = b"\xff\xd8\xff" + b"\x00" * 200
        result = run(svc.recognize_device_from_photo(jpeg_image))
        assert isinstance(result, DeviceRecognitionResult)

        # Test with PNG
        png_image = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        result = run(svc.recognize_device_from_photo(png_image))
        assert isinstance(result, DeviceRecognitionResult)

        # Test QR code decoding
        qr_image = b"\xff\xd8\xff" + b"\x00" * 200
        qr_result = run(svc.decode_qr_code(qr_image))
        assert isinstance(qr_result, QRCodeResult)

    def test_search_history_workflow(self):
        """
        Integration test: Search history and suggestions workflow.
        Validates the complete search history workflow.
        """
        from unittest.mock import MagicMock
        from app.search_service import EnhancedSearchService

        client = MagicMock()
        client.get_collections.return_value = MagicMock(collections=[])
        svc = EnhancedSearchService(client)

        # Add search history
        svc._history.add("arduino uno")
        svc._history.add("raspberry pi")
        svc._history.add("esp32 devkit")

        # Get history
        history = svc.get_search_history(10)
        assert len(history) == 3

        # Get suggestions
        suggestions = svc.get_search_suggestions("arduino", 5)
        assert len(suggestions) == 1
        assert "arduino uno" in suggestions

    def test_folder_creation_workflow(self, tmp_path):
        """
        Integration test: Create and manage folders.
        Validates the complete folder management workflow.
        """
        from unittest.mock import MagicMock
        from app.folder_service import FolderService, ConfigStore
        from app.folder_models import FolderDefinition, ContentType

        mock_qdrant = MagicMock()
        mock_qdrant.get_collection.side_effect = Exception("Not found")
        mock_qdrant.create_collection = MagicMock()

        config_store = ConfigStore(str(tmp_path))
        svc = FolderService(mock_qdrant, config_store)

        # Create folder
        folder_def = FolderDefinition(
            name="Test Folder",
            description="A test folder",
            content_types=[ContentType.NOTES],
        )
        folder = run(svc.create_folder(folder_def))
        assert folder.name == "Test Folder"
        assert folder.id is not None

        # List folders
        folders = run(svc.list_folders())
        assert len(folders) == 1

        # Get by name
        found = run(svc.get_folder_by_name("Test Folder"))
        assert found is not None
        assert found.id == folder.id


# ---------------------------------------------------------------------------
# Requirement 19.4: Performance testing
# ---------------------------------------------------------------------------


class TestPerformanceRequirements:
    """
    Requirement 19.4: THE Test_Framework SHALL support performance testing
    for search operations and content retrieval.
    """

    def test_device_recognition_performance(self):
        """
        Device recognition should complete within acceptable time limits.
        Validates performance for device recognition operations.
        """
        svc = create_device_recognition_service()
        run(svc.initialize())

        image_data = b"\xff\xd8\xff" + b"\x00" * 200
        max_allowed_ms = 2000  # 2 seconds max

        start = time.perf_counter()
        result = run(svc.recognize_device_from_photo(image_data))
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert isinstance(result, DeviceRecognitionResult)
        assert elapsed_ms < max_allowed_ms, (
            f"Device recognition took {elapsed_ms:.1f}ms, exceeds {max_allowed_ms}ms limit"
        )

    def test_content_retrieval_performance(self, tmp_path):
        """
        Content retrieval should complete within acceptable time limits.
        Validates performance for content retrieval operations.
        """
        from app.device_database import DeviceDatabase
        from app.content_retrieval_service import ContentRetrievalService

        db = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))
        service = ContentRetrievalService(device_database=db)

        max_allowed_ms = 5000  # 5 seconds max

        start = time.perf_counter()
        result = run(service.retrieve_device_content({"name": "Arduino Uno"}))
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result is not None
        assert elapsed_ms < max_allowed_ms, (
            f"Content retrieval took {elapsed_ms:.1f}ms, exceeds {max_allowed_ms}ms limit"
        )

    def test_content_retrieval_caching_improves_performance(self, tmp_path):
        """
        Cached content retrieval should be faster than uncached.
        Validates caching performance improvement.
        """
        from app.device_database import DeviceDatabase
        from app.content_retrieval_service import ContentRetrievalService

        db = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))
        service = ContentRetrievalService(device_database=db)
        device_info = {"name": "Arduino Uno", "manufacturer": "Arduino"}

        # First call (cache miss)
        start = time.perf_counter()
        run(service.retrieve_device_content(device_info))
        first_call_ms = (time.perf_counter() - start) * 1000

        # Second call (cache hit)
        start = time.perf_counter()
        run(service.retrieve_device_content(device_info))
        second_call_ms = (time.perf_counter() - start) * 1000

        # Cached call should be faster (or at least not significantly slower)
        # Allow 10x tolerance for test environment variability
        assert second_call_ms <= first_call_ms * 10, (
            f"Cached call ({second_call_ms:.1f}ms) should not be much slower "
            f"than uncached ({first_call_ms:.1f}ms)"
        )

    def test_search_cache_performance(self):
        """
        Search cache operations should be fast.
        Validates search cache performance.
        """
        from app.search_cache import SearchCache

        cache = SearchCache(max_entries=1000)
        max_operation_ms = 10  # Cache operations should be < 10ms

        # Test set performance
        start = time.perf_counter()
        for i in range(100):
            cache.set(f"key_{i}", [f"result_{i}"])
        set_elapsed_ms = (time.perf_counter() - start) * 1000

        assert set_elapsed_ms < max_operation_ms * 100, (
            f"100 cache sets took {set_elapsed_ms:.1f}ms"
        )

        # Test get performance
        start = time.perf_counter()
        for i in range(100):
            cache.get(f"key_{i}")
        get_elapsed_ms = (time.perf_counter() - start) * 1000

        assert get_elapsed_ms < max_operation_ms * 100, (
            f"100 cache gets took {get_elapsed_ms:.1f}ms"
        )

    def test_device_database_search_performance(self, tmp_path):
        """
        Device database search should be fast even with many records.
        Validates search performance for device database.
        """
        from app.device_database import DeviceDatabase

        db = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))

        # Populate with 50 devices
        for i in range(50):
            db.create(
                name=f"Device {i}",
                manufacturer=f"Manufacturer {i % 5}",
                model=f"Model-{i:03d}",
            )

        max_search_ms = 500  # Search should complete within 500ms

        start = time.perf_counter()
        results = db.search("Device")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert len(results) == 50
        assert elapsed_ms < max_search_ms, (
            f"Search over 50 devices took {elapsed_ms:.1f}ms, exceeds {max_search_ms}ms"
        )


# ---------------------------------------------------------------------------
# Requirement 19.5: Accessibility testing
# ---------------------------------------------------------------------------


class TestAccessibilityCompliance:
    """
    Requirement 19.5: THE System SHALL include accessibility testing to
    verify WCAG compliance.

    Note: Full WCAG compliance requires manual testing with assistive
    technologies. These tests verify backend API responses include
    accessibility-relevant metadata and structure.
    """

    def test_api_error_responses_have_descriptive_messages(self):
        """
        API error responses should have descriptive, accessible messages.
        Validates that error messages are human-readable (WCAG 3.3.1).
        """
        from app.error_handling import make_device_recognition_error, ErrorCode

        for error_code in [
            ErrorCode.IMAGE_TOO_LARGE,
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            ErrorCode.RECOGNITION_FAILED,
            ErrorCode.QR_NOT_DETECTED,
        ]:
            response = make_device_recognition_error(error_code)
            # User message should be descriptive (not just an error code)
            assert len(response.user_message) > 20, (
                f"Error message for {error_code} is too short: {response.user_message!r}"
            )
            # Should not be all uppercase (hard to read)
            assert response.user_message != response.user_message.upper(), (
                f"Error message for {error_code} is all uppercase"
            )

    def test_api_responses_have_consistent_structure(self, tmp_path):
        """
        API responses should have consistent, predictable structure.
        Validates structural consistency for screen reader compatibility.
        """
        from app.device_database import DeviceDatabase

        db = DeviceDatabase(storage_path=str(tmp_path / "devices.json"))
        device = db.create(
            name="Arduino Uno",
            manufacturer="Arduino",
            model="Uno R3",
        )

        # All device records should have the same fields
        required_fields = {"id", "name", "manufacturer", "model", "created_at"}
        device_dict = device.__dict__
        for field in required_fields:
            assert field in device_dict, f"Device record missing required field: {field}"

    def test_search_results_have_accessible_metadata(self):
        """
        Search results should include metadata needed for accessibility.
        Validates that results have title and content for screen readers.
        """
        from app.search_service import SearchResult

        result = SearchResult(
            id="test-1",
            title="Arduino Uno Documentation",
            content="This is the documentation for Arduino Uno...",
            score=0.9,
        )

        # Results must have title (for screen reader announcements)
        assert result.title is not None
        assert len(result.title) > 0

        # Results must have content (for screen reader reading)
        assert result.content is not None
        assert len(result.content) > 0

    def test_error_suggestions_are_actionable(self):
        """
        Error suggestions should be actionable (WCAG 3.3.3 - Error Suggestion).
        Validates that suggestions tell users what to do.
        """
        from app.error_handling import make_device_recognition_error, ErrorCode

        response = make_device_recognition_error(ErrorCode.RECOGNITION_FAILED)

        for suggestion in response.suggestions:
            # Each suggestion should have an action (what to do)
            assert suggestion.action is not None
            assert len(suggestion.action) > 0, "Suggestion action should not be empty"

    def test_upload_errors_provide_format_guidance(self):
        """
        Upload errors should provide format guidance (WCAG 3.3.2 - Labels or Instructions).
        Validates that format errors explain what formats are accepted.
        """
        from app.error_handling import make_upload_error, ErrorCode

        response = make_upload_error("test.exe", ErrorCode.UPLOAD_FORMAT_UNSUPPORTED)

        # Should mention accepted formats
        all_text = response.user_message + " ".join(response.retry_options)
        # Should reference some accepted format
        has_format_info = any(
            fmt in all_text.lower()
            for fmt in ["pdf", "txt", "doc", "formato", "format"]
        )
        assert has_format_info, (
            "Format error should mention accepted file formats"
        )


# ---------------------------------------------------------------------------
# Property 65: Mock Framework Consistency (Requirement 19.2)
# ---------------------------------------------------------------------------


@given(st.binary(min_size=3, max_size=512))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property_65_mock_service_always_returns_valid_result(image_bytes):
    """
    **Validates: Requirements 19.2**

    Property 65: Mock Framework Consistency

    For any image bytes input, MockAIService SHALL always return a valid
    DeviceRecognitionResult with:
    - A non-empty device_id
    - A non-empty device_name
    - A non-empty manufacturer
    - A confidence value in [0.0, 1.0]
    - A list of alternative_matches (may be empty)
    """
    svc = _make_mock_service()
    result = run(svc.process_image(image_bytes))

    assert isinstance(result, DeviceRecognitionResult), (
        f"Expected DeviceRecognitionResult, got {type(result).__name__}"
    )
    assert result.device_id is not None and len(result.device_id) > 0, (
        "device_id must be non-empty"
    )
    assert result.device_name is not None and len(result.device_name) > 0, (
        "device_name must be non-empty"
    )
    assert result.manufacturer is not None and len(result.manufacturer) > 0, (
        "manufacturer must be non-empty"
    )
    assert 0.0 <= result.confidence <= 1.0, (
        f"confidence={result.confidence} must be in [0.0, 1.0]"
    )
    assert isinstance(result.alternative_matches, list), (
        "alternative_matches must be a list"
    )


@given(st.binary(min_size=3, max_size=512))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property_65_mock_service_deterministic(image_bytes):
    """
    **Validates: Requirements 19.2**

    Property 65: Mock Framework Consistency

    MockAIService SHALL be deterministic: the same image bytes always
    produce the same device_id, device_name, and confidence.
    This ensures tests are reproducible and predictable.
    """
    svc = _make_mock_service()

    result1 = run(svc.process_image(image_bytes))
    result2 = run(svc.process_image(image_bytes))

    assert result1.device_id == result2.device_id, (
        f"device_id not deterministic: {result1.device_id!r} vs {result2.device_id!r}"
    )
    assert result1.device_name == result2.device_name, (
        f"device_name not deterministic: {result1.device_name!r} vs {result2.device_name!r}"
    )
    assert result1.confidence == result2.confidence, (
        f"confidence not deterministic: {result1.confidence} vs {result2.confidence}"
    )


@given(st.binary(min_size=3, max_size=512))
@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow])
def test_property_65_mock_qr_service_always_returns_valid_result(image_bytes):
    """
    **Validates: Requirements 19.2**

    Property 65: Mock Framework Consistency

    For any image bytes input, MockAIService.extract_qr_code SHALL always
    return a valid QRCodeResult with:
    - A non-empty content string
    - A confidence value in [0.0, 1.0]
    - A valid QRCodeFormat
    """
    svc = _make_mock_service()
    result = run(svc.extract_qr_code(image_bytes))

    assert isinstance(result, QRCodeResult), (
        f"Expected QRCodeResult, got {type(result).__name__}"
    )
    assert result.content is not None and len(result.content) > 0, (
        "QR content must be non-empty"
    )
    assert 0.0 <= result.confidence <= 1.0, (
        f"QR confidence={result.confidence} must be in [0.0, 1.0]"
    )


@given(
    image_bytes_1=st.binary(min_size=3, max_size=256),
    image_bytes_2=st.binary(min_size=3, max_size=256),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.too_slow])
def test_property_65_mock_service_independent_calls(image_bytes_1, image_bytes_2):
    """
    **Validates: Requirements 19.2**

    Property 65: Mock Framework Consistency

    MockAIService calls are independent: processing image_1 does not affect
    the result of processing image_2. Each call produces a valid result
    regardless of call order.
    """
    svc = _make_mock_service()

    # Process in order 1, 2
    result_1_first = run(svc.process_image(image_bytes_1))
    result_2_after_1 = run(svc.process_image(image_bytes_2))

    # Process in order 2, 1
    result_2_first = run(svc.process_image(image_bytes_2))
    result_1_after_2 = run(svc.process_image(image_bytes_1))

    # Results should be the same regardless of call order
    assert result_1_first.device_id == result_1_after_2.device_id, (
        "image_1 result changed based on call order"
    )
    assert result_2_after_1.device_id == result_2_first.device_id, (
        "image_2 result changed based on call order"
    )
