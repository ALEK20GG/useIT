"""
AI model interfaces and data structures for device recognition.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field


class ModelType(str, Enum):
    """Supported AI model formats."""
    
    ONNX = "onnx"
    TENSORFLOW = "tensorflow"
    PYTORCH = "pytorch"
    HUGGINGFACE = "huggingface"


class IdentifierType(str, Enum):
    """Device identifier types."""
    
    QR_CODE = "qr_code"
    BARCODE = "barcode"
    MODEL_NUMBER = "model_number"
    SERIAL_NUMBER = "serial_number"
    VISUAL_RECOGNITION = "visual_recognition"


class QRCodeFormat(str, Enum):
    """Supported QR code formats."""
    
    STANDARD = "standard"
    MICRO = "micro"
    DATA_MATRIX = "data_matrix"


class DevicePhoto(BaseModel):
    """Device photo capture data."""
    
    image_data: bytes = Field(description="Raw image data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Camera metadata")


class QRCodeResult(BaseModel):
    """QR code scanning result."""
    
    content: str = Field(description="Decoded QR code content")
    format: QRCodeFormat = Field(description="QR code format")
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence")
    bounding_box: Optional[Tuple[int, int, int, int]] = Field(None, description="Bounding box coordinates")


class DeviceMatch(BaseModel):
    """Alternative device match result."""
    
    device_id: str = Field(description="Device identifier")
    device_name: str = Field(description="Device name")
    manufacturer: str = Field(description="Manufacturer name")
    model: str = Field(description="Device model")
    confidence: float = Field(ge=0.0, le=1.0, description="Match confidence")
    similarity_reasons: List[str] = Field(default_factory=list, description="Reasons for similarity")


class DeviceRecognitionResult(BaseModel):
    """Device recognition result from AI processing."""
    
    device_id: Optional[str] = Field(None, description="Unique device identifier")
    device_name: Optional[str] = Field(None, description="Recognized device name")
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    model: Optional[str] = Field(None, description="Device model")
    confidence: float = Field(ge=0.0, le=1.0, description="Recognition confidence")
    alternative_matches: List[DeviceMatch] = Field(default_factory=list, description="Alternative matches")
    processing_time_ms: float = Field(default=0.0, description="Processing time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if recognition failed")


class ModelConfiguration(BaseModel):
    """AI model configuration structure."""

    model_config = {"protected_namespaces": ()}  # Allow model_* field names

    model_name: str = Field(description="Model identifier")
    model_path: str = Field(description="Path to model file")
    model_type: ModelType = Field(description="Model format type")
    input_size: Tuple[int, int] = Field(description="Expected input image size (width, height)")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold")
    batch_size: int = Field(default=1, ge=1, description="Processing batch size")
    device: str = Field(default="cpu", description="Processing device (cpu, cuda, mps)")
    preprocessing_config: Dict[str, Any] = Field(default_factory=dict, description="Preprocessing parameters")


class ModelInfo(BaseModel):
    """AI model metadata and capabilities."""

    model_config = {"protected_namespaces": ()}  # Allow model_* field names

    model_name: str = Field(description="Model name")
    model_type: ModelType = Field(description="Model format")
    version: str = Field(description="Model version")
    input_size: Tuple[int, int] = Field(description="Input image size")
    supported_devices: List[str] = Field(description="Supported device categories")
    accuracy_metrics: Dict[str, float] = Field(default_factory=dict, description="Model accuracy metrics")
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImagePreprocessingConfig(BaseModel):
    """Image preprocessing configuration."""
    
    resize_enabled: bool = Field(default=True, description="Enable image resizing")
    target_size: Tuple[int, int] = Field(default=(640, 640), description="Target image size")
    normalize: bool = Field(default=True, description="Normalize pixel values")
    enhance_contrast: bool = Field(default=True, description="Enhance image contrast")
    noise_reduction: bool = Field(default=False, description="Apply noise reduction")
    rotation_correction: bool = Field(default=True, description="Correct image rotation")


class AIModelInterface(ABC):
    """Abstract interface for AI model integration."""
    
    @abstractmethod
    async def initialize(self, config: ModelConfiguration) -> bool:
        """Initialize the AI model with configuration.
        
        Args:
            config: Model configuration parameters
            
        Returns:
            True if initialization successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def process_image(self, image_data: bytes) -> DeviceRecognitionResult:
        """Process device image for recognition.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Device recognition result with confidence and alternatives
        """
        pass
    
    @abstractmethod
    async def extract_qr_code(self, image_data: bytes) -> QRCodeResult:
        """Extract and decode QR code from image.
        
        Args:
            image_data: Raw image bytes containing QR code
            
        Returns:
            QR code content and metadata
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> ModelInfo:
        """Return model metadata and capabilities.
        
        Returns:
            Model information including version and capabilities
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if model is loaded and available for processing.
        
        Returns:
            True if model is ready, False otherwise
        """
        pass


class CameraMetadata(BaseModel):
    """Camera capture metadata."""
    
    camera_id: Optional[str] = Field(None, description="Camera device identifier")
    resolution: Optional[Tuple[int, int]] = Field(None, description="Image resolution")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    flash_used: bool = Field(default=False, description="Whether flash was used")
    focus_mode: Optional[str] = Field(None, description="Camera focus mode")
    exposure_settings: Dict[str, Any] = Field(default_factory=dict, description="Exposure settings")


class ProcessingMetrics(BaseModel):
    """AI processing performance metrics."""
    
    processing_time_ms: float = Field(description="Total processing time")
    preprocessing_time_ms: float = Field(description="Image preprocessing time")
    inference_time_ms: float = Field(description="Model inference time")
    postprocessing_time_ms: float = Field(description="Result postprocessing time")
    memory_usage_mb: float = Field(description="Peak memory usage")
    gpu_utilization: Optional[float] = Field(None, description="GPU utilization percentage")