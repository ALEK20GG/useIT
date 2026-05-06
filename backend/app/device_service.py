"""
AI mock service, model factory, and device recognition service.

Implements Requirements 9.1-9.5:
- 9.1: Clear interfaces for AI model integration
- 9.2: Mock AI service for development and testing
- 9.3: Model loading and initialization during startup
- 9.4: Support for different model formats (ONNX, TensorFlow, PyTorch)
- 9.5: Configuration options for AI model parameters
"""

import asyncio
import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .ai_models import (
    AIModelInterface,
    DeviceMatch,
    DeviceRecognitionResult,
    ModelConfiguration,
    ModelInfo,
    ModelType,
    QRCodeFormat,
    QRCodeResult,
)
from .ai_config import AIConfiguration, DefaultAIConfig, get_ai_config


# ---------------------------------------------------------------------------
# Mock AI Service (Requirement 9.2)
# ---------------------------------------------------------------------------

class MockAIService(AIModelInterface):
    """
    Mock AI service for development and testing.

    Returns deterministic results based on image content hash so that
    the same image always produces the same recognition result.
    """

    _MOCK_DEVICES = [
        {
            "name": "Arduino Uno R3",
            "manufacturer": "Arduino",
            "model": "Uno R3",
            "confidence": 0.85,
            "category": "microcontroller",
        },
        {
            "name": "Raspberry Pi 4",
            "manufacturer": "Raspberry Pi Foundation",
            "model": "Pi 4 Model B",
            "confidence": 0.92,
            "category": "single-board-computer",
        },
        {
            "name": "ESP32 DevKit",
            "manufacturer": "Espressif",
            "model": "ESP32-WROOM-32",
            "confidence": 0.78,
            "category": "microcontroller",
        },
        {
            "name": "STM32 Nucleo",
            "manufacturer": "STMicroelectronics",
            "model": "NUCLEO-F401RE",
            "confidence": 0.81,
            "category": "microcontroller",
        },
        {
            "name": "Jetson Nano",
            "manufacturer": "NVIDIA",
            "model": "Jetson Nano Developer Kit",
            "confidence": 0.88,
            "category": "ai-accelerator",
        },
    ]

    _MOCK_QR_CONTENTS = [
        "https://arduino.cc/en/Main/ArduinoBoardUno",
        "https://www.raspberrypi.com/products/raspberry-pi-4-model-b/",
        "https://www.espressif.com/en/products/socs/esp32",
        "DEVICE:STM32-NUCLEO-F401RE:SN123456",
        "DEVICE:ARDUINO-UNO-R3:SN789012",
    ]

    def __init__(self) -> None:
        self._initialized = False
        self._config: Optional[ModelConfiguration] = None
        self._loaded_at: Optional[datetime] = None

    async def initialize(self, config: ModelConfiguration) -> bool:
        """Simulate model initialization with a short delay."""
        await asyncio.sleep(0.05)  # Simulate loading time
        self._config = config
        self._initialized = True
        self._loaded_at = datetime.now(timezone.utc)
        return True

    async def process_image(self, image_data: bytes) -> DeviceRecognitionResult:
        """
        Return deterministic mock device recognition results.

        The selected device is determined by the MD5 hash of the image bytes,
        ensuring the same image always returns the same result.
        """
        start_time = time.monotonic()

        # Simulate processing delay
        await asyncio.sleep(0.02)

        image_hash = hashlib.md5(image_data).hexdigest()

        # Select primary device based on first byte of hash
        primary_idx = int(image_hash[:2], 16) % len(self._MOCK_DEVICES)
        primary = self._MOCK_DEVICES[primary_idx]

        # Build alternative matches (next 2 devices in the list)
        alternatives: List[DeviceMatch] = []
        for offset in range(1, 3):
            alt_idx = (primary_idx + offset) % len(self._MOCK_DEVICES)
            alt = self._MOCK_DEVICES[alt_idx]
            alternatives.append(
                DeviceMatch(
                    device_id=f"mock_{image_hash[offset * 2:(offset + 1) * 2]}",
                    device_name=alt["name"],
                    manufacturer=alt["manufacturer"],
                    model=alt["model"],
                    confidence=max(0.0, alt["confidence"] - 0.15 * offset),
                    similarity_reasons=["visual_similarity", "category_match"],
                )
            )

        elapsed_ms = (time.monotonic() - start_time) * 1000

        return DeviceRecognitionResult(
            device_id=f"mock_{image_hash[:8]}",
            device_name=primary["name"],
            manufacturer=primary["manufacturer"],
            model=primary["model"],
            confidence=primary["confidence"],
            alternative_matches=alternatives,
            processing_time_ms=elapsed_ms,
        )

    async def extract_qr_code(self, image_data: bytes) -> QRCodeResult:
        """
        Return deterministic mock QR code extraction results.

        The selected QR content is determined by the MD5 hash of the image bytes.
        """
        await asyncio.sleep(0.01)  # Simulate processing delay

        image_hash = hashlib.md5(image_data).hexdigest()
        qr_idx = int(image_hash[:2], 16) % len(self._MOCK_QR_CONTENTS)
        content = self._MOCK_QR_CONTENTS[qr_idx]

        return QRCodeResult(
            content=content,
            format=QRCodeFormat.STANDARD,
            confidence=0.95,
            bounding_box=(10, 10, 200, 200),
        )

    def get_model_info(self) -> ModelInfo:
        """Return mock model metadata."""
        return ModelInfo(
            model_name="MockDeviceRecognitionModel",
            model_type=ModelType.PYTORCH,
            version="1.0.0-mock",
            input_size=(640, 640),
            supported_devices=[
                "microcontroller",
                "single-board-computer",
                "ai-accelerator",
                "sensor",
                "actuator",
            ],
            accuracy_metrics={
                "top1_accuracy": 0.0,  # Mock – not a real model
                "top5_accuracy": 0.0,
            },
            loaded_at=self._loaded_at or datetime.now(timezone.utc),
        )

    def is_available(self) -> bool:
        """Mock service is always available once initialized."""
        return self._initialized


