"""
Unit and property-based tests for configuration management.

Covers Task 18 requirements:
- 16.1: Environment-based configuration for AI model paths and parameters
- 16.2: Configuration reading from environment variables and config files
- 16.3: Configuration validation during application startup
- 16.4: Default values for optional configuration parameters
- 16.5: Hot-reloading support for non-critical configuration changes

Properties tested:
- Property 51: Environment Configuration Support (Req 16.1)
- Property 52: Configuration Source Reading (Req 16.2)
- Property 53: Default Configuration Values (Req 16.4)
- Property 54: Configuration Hot-Reloading (Req 16.5)
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings as hyp_settings, HealthCheck
from hypothesis import strategies as st

from app.app_config import (
    AppConfigManager,
    AppSettings,
    ConfigValidationResult,
    HotReloadableConfig,
    get_app_config_manager,
    get_app_settings,
    get_hot_config,
    load_config_file,
    reset_app_config_manager,
    save_config_file,
    validate_app_settings,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_manager(tmp_path: Path, hot_data: dict | None = None) -> AppConfigManager:
    """Create an AppConfigManager backed by a temp config file."""
    config_file = tmp_path / "app-config.json"
    if hot_data is not None:
        config_file.write_text(json.dumps({"hot_reload": hot_data}))
    return AppConfigManager(config_file=config_file)


# ---------------------------------------------------------------------------
# Unit tests: AppSettings defaults (Requirement 16.4)
# ---------------------------------------------------------------------------


class TestAppSettingsDefaults:
    """Verify that all optional settings have sensible defaults."""

    def test_default_environment_is_development(self):
        s = AppSettings()
        assert s.environment == "development"

    def test_default_ai_use_mock_is_true(self):
        s = AppSettings()
        assert s.ai_use_mock is True

    def test_default_ai_confidence_threshold(self):
        s = AppSettings()
        assert 0.0 <= s.ai_confidence_threshold <= 1.0

    def test_default_ai_max_concurrent_requests_positive(self):
        s = AppSettings()
        assert s.ai_max_concurrent_requests >= 1

    def test_default_ai_request_timeout_positive(self):
        s = AppSettings()
        assert s.ai_request_timeout > 0.0

    def test_default_ai_model_path_is_none(self):
        s = AppSettings()
        assert s.ai_model_path is None

    def test_default_ai_model_type_is_onnx(self):
        s = AppSettings()
        assert s.ai_model_type == "onnx"

    def test_default_max_upload_size_is_10mb(self):
        s = AppSettings()
        assert s.max_upload_size_bytes == 10 * 1024 * 1024

    def test_default_allowed_extensions_non_empty(self):
        s = AppSettings()
        assert len(s.allowed_upload_extensions) > 0

    def test_default_cors_origins_non_empty(self):
        s = AppSettings()
        assert len(s.cors_origins) > 0

    def test_default_qdrant_url_set(self):
        s = AppSettings()
        assert s.qdrant_url.startswith("http")

    def test_default_qdrant_api_key_is_none(self):
        s = AppSettings()
        assert s.qdrant_api_key is None

    def test_default_uploads_storage_directory_set(self):
        s = AppSettings()
        assert s.uploads_storage_directory != ""

    def test_default_ai_models_directory_set(self):
        s = AppSettings()
        assert s.ai_models_directory != ""

    def test_default_ai_cache_directory_set(self):
        s = AppSettings()
        assert s.ai_cache_directory != ""


# ---------------------------------------------------------------------------
# Unit tests: Environment variable overrides (Requirement 16.1, 16.2)
# ---------------------------------------------------------------------------


class TestEnvironmentVariableOverrides:
    """Verify settings are read from environment variables."""

    def test_ai_use_mock_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_AI_USE_MOCK", "false")
        monkeypatch.setenv("APP_AI_MODEL_PATH", "/tmp/model.onnx")
        s = AppSettings()
        assert s.ai_use_mock is False

    def test_ai_confidence_threshold_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_AI_CONFIDENCE_THRESHOLD", "0.85")
        s = AppSettings()
        assert abs(s.ai_confidence_threshold - 0.85) < 1e-9

    def test_ai_max_concurrent_requests_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_AI_MAX_CONCURRENT_REQUESTS", "10")
        s = AppSettings()
        assert s.ai_max_concurrent_requests == 10

    def test_ai_request_timeout_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_AI_REQUEST_TIMEOUT", "60.0")
        s = AppSettings()
        assert abs(s.ai_request_timeout - 60.0) < 1e-9

    def test_ai_model_path_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_AI_MODEL_PATH", "/models/device_recognition.onnx")
        s = AppSettings()
        assert s.ai_model_path == "/models/device_recognition.onnx"

    def test_ai_model_type_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_AI_MODEL_TYPE", "pytorch")
        s = AppSettings()
        assert s.ai_model_type == "pytorch"

    def test_environment_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_ENVIRONMENT", "production")
        s = AppSettings()
        assert s.environment == "production"

    def test_qdrant_url_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_QDRANT_URL", "http://qdrant-server:6333")
        s = AppSettings()
        assert s.qdrant_url == "http://qdrant-server:6333"

    def test_cors_origins_from_env(self, monkeypatch):
        # pydantic-settings with APP_ prefix reads APP_CORS_ORIGINS as a JSON array
        monkeypatch.setenv("APP_CORS_ORIGINS", '["http://example.com","http://app.example.com"]')
        s = AppSettings()
        assert "http://example.com" in s.cors_origins
        assert "http://app.example.com" in s.cors_origins

    def test_max_upload_size_from_env(self, monkeypatch):
        monkeypatch.setenv("APP_MAX_UPLOAD_SIZE_BYTES", "5242880")
        s = AppSettings()
        assert s.max_upload_size_bytes == 5242880

    def test_invalid_model_type_raises(self, monkeypatch):
        monkeypatch.setenv("APP_AI_MODEL_TYPE", "invalid_type")
        with pytest.raises(Exception):
            AppSettings()


# ---------------------------------------------------------------------------
# Unit tests: Config file loading (Requirement 16.2)
# ---------------------------------------------------------------------------


class TestConfigFileLoading:
    """Verify configuration is read from JSON config files."""

    def test_load_existing_config_file(self, tmp_path):
        config_file = tmp_path / "app-config.json"
        data = {"hot_reload": {"search_result_limit": 25}}
        config_file.write_text(json.dumps(data))

        loaded = load_config_file(config_file)
        assert loaded["hot_reload"]["search_result_limit"] == 25

    def test_load_missing_config_file_returns_empty(self, tmp_path):
        config_file = tmp_path / "nonexistent.json"
        loaded = load_config_file(config_file)
        assert loaded == {}

    def test_load_malformed_config_file_returns_empty(self, tmp_path):
        config_file = tmp_path / "bad.json"
        config_file.write_text("{ this is not valid json }")
        loaded = load_config_file(config_file)
        assert loaded == {}

    def test_save_and_reload_config_file(self, tmp_path):
        config_file = tmp_path / "app-config.json"
        data = {"hot_reload": {"log_level": "DEBUG"}}
        success = save_config_file(config_file, data)
        assert success is True

        loaded = load_config_file(config_file)
        assert loaded["hot_reload"]["log_level"] == "DEBUG"

    def test_save_creates_parent_directories(self, tmp_path):
        config_file = tmp_path / "nested" / "dir" / "config.json"
        success = save_config_file(config_file, {"key": "value"})
        assert success is True
        assert config_file.exists()

    def test_manager_loads_hot_config_from_file(self, tmp_path):
        manager = _make_manager(tmp_path, hot_data={"search_result_limit": 42})
        assert manager.hot.search_result_limit == 42

    def test_manager_uses_defaults_when_no_file(self, tmp_path):
        manager = _make_manager(tmp_path)  # no hot_data written
        # Should fall back to HotReloadableConfig defaults
        assert manager.hot.search_result_limit == 10


# ---------------------------------------------------------------------------
# Unit tests: Startup validation (Requirement 16.3)
# ---------------------------------------------------------------------------


class TestStartupValidation:
    """Verify required parameters are validated at startup."""

    def test_valid_default_config_passes(self, tmp_path):
        manager = _make_manager(tmp_path)
        result = manager.validate_startup()
        assert result.is_valid

    def test_missing_model_path_when_not_mock_is_error(self, monkeypatch, tmp_path):
        monkeypatch.setenv("APP_AI_USE_MOCK", "false")
        # ai_model_path not set
        settings = AppSettings()
        result = validate_app_settings(settings)
        assert not result.is_valid
        assert any("AI_MODEL_PATH" in e for e in result.errors)

    def test_nonexistent_model_path_is_error(self, tmp_path):
        settings = AppSettings(
            ai_use_mock=False,
            ai_model_path="/nonexistent/model.onnx",
        )
        result = validate_app_settings(settings)
        assert not result.is_valid
        assert any("not found" in e for e in result.errors)

    def test_mock_mode_passes_without_model_path(self, tmp_path):
        settings = AppSettings(ai_use_mock=True)
        result = validate_app_settings(settings)
        assert result.is_valid

    def test_production_without_api_key_is_warning(self, monkeypatch):
        settings = AppSettings(environment="production", ai_use_mock=True)
        result = validate_app_settings(settings)
        # Should be valid (no errors) but have warnings
        assert result.is_valid
        assert any("API_KEY" in w for w in result.warnings)

    def test_production_with_mock_is_warning(self, monkeypatch):
        settings = AppSettings(environment="production", ai_use_mock=True)
        result = validate_app_settings(settings)
        assert result.is_valid
        assert any("mock" in w.lower() for w in result.warnings)

    def test_low_confidence_threshold_is_warning(self):
        settings = AppSettings(ai_confidence_threshold=0.1)
        result = validate_app_settings(settings)
        assert result.is_valid
        assert any("CONFIDENCE_THRESHOLD" in w for w in result.warnings)

    def test_validation_result_repr(self):
        r = ConfigValidationResult()
        r.add_error("test error")
        r.add_warning("test warning")
        text = repr(r)
        assert "valid=False" in text

    def test_validation_result_is_valid_no_errors(self):
        r = ConfigValidationResult()
        assert r.is_valid is True

    def test_validation_result_is_invalid_with_errors(self):
        r = ConfigValidationResult()
        r.add_error("something wrong")
        assert r.is_valid is False


# ---------------------------------------------------------------------------
# Unit tests: HotReloadableConfig (Requirement 16.5)
# ---------------------------------------------------------------------------


class TestHotReloadableConfig:
    """Verify hot-reloadable configuration works correctly."""

    def test_default_values_are_set(self):
        hot = HotReloadableConfig()
        assert hot.search_result_limit == 10
        assert hot.search_score_threshold == 0.0
        assert hot.search_hybrid_weight == 0.5
        assert hot.rate_limit_requests_per_minute == 60
        assert hot.rate_limit_upload_per_hour == 20
        assert hot.content_cache_ttl_seconds == 3600
        assert hot.content_source_timeout_seconds == 10.0
        assert isinstance(hot.content_source_priority, list)
        assert hot.log_level == "INFO"

    def test_initial_values_override_defaults(self):
        hot = HotReloadableConfig({"search_result_limit": 50})
        assert hot.search_result_limit == 50

    def test_set_updates_value(self):
        hot = HotReloadableConfig()
        hot.set("search_result_limit", 25)
        assert hot.search_result_limit == 25

    def test_update_applies_multiple_values(self):
        hot = HotReloadableConfig()
        hot.update({"search_result_limit": 20, "log_level": "DEBUG"})
        assert hot.search_result_limit == 20
        assert hot.log_level == "DEBUG"

    def test_snapshot_returns_copy(self):
        hot = HotReloadableConfig()
        snap = hot.snapshot()
        snap["search_result_limit"] = 999
        # Original should be unchanged
        assert hot.search_result_limit == 10

    def test_reset_to_defaults(self):
        hot = HotReloadableConfig()
        hot.set("search_result_limit", 99)
        hot.reset_to_defaults()
        assert hot.search_result_limit == 10

    def test_get_with_default(self):
        hot = HotReloadableConfig()
        assert hot.get("nonexistent_key", "fallback") == "fallback"

    def test_thread_safety(self):
        """Concurrent reads and writes should not raise exceptions."""
        hot = HotReloadableConfig()
        errors = []

        def writer():
            for i in range(50):
                try:
                    hot.set("search_result_limit", i)
                except Exception as exc:
                    errors.append(exc)

        def reader():
            for _ in range(50):
                try:
                    _ = hot.search_result_limit
                except Exception as exc:
                    errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(3)]
        threads += [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread safety errors: {errors}"


# ---------------------------------------------------------------------------
# Unit tests: AppConfigManager (Requirement 16.2, 16.5)
# ---------------------------------------------------------------------------


class TestAppConfigManager:
    """Verify the central config manager works correctly."""

    def test_manager_returns_settings(self, tmp_path):
        manager = _make_manager(tmp_path)
        assert isinstance(manager.settings, AppSettings)

    def test_manager_returns_hot_config(self, tmp_path):
        manager = _make_manager(tmp_path)
        assert isinstance(manager.hot, HotReloadableConfig)

    def test_reload_hot_config_picks_up_changes(self, tmp_path):
        config_file = tmp_path / "app-config.json"
        config_file.write_text(json.dumps({"hot_reload": {"search_result_limit": 5}}))
        manager = AppConfigManager(config_file=config_file)
        assert manager.hot.search_result_limit == 5

        # Update the file
        config_file.write_text(json.dumps({"hot_reload": {"search_result_limit": 99}}))
        success, changed = manager.reload_hot_config()

        assert success is True
        assert "search_result_limit" in changed
        assert manager.hot.search_result_limit == 99

    def test_reload_returns_changed_keys(self, tmp_path):
        config_file = tmp_path / "app-config.json"
        config_file.write_text(json.dumps({"hot_reload": {"log_level": "INFO"}}))
        manager = AppConfigManager(config_file=config_file)

        config_file.write_text(json.dumps({"hot_reload": {"log_level": "DEBUG"}}))
        _, changed = manager.reload_hot_config()
        assert "log_level" in changed

    def test_reload_no_changes_returns_empty_list(self, tmp_path):
        config_file = tmp_path / "app-config.json"
        data = {"hot_reload": {"search_result_limit": 10}}
        config_file.write_text(json.dumps(data))
        manager = AppConfigManager(config_file=config_file)

        # Reload without changing the file
        _, changed = manager.reload_hot_config()
        assert changed == []

    def test_apply_hot_updates_programmatically(self, tmp_path):
        manager = _make_manager(tmp_path)
        changed = manager.apply_hot_updates({"search_result_limit": 77})
        assert "search_result_limit" in changed
        assert manager.hot.search_result_limit == 77

    def test_last_reload_time_updates(self, tmp_path):
        manager = _make_manager(tmp_path)
        t0 = manager.last_reload_time
        time.sleep(0.01)
        manager.reload_hot_config()
        assert manager.last_reload_time >= t0

    def test_get_full_snapshot_contains_sections(self, tmp_path):
        manager = _make_manager(tmp_path)
        snap = manager.get_full_snapshot()
        assert "static" in snap
        assert "hot_reload" in snap
        assert "last_reload_time" in snap

    def test_is_development_default(self, tmp_path):
        manager = _make_manager(tmp_path)
        assert manager.is_development() is True
        assert manager.is_production() is False

    def test_validate_startup_returns_result(self, tmp_path):
        manager = _make_manager(tmp_path)
        result = manager.validate_startup()
        assert isinstance(result, ConfigValidationResult)


# ---------------------------------------------------------------------------
# Unit tests: Singleton helpers
# ---------------------------------------------------------------------------


class TestSingletonHelpers:
    """Verify module-level singleton helpers work correctly."""

    def setup_method(self):
        reset_app_config_manager()

    def teardown_method(self):
        reset_app_config_manager()

    def test_get_app_config_manager_returns_same_instance(self):
        m1 = get_app_config_manager()
        m2 = get_app_config_manager()
        assert m1 is m2

    def test_reset_creates_new_instance(self):
        m1 = get_app_config_manager()
        reset_app_config_manager()
        m2 = get_app_config_manager()
        assert m1 is not m2

    def test_get_app_settings_returns_settings(self):
        s = get_app_settings()
        assert isinstance(s, AppSettings)

    def test_get_hot_config_returns_hot_config(self):
        h = get_hot_config()
        assert isinstance(h, HotReloadableConfig)


# ---------------------------------------------------------------------------
# Property-based tests (Task 18.1)
# ---------------------------------------------------------------------------


# Property 51: Environment Configuration Support
# Validates: Requirements 16.1


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    max_requests=st.integers(min_value=1, max_value=100),
    timeout=st.floats(min_value=0.1, max_value=300.0, allow_nan=False),
)
@hyp_settings(max_examples=30)
def test_property_51_valid_ai_params_accepted(confidence, max_requests, timeout):
    """
    **Validates: Requirements 16.1**

    Property 51: For any valid AI configuration parameters, AppSettings SHALL
    accept and store them correctly.
    """
    s = AppSettings(
        ai_confidence_threshold=confidence,
        ai_max_concurrent_requests=max_requests,
        ai_request_timeout=timeout,
    )
    assert abs(s.ai_confidence_threshold - confidence) < 1e-9
    assert s.ai_max_concurrent_requests == max_requests
    assert abs(s.ai_request_timeout - timeout) < 1e-9


@given(st.sampled_from(["onnx", "tensorflow", "pytorch", "huggingface"]))
@hyp_settings(max_examples=10)
def test_property_51_all_model_types_accepted(model_type):
    """
    **Validates: Requirements 16.1**

    Property 51: AppSettings SHALL accept all supported AI model types.
    """
    s = AppSettings(ai_model_type=model_type)
    assert s.ai_model_type == model_type


# Property 52: Configuration Source Reading
# Validates: Requirements 16.2


@given(
    limit=st.integers(min_value=1, max_value=1000),
    threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    log_level=st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR"]),
)
@hyp_settings(max_examples=30)
def test_property_52_config_file_values_loaded(limit, threshold, log_level):
    """
    **Validates: Requirements 16.2**

    Property 52: For any valid hot-reload configuration written to a config
    file, AppConfigManager SHALL read and apply those values correctly.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "app-config.json"
        data = {
            "hot_reload": {
                "search_result_limit": limit,
                "search_score_threshold": threshold,
                "log_level": log_level,
            }
        }
        config_file.write_text(json.dumps(data))

        manager = AppConfigManager(config_file=config_file)
        assert manager.hot.search_result_limit == limit
        assert abs(manager.hot.search_score_threshold - threshold) < 1e-9
        assert manager.hot.log_level == log_level


