"""
Unit and property-based tests for AI integration architecture.

Covers Task 2 requirements:
- 9.1: AI model interface definition
- 9.2: Mock AI service for development and testing
- 9.3: Model loading and initialization
- 9.4: Support for different model formats
- 9.5: Configuration options for AI model parameters
"""

import asyncio
import hashlib
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.ai_models import (
    AIModelInterface,
    DeviceRecognitionResult,
    ModelConfiguration,
    ModelInfo,
    ModelType,
    QRCodeFormat,
    QRCodeResult,
)
from app.ai_config import (
    AIConfiguration,
    DefaultAIConfig,
    load_ai_config_from_env,
    validate_ai_config,
    AIConfigManager,
)
from app.device_service import (
    AIModelFactory,
    DeviceRecognitionService,
    MockAIService,
    create_device_recognition_service,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(coro):
    """Run a coroutine synchronously for use in sync test functions."""
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
# Unit tests: MockAIService (Requirement 9.2)
# ---------------------------------------------------------------------------


class TestMockAIService:
    """Unit tests for MockAIService."""

    def test_initialize_returns_true(self):
        """MockAIService.initialize should return True."""
        svc = MockAIService()
        config = ModelConfiguration(
            model_name="test",
            model_path="",
            model_type=ModelType.ONNX,
            input_size=(640, 640),
            confidence_threshold=0.7,
            batch_size=1,
            device="cpu",
            preprocessing_config={},
        )
        result = run(svc.initialize(config))
        assert result is True

    def test_is_available_after_initialize(self):
        """MockAIService should be available after initialization."""
        svc = _make_mock_service()
        assert svc.is_available() is True

    def test_is_not_available_before_initialize(self):
        """MockAIService should not be available before initialization."""
        svc = MockAIService()
        assert svc.is_available() is False

    def test_process_image_returns_result(self):
        """process_image should return a DeviceRecognitionResult."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x00" * 100  # Minimal JPEG-like bytes
        result = run(svc.process_image(image_data))
        assert isinstance(result, DeviceRecognitionResult)

    def test_process_image_confidence_in_range(self):
        """process_image confidence should be between 0 and 1."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\xab" * 50
        result = run(svc.process_image(image_data))
        assert 0.0 <= result.confidence <= 1.0

    def test_process_image_deterministic(self):
        """Same image bytes should always produce the same result."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x42" * 200
        result1 = run(svc.process_image(image_data))
        result2 = run(svc.process_image(image_data))
        assert result1.device_id == result2.device_id
        assert result1.device_name == result2.device_name
        assert result1.confidence == result2.confidence

    def test_process_image_different_inputs_may_differ(self):
        """Different image bytes should (generally) produce different results."""
        svc = _make_mock_service()
        # Use images that hash to different first bytes
        image_a = b"\xff\xd8\xff" + bytes(range(256))
        image_b = b"\xff\xd8\xff" + bytes(reversed(range(256)))
        result_a = run(svc.process_image(image_a))
        result_b = run(svc.process_image(image_b))
        # They may or may not differ, but both must be valid results
        assert isinstance(result_a, DeviceRecognitionResult)
        assert isinstance(result_b, DeviceRecognitionResult)

    def test_process_image_has_device_name(self):
        """process_image result should include a device name."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x01" * 100
        result = run(svc.process_image(image_data))
        assert result.device_name is not None
        assert len(result.device_name) > 0

    def test_process_image_has_manufacturer(self):
        """process_image result should include a manufacturer."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x02" * 100
        result = run(svc.process_image(image_data))
        assert result.manufacturer is not None
        assert len(result.manufacturer) > 0

    def test_process_image_has_alternative_matches(self):
        """process_image result should include alternative matches."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x03" * 100
        result = run(svc.process_image(image_data))
        assert isinstance(result.alternative_matches, list)
        assert len(result.alternative_matches) > 0

    def test_extract_qr_code_returns_result(self):
        """extract_qr_code should return a QRCodeResult."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x10" * 100
        result = run(svc.extract_qr_code(image_data))
        assert isinstance(result, QRCodeResult)

    def test_extract_qr_code_has_content(self):
        """extract_qr_code result should have non-empty content."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x20" * 100
        result = run(svc.extract_qr_code(image_data))
        assert len(result.content) > 0

    def test_extract_qr_code_confidence_in_range(self):
        """extract_qr_code confidence should be between 0 and 1."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x30" * 100
        result = run(svc.extract_qr_code(image_data))
        assert 0.0 <= result.confidence <= 1.0

    def test_extract_qr_code_deterministic(self):
        """Same image bytes should always produce the same QR result."""
        svc = _make_mock_service()
        image_data = b"\xff\xd8\xff" + b"\x55" * 100
        result1 = run(svc.extract_qr_code(image_data))
        result2 = run(svc.extract_qr_code(image_data))
        assert result1.content == result2.content
        assert result1.confidence == result2.confidence

    def test_get_model_info_returns_info(self):
        """get_model_info should return a ModelInfo object."""
        svc = _make_mock_service()
        info = svc.get_model_info()
        assert isinstance(info, ModelInfo)
        assert info.model_name == "MockDeviceRecognitionModel"
        assert info.version == "1.0.0-mock"

    def test_implements_ai_model_interface(self):
        """MockAIService should be an instance of AIModelInterface."""
        svc = MockAIService()
        assert isinstance(svc, AIModelInterface)


# ---------------------------------------------------------------------------
# Unit tests: AIModelFactory (Requirement 9.4)
# ---------------------------------------------------------------------------


class TestAIModelFactory:
    """Unit tests for AIModelFactory."""

    def test_creates_mock_service_when_use_mock_true(self):
        """Factory should return MockAIService when use_mock=True."""
        config = AIConfiguration(use_mock=True, model_available=False)
        service = AIModelFactory.create_ai_service(config)
        assert isinstance(service, MockAIService)

    def test_creates_mock_service_when_model_not_available(self):
        """Factory should return MockAIService when model_available=False."""
        config = AIConfiguration(use_mock=False, model_available=False)
        service = AIModelFactory.create_ai_service(config)
        assert isinstance(service, MockAIService)

    def test_creates_mock_service_with_default_config(self):
        """Factory should return MockAIService with default configuration."""
        config = DefaultAIConfig.get_default_config()
        service = AIModelFactory.create_ai_service(config)
        assert isinstance(service, MockAIService)

    def test_fallback_to_mock_when_no_model_config(self):
        """Factory should fall back to mock when ai_model_config is None and fallback enabled."""
        config = AIConfiguration(
            use_mock=False,
            model_available=True,
            ai_model_config=None,
            fallback_enabled=True,
        )
        service = AIModelFactory.create_ai_service(config)
        assert isinstance(service, MockAIService)

    def test_raises_when_no_model_config_and_no_fallback(self):
        """Factory should raise ValueError when ai_model_config is None and fallback disabled."""
        config = AIConfiguration(
            use_mock=False,
            model_available=True,
            ai_model_config=None,
            fallback_enabled=False,
        )
        with pytest.raises(ValueError, match="model_config must be provided"):
            AIModelFactory.create_ai_service(config)

    def test_onnx_falls_back_to_mock_when_fallback_enabled(self):
        """Factory should fall back to mock for ONNX when fallback enabled."""
        model_cfg = ModelConfiguration(
            model_name="test-onnx",
            model_path="/nonexistent/model.onnx",
            model_type=ModelType.ONNX,
            input_size=(640, 640),
            confidence_threshold=0.7,
            batch_size=1,
            device="cpu",
            preprocessing_config={},
        )
        config = AIConfiguration(
            use_mock=False,
            model_available=True,
            ai_model_config=model_cfg,
            fallback_enabled=True,
        )
        service = AIModelFactory.create_ai_service(config)
        assert isinstance(service, MockAIService)

    def test_tensorflow_falls_back_to_mock_when_fallback_enabled(self):
        """Factory should fall back to mock for TensorFlow when fallback enabled."""
        model_cfg = ModelConfiguration(
            model_name="test-tf",
            model_path="/nonexistent/model.pb",
            model_type=ModelType.TENSORFLOW,
            input_size=(640, 640),
            confidence_threshold=0.7,
            batch_size=1,
            device="cpu",
            preprocessing_config={},
        )
        config = AIConfiguration(
            use_mock=False,
            model_available=True,
            ai_model_config=model_cfg,
            fallback_enabled=True,
        )
        service = AIModelFactory.create_ai_service(config)
        assert isinstance(service, MockAIService)

    def test_pytorch_falls_back_to_mock_when_fallback_enabled(self):
        """Factory should fall back to mock for PyTorch when fallback enabled."""
        model_cfg = ModelConfiguration(
            model_name="test-pt",
            model_path="/nonexistent/model.pt",
            model_type=ModelType.PYTORCH,
            input_size=(640, 640),
            confidence_threshold=0.7,
            batch_size=1,
            device="cpu",
            preprocessing_config={},
        )
        config = AIConfiguration(
            use_mock=False,
            model_available=True,
            ai_model_config=model_cfg,
            fallback_enabled=True,
        )
        service = AIModelFactory.create_ai_service(config)
        assert isinstance(service, MockAIService)

    def test_huggingface_falls_back_to_mock_when_fallback_enabled(self):
        """Factory should fall back to mock for HuggingFace when fallback enabled."""
        model_cfg = ModelConfiguration(
            model_name="test-hf",
            model_path="bert-base-uncased",
            model_type=ModelType.HUGGINGFACE,
            input_size=(640, 640),
            confidence_threshold=0.7,
            batch_size=1,
            device="cpu",
            preprocessing_config={},
        )
        config = AIConfiguration(
            use_mock=False,
            model_available=True,
            ai_model_config=model_cfg,
            fallback_enabled=True,
        )
        service = AIModelFactory.create_ai_service(config)
        assert isinstance(service, MockAIService)


# ---------------------------------------------------------------------------
# Unit tests: DeviceRecognitionService
# ---------------------------------------------------------------------------


class TestDeviceRecognitionService:
    """Unit tests for DeviceRecognitionService."""

    def _make_service(self, **kwargs) -> DeviceRecognitionService:
        config = DefaultAIConfig.get_default_config()
        for k, v in kwargs.items():
            setattr(config, k, v)
        svc = create_device_recognition_service(config)
        run(svc.initialize())
        return svc

    def test_initialize_returns_true(self):
        """DeviceRecognitionService.initialize should return True."""
        svc = create_device_recognition_service()
        result = run(svc.initialize())
        assert result is True

    def test_is_available_after_initialize(self):
        """Service should be available after initialization."""
        svc = self._make_service()
        assert svc.is_available() is True

    def test_recognize_device_valid_jpeg(self):
        """recognize_device_from_photo should work with valid JPEG bytes."""
        svc = self._make_service()
        # Minimal JPEG magic bytes + padding
        image_data = b"\xff\xd8\xff" + b"\x00" * 200
        result = run(svc.recognize_device_from_photo(image_data))
        assert isinstance(result, DeviceRecognitionResult)

    def test_recognize_device_valid_png(self):
        """recognize_device_from_photo should work with valid PNG bytes."""
        svc = self._make_service()
        image_data = b"\x89PNG" + b"\x00" * 200
        result = run(svc.recognize_device_from_photo(image_data))
        assert isinstance(result, DeviceRecognitionResult)

    def test_recognize_device_valid_webp(self):
        """recognize_device_from_photo should work with valid WebP bytes."""
        svc = self._make_service()
        # WebP: RIFF....WEBP
        image_data = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 200
        result = run(svc.recognize_device_from_photo(image_data))
        assert isinstance(result, DeviceRecognitionResult)

    def test_recognize_device_too_large_returns_error(self):
        """recognize_device_from_photo should return error for oversized images."""
        svc = self._make_service()
        # 11 MB image
        image_data = b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)
        result = run(svc.recognize_device_from_photo(image_data))
        assert result.error_message is not None
        assert "exceeds maximum" in result.error_message

    def test_recognize_device_empty_returns_error(self):
        """recognize_device_from_photo should return error for empty bytes."""
        svc = self._make_service()
        result = run(svc.recognize_device_from_photo(b""))
        assert result.error_message is not None

    def test_recognize_device_unsupported_format_returns_error(self):
        """recognize_device_from_photo should return error for unsupported formats."""
        svc = self._make_service()
        # Random bytes that don't match any supported format
        image_data = b"\x00\x01\x02\x03" * 100
        result = run(svc.recognize_device_from_photo(image_data))
        assert result.error_message is not None

    def test_recognize_device_low_confidence_sets_error_message(self):
        """Results below threshold should have an error message set."""
        svc = self._make_service(confidence_threshold=0.99)
        image_data = b"\xff\xd8\xff" + b"\x00" * 200
        result = run(svc.recognize_device_from_photo(image_data, confidence_threshold=0.99))
        # Mock confidence is at most 0.92, so this should trigger the threshold message
        if result.confidence < 0.99:
            assert result.error_message is not None
            assert "threshold" in result.error_message

    def test_decode_qr_code_valid_image(self):
        """decode_qr_code should return a QRCodeResult for valid images."""
        svc = self._make_service()
        image_data = b"\xff\xd8\xff" + b"\x00" * 200
        result = run(svc.decode_qr_code(image_data))
        assert isinstance(result, QRCodeResult)

    def test_decode_qr_code_disabled_returns_empty(self):
        """decode_qr_code should return empty result when QR detection is disabled."""
        svc = self._make_service(qr_detection_enabled=False)
        image_data = b"\xff\xd8\xff" + b"\x00" * 200
        result = run(svc.decode_qr_code(image_data))
        assert result.content == ""
        assert result.confidence == 0.0

    def test_get_service_info_returns_dict(self):
        """get_service_info should return a dictionary with expected keys."""
        svc = self._make_service()
        info = svc.get_service_info()
        assert isinstance(info, dict)
        assert "service_type" in info
        assert "is_mock" in info
        assert "initialized" in info
        assert "model_name" in info
        assert "confidence_threshold" in info

    def test_get_service_info_is_mock_true(self):
        """get_service_info should report is_mock=True for default config."""
        svc = self._make_service()
        info = svc.get_service_info()
        assert info["is_mock"] is True


# ---------------------------------------------------------------------------
# Unit tests: AIConfiguration (Requirement 9.5)
# ---------------------------------------------------------------------------


class TestAIConfiguration:
    """Unit tests for AI configuration management."""

    def test_default_config_uses_mock(self):
        """Default configuration should use mock service."""
        config = DefaultAIConfig.get_default_config()
        assert config.use_mock is True

    def test_default_config_model_not_available(self):
        """Default configuration should have model_available=False."""
        config = DefaultAIConfig.get_default_config()
        assert config.model_available is False

    def test_default_config_fallback_enabled(self):
        """Default configuration should have fallback enabled."""
        config = DefaultAIConfig.get_default_config()
        assert config.fallback_enabled is True

    def test_default_config_qr_detection_enabled(self):
        """Default configuration should have QR detection enabled."""
        config = DefaultAIConfig.get_default_config()
        assert config.qr_detection_enabled is True

    def test_default_config_confidence_threshold_valid(self):
        """Default confidence threshold should be between 0 and 1."""
        config = DefaultAIConfig.get_default_config()
        assert 0.0 <= config.confidence_threshold <= 1.0

    def test_default_config_max_concurrent_requests_positive(self):
        """Default max_concurrent_requests should be positive."""
        config = DefaultAIConfig.get_default_config()
        assert config.max_concurrent_requests >= 1

    def test_default_config_request_timeout_positive(self):
        """Default request_timeout should be positive."""
        config = DefaultAIConfig.get_default_config()
        assert config.request_timeout > 0

    def test_validate_config_no_issues_for_default(self):
        """Default configuration should pass validation (ignoring directory creation)."""
        config = DefaultAIConfig.get_default_config()
        # Override directories to temp paths to avoid filesystem side effects
        config.models_directory = "/tmp/test-ai-models"
        config.cache_directory = "/tmp/test-ai-cache"
        issues = validate_ai_config(config)
        assert issues == []

    def test_validate_config_detects_missing_model_config(self):
        """Validation should flag missing model_config when not using mock."""
        config = AIConfiguration(
            use_mock=False,
            model_available=True,
            ai_model_config=None,
            models_directory="/tmp/test-ai-models",
            cache_directory="/tmp/test-ai-cache",
        )
        issues = validate_ai_config(config)
        assert any("Model configuration required" in issue for issue in issues)

    def test_config_manager_returns_config(self):
        """AIConfigManager should return a valid AIConfiguration."""
        manager = AIConfigManager()
        config = manager.get_config()
        assert isinstance(config, AIConfiguration)

    def test_config_manager_is_mock_mode(self):
        """AIConfigManager.is_mock_mode should return True for default config."""
        manager = AIConfigManager()
        assert manager.is_mock_mode() is True

    def test_config_manager_model_not_available(self):
        """AIConfigManager.is_model_available should return False for default config."""
        manager = AIConfigManager()
        assert manager.is_model_available() is False

    def test_create_model_config_factory(self):
        """DefaultAIConfig.create_model_config should create a valid ModelConfiguration."""
        model_cfg = DefaultAIConfig.create_model_config(
            model_name="test-model",
            model_path="/path/to/model.onnx",
            model_type=ModelType.ONNX,
        )
        assert model_cfg.model_name == "test-model"
        assert model_cfg.model_type == ModelType.ONNX
        assert 0.0 <= model_cfg.confidence_threshold <= 1.0


# ---------------------------------------------------------------------------
# Property-based tests (Task 2.1)
# ---------------------------------------------------------------------------


# Property 27: AI Mock Service Responses
# Validates: Requirements 9.2

@given(st.binary(min_size=3, max_size=1024))
@settings(max_examples=25)
def test_mock_service_confidence_always_in_range(image_bytes):
    """
    **Validates: Requirements 9.2**

    Property 27: For any image bytes, MockAIService.process_image returns a
    DeviceRecognitionResult with confidence in [0.0, 1.0].
    """
    svc = _make_mock_service()
    result = run(svc.process_image(image_bytes))
    assert 0.0 <= result.confidence <= 1.0, (
        f"confidence={result.confidence} is outside [0.0, 1.0]"
    )


@given(st.binary(min_size=3, max_size=1024))
@settings(max_examples=25)
def test_mock_service_deterministic_for_same_input(image_bytes):
    """
    **Validates: Requirements 9.2**

    Property 27: MockAIService.process_image is deterministic — the same
    image bytes always produce the same device_id and device_name.
    """
    svc = _make_mock_service()
    result1 = run(svc.process_image(image_bytes))
    result2 = run(svc.process_image(image_bytes))
    assert result1.device_id == result2.device_id, (
        f"device_id changed between calls: {result1.device_id!r} vs {result2.device_id!r}"
    )
    assert result1.device_name == result2.device_name, (
        f"device_name changed between calls: {result1.device_name!r} vs {result2.device_name!r}"
    )


@given(st.binary(min_size=3, max_size=1024))
@settings(max_examples=25)
def test_mock_service_qr_confidence_always_in_range(image_bytes):
    """
    **Validates: Requirements 9.2**

    Property 27: For any image bytes, MockAIService.extract_qr_code returns a
    QRCodeResult with confidence in [0.0, 1.0].
    """
    svc = _make_mock_service()
    result = run(svc.extract_qr_code(image_bytes))
    assert 0.0 <= result.confidence <= 1.0, (
        f"QR confidence={result.confidence} is outside [0.0, 1.0]"
    )


@given(st.binary(min_size=3, max_size=1024))
@settings(max_examples=25)
def test_mock_service_qr_deterministic_for_same_input(image_bytes):
    """
    **Validates: Requirements 9.2**

    Property 27: MockAIService.extract_qr_code is deterministic — the same
    image bytes always produce the same QR content.
    """
    svc = _make_mock_service()
    result1 = run(svc.extract_qr_code(image_bytes))
    result2 = run(svc.extract_qr_code(image_bytes))
    assert result1.content == result2.content, (
        f"QR content changed between calls: {result1.content!r} vs {result2.content!r}"
    )


# Property 28: AI Model Format Support
# Validates: Requirements 9.4

@given(st.sampled_from(list(ModelType)))
@settings(max_examples=25)
def test_factory_handles_all_model_types_with_fallback(model_type):
    """
    **Validates: Requirements 9.4**

    Property 28: AIModelFactory.create_ai_service handles all ModelType values
    without raising an exception when fallback_enabled=True.
    """
    model_cfg = ModelConfiguration(
        model_name="test-model",
        model_path="/nonexistent/model",
        model_type=model_type,
        input_size=(640, 640),
        confidence_threshold=0.7,
        batch_size=1,
        device="cpu",
        preprocessing_config={},
    )
    config = AIConfiguration(
        use_mock=False,
        model_available=True,
        ai_model_config=model_cfg,
        fallback_enabled=True,
    )
    # Should not raise — falls back to mock
    service = AIModelFactory.create_ai_service(config)
    assert isinstance(service, AIModelInterface)


# Property 29: AI Configuration Management
# Validates: Requirements 9.5

@given(
    st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    st.integers(min_value=1, max_value=100),
    st.floats(min_value=0.1, max_value=300.0, allow_nan=False),
)
@settings(max_examples=25)
def test_ai_config_valid_parameters_pass_validation(
    confidence_threshold, max_concurrent_requests, request_timeout
):
    """
    **Validates: Requirements 9.5**

    Property 29: AIConfiguration with valid parameter ranges passes validation
    without issues related to those parameters.
    """
    config = AIConfiguration(
        use_mock=True,
        model_available=False,
        confidence_threshold=confidence_threshold,
        max_concurrent_requests=max_concurrent_requests,
        request_timeout=request_timeout,
        models_directory="/tmp/test-ai-models",
        cache_directory="/tmp/test-ai-cache",
    )
    issues = validate_ai_config(config)
    # Should have no issues for valid parameter ranges
    param_issues = [
        i for i in issues
        if "Confidence threshold" in i
        or "Max concurrent requests" in i
        or "Request timeout" in i
    ]
    assert param_issues == [], (
        f"Unexpected validation issues for valid params: {param_issues}"
    )


@given(st.booleans(), st.booleans())
@settings(max_examples=25)
def test_factory_always_returns_ai_model_interface(use_mock, fallback_enabled):
    """
    **Validates: Requirements 9.5**

    Property 29: AIModelFactory.create_ai_service always returns an object
    that implements AIModelInterface, regardless of configuration flags.
    """
    config = AIConfiguration(
        use_mock=use_mock,
        model_available=False,  # No real model available
        fallback_enabled=fallback_enabled,
    )
    service = AIModelFactory.create_ai_service(config)
    assert isinstance(service, AIModelInterface), (
        f"Expected AIModelInterface, got {type(service).__name__}"
    )