# ---------------------------------------------------------------------------
# AI Model Factory (Requirement 9.4)
# ---------------------------------------------------------------------------

class AIModelFactory:
    """
    Factory for creating the appropriate AI service instance.

    Selects between the mock service and real model implementations based
    on the provided AIConfiguration.  Real model adapters (ONNX, TensorFlow,
    PyTorch) are placeholders that raise NotImplementedError until the
    corresponding libraries are installed and models are available.
    """

    @staticmethod
    def create_ai_service(config: AIConfiguration) -> AIModelInterface:
        """
        Create and return an AI service instance.

        Args:
            config: AI system configuration.

        Returns:
            An AIModelInterface implementation appropriate for the config.
        """
        # Use mock when explicitly requested or when no real model is available
        if config.use_mock or not config.model_available:
            return MockAIService()

        # Real model path – requires ai_model_config to be set
        if config.ai_model_config is None:
            # Fallback to mock if no model config provided
            if config.fallback_enabled:
                return MockAIService()
            raise ValueError(
                "model_config must be provided when use_mock=False and model_available=True"
            )

        model_type = config.ai_model_config.model_type

        if model_type == ModelType.ONNX:
            return AIModelFactory._create_onnx_service(config)
        elif model_type == ModelType.TENSORFLOW:
            return AIModelFactory._create_tensorflow_service(config)
        elif model_type == ModelType.PYTORCH:
            return AIModelFactory._create_pytorch_service(config)
        elif model_type == ModelType.HUGGINGFACE:
            return AIModelFactory._create_huggingface_service(config)
        else:
            if config.fallback_enabled:
                return MockAIService()
            raise ValueError(f"Unsupported model type: {model_type}")

    @staticmethod
    def _create_onnx_service(config: AIConfiguration) -> AIModelInterface:
        """Create ONNX-based device recognition service (placeholder)."""
        # Placeholder: fall back to mock until ONNX runtime is integrated
        if config.fallback_enabled:
            return MockAIService()
        raise NotImplementedError(
            "ONNX device recognition service is not yet implemented. "
            "Set use_mock=True or fallback_enabled=True to use the mock service."
        )

    @staticmethod
    def _create_tensorflow_service(config: AIConfiguration) -> AIModelInterface:
        """Create TensorFlow-based device recognition service (placeholder)."""
        if config.fallback_enabled:
            return MockAIService()
        raise NotImplementedError(
            "TensorFlow device recognition service is not yet implemented. "
            "Set use_mock=True or fallback_enabled=True to use the mock service."
        )

    @staticmethod
    def _create_pytorch_service(config: AIConfiguration) -> AIModelInterface:
        """Create PyTorch-based device recognition service (placeholder)."""
        if config.fallback_enabled:
            return MockAIService()
        raise NotImplementedError(
            "PyTorch device recognition service is not yet implemented. "
            "Set use_mock=True or fallback_enabled=True to use the mock service."
        )

    @staticmethod
    def _create_huggingface_service(config: AIConfiguration) -> AIModelInterface:
        """Create HuggingFace-based device recognition service (placeholder)."""
        if config.fallback_enabled:
            return MockAIService()
        raise NotImplementedError(
            "HuggingFace device recognition service is not yet implemented. "
            "Set use_mock=True or fallback_enabled=True to use the mock service."
        )