@given(st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Ll",))),
    values=st.one_of(st.integers(min_value=0, max_value=9999), st.text(min_size=0, max_size=50)),
    min_size=0,
    max_size=10,
))
@hyp_settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow])
def test_property_52_arbitrary_hot_reload_data_stored(data):
    """
    **Validates: Requirements 16.2**

    Property 52: For any dictionary of hot-reload values, AppConfigManager
    SHALL store and retrieve them without data loss.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "app-config.json"
        config_file.write_text(json.dumps({"hot_reload": data}))

        manager = AppConfigManager(config_file=config_file)
        for key, value in data.items():
            assert manager.hot.get(key) == value


# Property 53: Default Configuration Values
# Validates: Requirements 16.4


@given(st.just(None))  # Parameterised to run via hypothesis
@hyp_settings(max_examples=5)
def test_property_53_all_defaults_are_valid(_):
    """
    **Validates: Requirements 16.4**

    Property 53: AppSettings with no overrides SHALL have valid default values
    for all optional parameters.
    """
    s = AppSettings()
    assert 0.0 <= s.ai_confidence_threshold <= 1.0
    assert s.ai_max_concurrent_requests >= 1
    assert s.ai_request_timeout > 0.0
    assert s.max_upload_size_bytes > 0
    assert len(s.allowed_upload_extensions) > 0
    assert len(s.cors_origins) > 0
    assert s.ai_models_directory != ""
    assert s.ai_cache_directory != ""
    assert s.uploads_storage_directory != ""


@given(st.just(None))
@hyp_settings(max_examples=5)
def test_property_53_hot_reload_defaults_are_valid(_):
    """
    **Validates: Requirements 16.4**

    Property 53: HotReloadableConfig with no overrides SHALL have valid
    default values for all parameters.
    """
    hot = HotReloadableConfig()
    assert hot.search_result_limit > 0
    assert 0.0 <= hot.search_score_threshold <= 1.0
    assert 0.0 <= hot.search_hybrid_weight <= 1.0
    assert hot.rate_limit_requests_per_minute > 0
    assert hot.rate_limit_upload_per_hour > 0
    assert hot.content_cache_ttl_seconds > 0
    assert hot.content_source_timeout_seconds > 0.0
    assert len(hot.content_source_priority) > 0
    assert hot.log_level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


# Property 54: Configuration Hot-Reloading
# Validates: Requirements 16.5


@given(
    initial=st.integers(min_value=1, max_value=100),
    updated=st.integers(min_value=1, max_value=100),
)
@hyp_settings(max_examples=30)
def test_property_54_hot_reload_updates_values(initial, updated):
    """
    **Validates: Requirements 16.5**

    Property 54: For any non-critical configuration change, hot-reloading
    SHALL update the in-memory values without restarting the application.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "app-config.json"
        config_file.write_text(json.dumps({"hot_reload": {"search_result_limit": initial}}))
        manager = AppConfigManager(config_file=config_file)
        assert manager.hot.search_result_limit == initial

        # Simulate a config file update
        config_file.write_text(json.dumps({"hot_reload": {"search_result_limit": updated}}))
        success, changed = manager.reload_hot_config()

        assert success is True
        assert manager.hot.search_result_limit == updated
        if initial != updated:
            assert "search_result_limit" in changed


