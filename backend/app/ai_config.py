"""
AI system configuration management.
"""

import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from .ai_models import ModelConfiguration, ModelType, ImagePreprocessingConfig


class AIConfiguration(BaseModel):
    """Comprehensive AI system configuration."""

    model_config = {"protected_namespaces": ()}  # Allow model_* field names

    use_mock: bool = Field(default=True, description="Use mock AI service during development")
    model_available: bool = Field(default=False, description="Whether AI model is available")
    ai_model_config: Optional[ModelConfiguration] = Field(None, description="AI model configuration")
    fallback_enabled: bool = Field(default=True, description="Enable fallback to mock when model fails")
    performance_monitoring: bool = Field(default=True, description="Enable performance monitoring")
    
    # QR Code processing settings
    qr_detection_enabled: bool = Field(default=True, description="Enable QR code detection")
    qr_libraries: List[str] = Field(default=["pyzbar", "opencv"], description="QR detection libraries")
    
    # Image preprocessing settings
    image_preprocessing: ImagePreprocessingConfig = Field(default_factory=ImagePreprocessingConfig)
    
    # Performance settings
    max_concurrent_requests: int = Field(default=5, ge=1, description="Maximum concurrent AI requests")
    request_timeout: float = Field(default=30.0, gt=0, description="Request timeout in seconds")
    model_warmup: bool = Field(default=True, description="Warm up model on startup")
    
    # Device recognition settings
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence for device recognition")
    max_alternative_matches: int = Field(default=3, ge=0, description="Maximum alternative matches to return")
    
    # Model paths and storage
    models_directory: str = Field(default="backend/storage/ai-models", description="Directory for AI models")
    cache_directory: str = Field(default="backend/storage/ai-cache", description="Directory for AI processing cache")


class DefaultAIConfig:
    """Default AI configuration values and factory methods."""
    
    @staticmethod
    def get_default_config() -> AIConfiguration:
        """Get default AI configuration for development."""
        return AIConfiguration(
            use_mock=True,
            model_available=False,
            fallback_enabled=True,
            performance_monitoring=True,
            qr_detection_enabled=True,
            qr_libraries=["pyzbar", "opencv"],
            image_preprocessing=ImagePreprocessingConfig(
                resize_enabled=True,
                target_size=(640, 640),
                normalize=True,
                enhance_contrast=True,
                noise_reduction=False,
                rotation_correction=True
            ),
            max_concurrent_requests=5,
            request_timeout=30.0,
            model_warmup=True,
            confidence_threshold=0.7,
            max_alternative_matches=3,
            models_directory="backend/storage/ai-models",
            cache_directory="backend/storage/ai-cache"
        )
    
    @staticmethod
    def get_production_config() -> AIConfiguration:
        """Get production AI configuration with real models."""
        config = DefaultAIConfig.get_default_config()
        config.use_mock = False
        config.model_available = True
        config.performance_monitoring = True
        config.model_warmup = True
        return config
    
    @staticmethod
    def create_model_config(
        model_name: str,
        model_path: str,
        model_type: ModelType = ModelType.ONNX,
        input_size: tuple = (640, 640),
        confidence_threshold: float = 0.7
    ) -> ModelConfiguration:
        """Create a model configuration with sensible defaults."""
        return ModelConfiguration(
            model_name=model_name,
            model_path=model_path,
            model_type=model_type,
            input_size=input_size,
            confidence_threshold=confidence_threshold,
            batch_size=1,
            device="cpu",
            preprocessing_config={
                "normalize": True,
                "resize": True,
                "enhance_contrast": True
            }
        )