# ---------------------------------------------------------------------------
# Device Recognition Service
# ---------------------------------------------------------------------------

class DeviceRecognitionService:
    """
    High-level service for device recognition from photos and QR codes.

    Wraps the underlying AI service and adds:
    - Confidence threshold filtering
    - Image format validation
    - Error handling and fallback logic
    - Processing metrics collection
    """

    # Supported image MIME types / magic bytes prefixes
    _SUPPORTED_FORMATS = {
        b"\xff\xd8\xff": "image/jpeg",
        b"\x89PNG": "image/png",
        b"RIFF": "image/webp",  # WebP starts with RIFF....WEBP
        b"GIF8": "image/gif",
    }

    # Maximum image size: 10 MB (Requirement 1.5)
    MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

    def __init__(
        self,
        ai_service: AIModelInterface,
        config: Optional[AIConfiguration] = None,
    ) -> None:
        self._ai_service = ai_service
        self._config = config or DefaultAIConfig.get_default_config()
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Initialize the underlying AI service.

        Called during application startup (Requirement 9.3).
        """
        if self._config.ai_model_config:
            success = await self._ai_service.initialize(self._config.ai_model_config)
        else:
            # Use a default config for mock initialization
            default_model_config = ModelConfiguration(
                model_name="mock-device-recognition",
                model_path="",
                model_type=ModelType.PYTORCH,
                input_size=(640, 640),
                confidence_threshold=self._config.confidence_threshold,
                batch_size=1,
                device="cpu",
                preprocessing_config={},
            )
            success = await self._ai_service.initialize(default_model_config)

        self._initialized = success
        return success

    def _validate_image(self, image_data: bytes) -> None:
        """
        Validate image data format and size.

        Raises:
            ValueError: If the image is too large or has an unsupported format.
        """
        if len(image_data) > self.MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Image size {len(image_data)} bytes exceeds maximum "
                f"{self.MAX_IMAGE_SIZE_BYTES} bytes (10 MB)"
            )

        if not image_data:
            raise ValueError("Image data is empty")

        # Check magic bytes for supported formats
        for magic, mime_type in self._SUPPORTED_FORMATS.items():
            if image_data[:len(magic)] == magic:
                return  # Valid format found

        # WebP has RIFF at offset 0 and WEBP at offset 8
        if image_data[:4] == b"RIFF" and image_data[8:12] == b"WEBP":
            return

        raise ValueError(
            "Unsupported image format. Supported formats: JPEG, PNG, WebP, GIF"
        )

    async def recognize_device_from_photo(
        self,
        image_data: bytes,
        confidence_threshold: Optional[float] = None,
    ) -> DeviceRecognitionResult:
        """
        Process a device photo and return identification results.

        Args:
            image_data: Raw image bytes (JPEG, PNG, or WebP).
            confidence_threshold: Override the configured threshold.

        Returns:
            DeviceRecognitionResult with device info and confidence score.
        """
        threshold = confidence_threshold or self._config.confidence_threshold

        try:
            self._validate_image(image_data)
        except ValueError as exc:
            return DeviceRecognitionResult(
                confidence=0.0,
                error_message=str(exc),
            )

        try:
            result = await self._ai_service.process_image(image_data)
        except Exception as exc:  # pragma: no cover
            return DeviceRecognitionResult(
                confidence=0.0,
                error_message=f"AI processing error: {exc}",
            )

        # Filter out low-confidence results
        if result.confidence < threshold:
            result.error_message = (
                f"Recognition confidence {result.confidence:.2f} is below "
                f"threshold {threshold:.2f}"
            )

        return result

    async def decode_qr_code(self, image_data: bytes) -> QRCodeResult:
        """
        Extract and decode a QR code from an image.

        Args:
            image_data: Raw image bytes containing a QR code.

        Returns:
            QRCodeResult with decoded content and metadata.
        """
        if not self._config.qr_detection_enabled:
            return QRCodeResult(
                content="",
                format=QRCodeFormat.STANDARD,
                confidence=0.0,
                bounding_box=None,
            )

        try:
            self._validate_image(image_data)
        except ValueError as exc:
            # Return empty result for invalid images
            return QRCodeResult(
                content="",
                format=QRCodeFormat.STANDARD,
                confidence=0.0,
                bounding_box=None,
            )

        return await self._ai_service.extract_qr_code(image_data)

    def get_service_info(self) -> Dict[str, Any]:
        """Return information about the current AI service and configuration."""
        model_info = self._ai_service.get_model_info()
        return {
            "service_type": type(self._ai_service).__name__,
            "is_mock": isinstance(self._ai_service, MockAIService),
            "initialized": self._initialized,
            "model_name": model_info.model_name,
            "model_type": model_info.model_type.value,
            "model_version": model_info.version,
            "supported_devices": model_info.supported_devices,
            "qr_detection_enabled": self._config.qr_detection_enabled,
            "confidence_threshold": self._config.confidence_threshold,
            "max_concurrent_requests": self._config.max_concurrent_requests,
        }

    def is_available(self) -> bool:
        """Check if the service is initialized and ready."""
        return self._initialized and self._ai_service.is_available()


# ---------------------------------------------------------------------------
# Module-level singleton helpers
# ---------------------------------------------------------------------------

_device_recognition_service: Optional[DeviceRecognitionService] = None


def create_device_recognition_service(
    config: Optional[AIConfiguration] = None,
) -> DeviceRecognitionService:
    """
    Create a DeviceRecognitionService using the provided (or default) config.

    The factory selects the appropriate AI backend automatically.
    """
    ai_config = config or get_ai_config()
    ai_service = AIModelFactory.create_ai_service(ai_config)
    return DeviceRecognitionService(ai_service=ai_service, config=ai_config)


async def get_device_recognition_service() -> DeviceRecognitionService:
    """
    FastAPI dependency that returns the initialized singleton service.

    Initializes the service on first call (Requirement 9.3).
    """
    global _device_recognition_service
    if _device_recognition_service is None:
        _device_recognition_service = create_device_recognition_service()
        await _device_recognition_service.initialize()
    return _device_recognition_service