@given(st.lists(
    st.fixed_dictionaries({
        "search_result_limit": st.integers(min_value=1, max_value=500),
        "log_level": st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR"]),
    }),
    min_size=1,
    max_size=5,
))
@hyp_settings(max_examples=20)
def test_property_54_multiple_reloads_always_reflect_latest(reload_sequence):
    """
    **Validates: Requirements 16.5**

    Property 54: After multiple hot-reloads, the configuration SHALL always
    reflect the most recently loaded values.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_file = Path(tmp_dir) / "app-config.json"
        config_file.write_text(json.dumps({"hot_reload": reload_sequence[0]}))
        manager = AppConfigManager(config_file=config_file)

        for update in reload_sequence:
            config_file.write_text(json.dumps({"hot_reload": update}))
            manager.reload_hot_config()

        # After all reloads, values should match the last update
        last = reload_sequence[-1]
        assert manager.hot.search_result_limit == last["search_result_limit"]
        assert manager.hot.log_level == last["log_level"]


@given(st.dictionaries(
    keys=st.sampled_from([
        "search_result_limit",
        "search_score_threshold",
        "rate_limit_requests_per_minute",
        "content_cache_ttl_seconds",
        "log_level",
    ]),
    values=st.one_of(
        st.integers(min_value=1, max_value=9999),
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR"]),
    ),
    min_size=1,
    max_size=5,
))
@hyp_settings(max_examples=20)
def test_property_54_programmatic_hot_updates_applied(updates):
    """
    **Validates: Requirements 16.5**

    Property 54: Programmatic hot-reload updates SHALL be applied immediately
    and reflected in subsequent reads.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = _make_manager(Path(tmp_dir))
        changed = manager.apply_hot_updates(updates)

        for key, value in updates.items():
            stored = manager.hot.get(key)
            assert stored == value, f"Key '{key}': expected {value!r}, got {stored!r}"
