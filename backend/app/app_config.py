"""
Comprehensive application configuration management.

Implements Requirement 16: Configuration Management for Deployment Flexibility.

- 16.1: Environment-based configuration for AI model paths and parameters
- 16.2: Configuration reading from environment variables and config files
- 16.3: Validation of required parameters during application startup
- 16.4: Default values for optional configuration parameters
- 16.5: Hot-reloading support for non-critical configuration changes
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config file paths
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).parent.parent  # backend/
_CONFIG_DIR = _BACKEND_DIR / "config"
_DEFAULT_CONFIG_FILE = _CONFIG_DIR / "app-config.json"


# ---------------------------------------------------------------------------
# Hot-reloadable (non-critical) configuration section
# ---------------------------------------------------------------------------

class HotReloadableConfig:
    """
    Holds non-critical configuration values that can be changed at runtime
    without restarting the application (Requirement 16.5).

    Non-critical settings include:
    - Search parameters (result limits, score thresholds)
    - Rate-limit windows and request caps
    - Content-source priorities and cache TTLs
    - Logging verbosity
    """

    # Default values
    _DEFAULTS: Dict[str, Any] = {
        # Search parameters
        "search_result_limit": 10,
        "search_score_threshold": 0.0,
        "search_hybrid_weight": 0.5,
        # Rate limiting
        "rate_limit_requests_per_minute": 60,
        "rate_limit_upload_per_hour": 20,
        # Content source settings
        "content_cache_ttl_seconds": 3600,
        "content_source_timeout_seconds": 10.0,
        "content_source_priority": ["internal_database", "manufacturer_website", "video_platform"],
        # Logging
        "log_level": "INFO",
    }

    def __init__(self, initial: Optional[Dict[str, Any]] = None) -> None:
        self._lock = threading.RLock()
        self._values: Dict[str, Any] = dict(self._DEFAULTS)
        if initial:
            self._values.update(initial)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._values[key] = value
        logger.debug("Hot-reload: %s = %r", key, value)

    def update(self, updates: Dict[str, Any]) -> None:
        """Apply multiple updates atomically."""
        with self._lock:
            self._values.update(updates)
        logger.info("Hot-reload: applied %d configuration update(s)", len(updates))

    def snapshot(self) -> Dict[str, Any]:
        """Return a copy of the current values."""
        with self._lock:
            return dict(self._values)

    def reset_to_defaults(self) -> None:
        """Reset all values to their defaults."""
        with self._lock:
            self._values = dict(self._DEFAULTS)

    # ------------------------------------------------------------------
    # Typed convenience properties
    # ------------------------------------------------------------------

    @property
    def search_result_limit(self) -> int:
        return int(self.get("search_result_limit", 10))

    @property
    def search_score_threshold(self) -> float:
        return float(self.get("search_score_threshold", 0.0))

    @property
    def search_hybrid_weight(self) -> float:
        return float(self.get("search_hybrid_weight", 0.5))

    @property
    def rate_limit_requests_per_minute(self) -> int:
        return int(self.get("rate_limit_requests_per_minute", 60))

    @property
    def rate_limit_upload_per_hour(self) -> int:
        return int(self.get("rate_limit_upload_per_hour", 20))

    @property
    def content_cache_ttl_seconds(self) -> int:
        return int(self.get("content_cache_ttl_seconds", 3600))

    @property
    def content_source_timeout_seconds(self) -> float:
        return float(self.get("content_source_timeout_seconds", 10.0))

    @property
    def content_source_priority(self) -> List[str]:
        return list(self.get("content_source_priority", ["internal_database"]))

    @property
    def log_level(self) -> str:
        return str(self.get("log_level", "INFO"))


# ---------------------------------------------------------------------------
# Static (critical) application settings via pydantic-settings
# ---------------------------------------------------------------------------

class AppSettings(BaseSettings):
    """
    Strongly-typed application settings loaded from environment variables
    and/or a .env file (Requirement 16.1, 16.2, 16.4).

    All fields have sensible defaults (Requirement 16.4).
    Required fields (those without defaults) are validated at startup
    (Requirement 16.3).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="APP_",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application identity
    # ------------------------------------------------------------------
    app_name: str = Field(default="UseIt Device Documentation Platform")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")

    # ------------------------------------------------------------------
    # AI model configuration (Requirement 16.1)
    # ------------------------------------------------------------------
    ai_models_directory: str = Field(
        default="backend/storage/ai-models",
        description="Directory where AI models are stored",
    )
    ai_cache_directory: str = Field(
        default="backend/storage/ai-cache",
        description="Directory for AI processing cache",
    )
    ai_use_mock: bool = Field(
        default=True,
        description="Use mock AI service (set False in production with real models)",
    )
    ai_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence score for device recognition",
    )
    ai_max_concurrent_requests: int = Field(
        default=5,
        ge=1,
        description="Maximum concurrent AI inference requests",
    )
    ai_request_timeout: float = Field(
        default=30.0,
        gt=0.0,
        description="AI request timeout in seconds",
    )
    ai_model_path: Optional[str] = Field(
        default=None,
        description="Path to the AI model file (required when ai_use_mock=False)",
    )
    ai_model_type: str = Field(
        default="onnx",
        description="AI model format: onnx, tensorflow, pytorch, huggingface",
    )

    # ------------------------------------------------------------------
    # Qdrant / vector database
    # ------------------------------------------------------------------
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: Optional[str] = Field(default=None)

    # ------------------------------------------------------------------
    # File upload limits
    # ------------------------------------------------------------------
    max_upload_size_bytes: int = Field(
        default=50 * 1024 * 1024,  # 50 MB
        description="Maximum allowed file upload size in bytes",
    )
    allowed_upload_extensions: List[str] = Field(
        default=[".pdf", ".doc", ".docx", ".txt"],
        description="Allowed file extensions for document uploads",
    )

    # ------------------------------------------------------------------
    # Storage paths
    # ------------------------------------------------------------------
    uploads_storage_directory: str = Field(
        default="backend/storage/uploads",
        description="Directory for uploaded document files",
    )
    device_images_directory: str = Field(
        default="frontend/static/device-images",
        description="Directory for device images",
    )
    config_directory: str = Field(
        default="backend/config",
        description="Directory for configuration files",
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> object:
        # pydantic-settings passes the raw env string here; handle comma-separated lists
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                # JSON array — let pydantic parse it
                import json as _json
                try:
                    return _json.loads(stripped)
                except Exception:
                    pass
            # Comma-separated format
            return [o.strip() for o in stripped.split(",") if o.strip()]
        return v

    @field_validator("allowed_upload_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v: object) -> object:
        if isinstance(v, str):
            return [e.strip() for e in v.split(",") if e.strip()]
        return v

    @field_validator("ai_model_type")
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        allowed = {"onnx", "tensorflow", "pytorch", "huggingface"}
        if v.lower() not in allowed:
            raise ValueError(f"ai_model_type must be one of {allowed}, got '{v}'")
        return v.lower()

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production", "test"}
        if v.lower() not in allowed:
            logger.warning("Unknown environment '%s'; expected one of %s", v, allowed)
        return v.lower()


# ---------------------------------------------------------------------------
# Startup validation (Requirement 16.3)
# ---------------------------------------------------------------------------

class ConfigValidationResult:
    """Result of configuration validation at startup."""

    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        logger.error("Config validation ERROR: %s", message)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
        logger.warning("Config validation WARNING: %s", message)

    def __repr__(self) -> str:
        return (
            f"ConfigValidationResult(valid={self.is_valid}, "
            f"errors={self.errors}, warnings={self.warnings})"
        )


def validate_app_settings(settings: AppSettings) -> ConfigValidationResult:
    """
    Validate application settings at startup (Requirement 16.3).

    - Errors block startup (required parameters missing or invalid).
    - Warnings are logged but do not block startup (optional parameters).
    """
    result = ConfigValidationResult()

    # --- Required: AI model path when not using mock ---
    if not settings.ai_use_mock and not settings.ai_model_path:
        result.add_error(
            "AI_MODEL_PATH is required when APP_AI_USE_MOCK=false. "
            "Set APP_AI_MODEL_PATH to the path of your AI model file."
        )

    # --- Required: AI model file must exist when specified ---
    if settings.ai_model_path and not Path(settings.ai_model_path).exists():
        result.add_error(
            f"AI model file not found: '{settings.ai_model_path}'. "
            "Ensure the file exists or set APP_AI_USE_MOCK=true."
        )

    # --- Warning: storage directories ---
    for label, directory in [
        ("AI models", settings.ai_models_directory),
        ("AI cache", settings.ai_cache_directory),
        ("Uploads storage", settings.uploads_storage_directory),
        ("Device images", settings.device_images_directory),
        ("Config", settings.config_directory),
    ]:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            result.add_warning(
                f"Cannot create {label} directory '{directory}': {exc}. "
                "Some features may not work correctly."
            )

    # --- Warning: production-specific checks ---
    if settings.environment == "production":
        if settings.ai_use_mock:
            result.add_warning(
                "APP_AI_USE_MOCK=true in production environment. "
                "Device recognition will use mock responses."
            )
        if not settings.qdrant_api_key:
            result.add_warning(
                "QDRANT_API_KEY is not set in production environment. "
                "Consider securing Qdrant with an API key."
            )

    # --- Warning: numeric range sanity checks ---
    if settings.ai_confidence_threshold < 0.5:
        result.add_warning(
            f"APP_AI_CONFIDENCE_THRESHOLD={settings.ai_confidence_threshold} is very low. "
            "Device recognition may return low-quality results."
        )

    if settings.max_upload_size_bytes > 100 * 1024 * 1024:
        result.add_warning(
            f"APP_MAX_UPLOAD_SIZE_BYTES={settings.max_upload_size_bytes} exceeds 100 MB. "
            "Large uploads may impact performance."
        )

    return result


# ---------------------------------------------------------------------------
# Config file loading (Requirement 16.2)
# ---------------------------------------------------------------------------

def load_config_file(path: Path) -> Dict[str, Any]:
    """
    Load configuration from a JSON file (Requirement 16.2).

    Returns an empty dict if the file does not exist or cannot be parsed.
    """
    if not path.exists():
        logger.debug("Config file not found: %s (using defaults)", path)
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        logger.info("Loaded config file: %s", path)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load config file '%s': %s", path, exc)
        return {}


def save_config_file(path: Path, data: Dict[str, Any]) -> bool:
    """
    Persist configuration to a JSON file.

    Returns True on success, False on failure.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        logger.info("Saved config file: %s", path)
        return True
    except OSError as exc:
        logger.warning("Failed to save config file '%s': %s", path, exc)
        return False


# ---------------------------------------------------------------------------
# Central configuration manager
# ---------------------------------------------------------------------------

class AppConfigManager:
    """
    Central manager for all application configuration (Requirement 16).

    Responsibilities:
    - Load static settings from environment variables / .env file (16.1, 16.2)
    - Load hot-reloadable settings from a JSON config file (16.2)
    - Validate required parameters at startup (16.3)
    - Provide default values for optional parameters (16.4)
    - Support hot-reloading of non-critical settings (16.5)
    """

    def __init__(
        self,
        config_file: Optional[Path] = None,
        auto_reload: bool = False,
        reload_interval_seconds: float = 30.0,
    ) -> None:
        self._config_file = config_file or _DEFAULT_CONFIG_FILE
        self._auto_reload = auto_reload
        self._reload_interval = reload_interval_seconds

        # Load static settings
        self._settings: AppSettings = AppSettings()

        # Load hot-reloadable settings from file
        file_data = load_config_file(self._config_file)
        hot_section = file_data.get("hot_reload", {})
        self._hot: HotReloadableConfig = HotReloadableConfig(hot_section)

        # Track last reload time
        self._last_reload_time: float = time.monotonic()
        self._reload_lock = threading.Lock()

        # Background reload thread (optional)
        self._reload_thread: Optional[threading.Thread] = None
        if auto_reload:
            self._start_auto_reload()

    # ------------------------------------------------------------------
    # Static settings access
    # ------------------------------------------------------------------

    @property
    def settings(self) -> AppSettings:
        """Return the static (critical) application settings."""
        return self._settings

    # ------------------------------------------------------------------
    # Hot-reloadable settings access
    # ------------------------------------------------------------------

    @property
    def hot(self) -> HotReloadableConfig:
        """Return the hot-reloadable configuration section."""
        return self._hot

    # ------------------------------------------------------------------
    # Startup validation (Requirement 16.3)
    # ------------------------------------------------------------------

    def validate_startup(self) -> ConfigValidationResult:
        """
        Validate configuration at application startup (Requirement 16.3).

        Logs all errors and warnings. Returns the validation result so the
        caller can decide whether to abort startup.
        """
        result = validate_app_settings(self._settings)

        if result.is_valid:
            logger.info(
                "Configuration validation passed (%d warning(s))",
                len(result.warnings),
            )
        else:
            logger.error(
                "Configuration validation FAILED: %d error(s), %d warning(s)",
                len(result.errors),
                len(result.warnings),
            )

        return result

    # ------------------------------------------------------------------
    # Hot-reload (Requirement 16.5)
    # ------------------------------------------------------------------

    def reload_hot_config(self) -> Tuple[bool, List[str]]:
        """
        Reload non-critical configuration from the config file (Requirement 16.5).

        Returns (success, list_of_changed_keys).
        """
        with self._reload_lock:
            file_data = load_config_file(self._config_file)
            hot_section = file_data.get("hot_reload", {})

            if not hot_section:
                logger.debug("Hot-reload: no 'hot_reload' section in config file")
                self._last_reload_time = time.monotonic()
                return True, []

            old_snapshot = self._hot.snapshot()
            self._hot.update(hot_section)
            new_snapshot = self._hot.snapshot()

            changed = [k for k in new_snapshot if new_snapshot[k] != old_snapshot.get(k)]
            self._last_reload_time = time.monotonic()

            if changed:
                logger.info("Hot-reload: updated keys: %s", changed)

            return True, changed

    def apply_hot_updates(self, updates: Dict[str, Any]) -> List[str]:
        """
        Apply hot-reload updates programmatically (e.g. from an API endpoint).

        Returns the list of keys that were actually changed.
        """
        old_snapshot = self._hot.snapshot()
        self._hot.update(updates)
        new_snapshot = self._hot.snapshot()
        changed = [k for k in new_snapshot if new_snapshot[k] != old_snapshot.get(k)]
        return changed

    @property
    def last_reload_time(self) -> float:
        """Monotonic timestamp of the last hot-reload."""
        return self._last_reload_time

    # ------------------------------------------------------------------
    # Auto-reload background thread
    # ------------------------------------------------------------------

    def _start_auto_reload(self) -> None:
        """Start a background thread that periodically reloads hot config."""
        self._reload_thread = threading.Thread(
            target=self._auto_reload_loop,
            daemon=True,
            name="config-hot-reload",
        )
        self._reload_thread.start()
        logger.info(
            "Config auto-reload started (interval=%.1fs)", self._reload_interval
        )

    def _auto_reload_loop(self) -> None:
        """Background loop for periodic hot-reload."""
        while True:
            time.sleep(self._reload_interval)
            try:
                self.reload_hot_config()
            except Exception as exc:  # pragma: no cover
                logger.warning("Auto-reload error: %s", exc)

    def stop_auto_reload(self) -> None:
        """Stop the background auto-reload thread (if running)."""
        self._auto_reload = False
        # The daemon thread will exit when the process exits; no explicit join needed.

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_full_snapshot(self) -> Dict[str, Any]:
        """Return a snapshot of all configuration (static + hot-reloadable)."""
        return {
            "static": self._settings.model_dump(),
            "hot_reload": self._hot.snapshot(),
            "last_reload_time": self._last_reload_time,
        }

    def is_production(self) -> bool:
        return self._settings.environment == "production"

    def is_development(self) -> bool:
        return self._settings.environment == "development"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: Optional[AppConfigManager] = None
_manager_lock = threading.Lock()


def get_app_config_manager(
    config_file: Optional[Path] = None,
    auto_reload: bool = False,
    reload_interval_seconds: float = 30.0,
) -> AppConfigManager:
    """
    Return the module-level AppConfigManager singleton.

    The first call initialises the manager; subsequent calls return the
    cached instance (thread-safe).
    """
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = AppConfigManager(
                    config_file=config_file,
                    auto_reload=auto_reload,
                    reload_interval_seconds=reload_interval_seconds,
                )
    return _manager


def reset_app_config_manager() -> None:
    """
    Reset the singleton (useful in tests to get a fresh instance).
    """
    global _manager
    with _manager_lock:
        _manager = None


def get_app_settings() -> AppSettings:
    """Convenience shortcut to get the static AppSettings."""
    return get_app_config_manager().settings


def get_hot_config() -> HotReloadableConfig:
    """Convenience shortcut to get the hot-reloadable config."""
    return get_app_config_manager().hot