def load_ai_config_from_env() -> AIConfiguration:
    """Load AI configuration from environment variables."""
    config = DefaultAIConfig.get_default_config()
    
    # Override with environment variables if present
    if os.getenv("AI_USE_MOCK") is not None:
        config.use_mock = os.getenv("AI_USE_MOCK", "true").lower() == "true"
    
    if os.getenv("AI_MODEL_AVAILABLE") is not None:
        config.model_available = os.getenv("AI_MODEL_AVAILABLE", "false").lower() == "true"
    
    if os.getenv("AI_CONFIDENCE_THRESHOLD"):
        try:
            config.confidence_threshold = float(os.getenv("AI_CONFIDENCE_THRESHOLD"))
        except ValueError:
            pass  # Keep default value
    
    if os.getenv("AI_MAX_CONCURRENT_REQUESTS"):
        try:
            config.max_concurrent_requests = int(os.getenv("AI_MAX_CONCURRENT_REQUESTS"))
        except ValueError:
            pass  # Keep default value
    
    if os.getenv("AI_REQUEST_TIMEOUT"):
        try:
            config.request_timeout = float(os.getenv("AI_REQUEST_TIMEOUT"))
        except ValueError:
            pass  # Keep default value
    
    if os.getenv("AI_MODELS_DIRECTORY"):
        config.models_directory = os.getenv("AI_MODELS_DIRECTORY")
    
    if os.getenv("AI_CACHE_DIRECTORY"):
        config.cache_directory = os.getenv("AI_CACHE_DIRECTORY")
    
    # QR detection settings
    if os.getenv("AI_QR_DETECTION_ENABLED") is not None:
        config.qr_detection_enabled = os.getenv("AI_QR_DETECTION_ENABLED", "true").lower() == "true"
    
    # Image preprocessing settings
    if os.getenv("AI_IMAGE_TARGET_SIZE"):
        try:
            size_str = os.getenv("AI_IMAGE_TARGET_SIZE")
            width, height = map(int, size_str.split(","))
            config.image_preprocessing.target_size = (width, height)
        except ValueError:
            pass  # Keep default value
    
    return config


def validate_ai_config(config: AIConfiguration) -> List[str]:
    """Validate AI configuration and return list of issues."""
    issues = []
    
    # Check model configuration if not using mock
    if not config.use_mock and config.ai_model_config is None:
        issues.append("Model configuration required when not using mock service")
    
    # Check model file exists if specified
    if config.ai_model_config and config.ai_model_config.model_path:
        if not os.path.exists(config.ai_model_config.model_path):
            issues.append(f"Model file not found: {config.ai_model_config.model_path}")
    
    # Check directories exist or can be created
    for directory in [config.models_directory, config.cache_directory]:
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError as e:
            issues.append(f"Cannot create directory {directory}: {e}")
    
    # Validate numeric ranges
    if not 0.0 <= config.confidence_threshold <= 1.0:
        issues.append("Confidence threshold must be between 0.0 and 1.0")
    
    if config.max_concurrent_requests < 1:
        issues.append("Max concurrent requests must be at least 1")
    
    if config.request_timeout <= 0:
        issues.append("Request timeout must be positive")
    
    return issues


class AIConfigManager:
    """Manages AI configuration loading, validation, and updates."""
    
    def __init__(self):
        self._config: Optional[AIConfiguration] = None
        self._config_file_path = "backend/config/ai-config.json"
    
    def get_config(self) -> AIConfiguration:
        """Get current AI configuration, loading from environment if needed."""
        if self._config is None:
            self._config = load_ai_config_from_env()
        return self._config
    
    def update_config(self, updates: Dict[str, any]) -> AIConfiguration:
        """Update AI configuration with new values."""
        config = self.get_config()
        
        # Update configuration fields
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        # Validate updated configuration
        issues = validate_ai_config(config)
        if issues:
            raise ValueError(f"Invalid AI configuration: {'; '.join(issues)}")
        
        self._config = config
        return config
    
    def reload_config(self) -> AIConfiguration:
        """Reload configuration from environment variables."""
        self._config = load_ai_config_from_env()
        return self._config
    
    def validate_current_config(self) -> List[str]:
        """Validate current configuration and return issues."""
        config = self.get_config()
        return validate_ai_config(config)
    
    def is_mock_mode(self) -> bool:
        """Check if AI system is running in mock mode."""
        return self.get_config().use_mock
    
    def is_model_available(self) -> bool:
        """Check if AI model is available for processing."""
        config = self.get_config()
        return config.model_available and not config.use_mock


# Global configuration manager instance
ai_config_manager = AIConfigManager()


def get_ai_config() -> AIConfiguration:
    """Get the current AI configuration."""
    return ai_config_manager.get_config()