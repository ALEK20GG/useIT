"""
Property-based and unit tests for comprehensive error handling.

Covers Task 16 requirements:
- 17.1: Device recognition error messages with suggested solutions
- 17.2: Graceful degradation when external services are unavailable
- 17.3: Upload error information and retry options
- 17.4: Loading indicators (timing metadata)
- 17.5: Error logging while displaying user-friendly messages

Properties tested:
- Property 55: Device Recognition Error Handling (Req 17.1)
- Property 56: Graceful Service Degradation (Req 17.2)
- Property 57: Upload Error Handling (Req 17.3)
- Property 58: Loading Indicators (Req 17.4)
- Property 59: Error Logging and User Messages (Req 17.5)
"""

import asyncio
import logging
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.error_handling import (
    CircuitBreaker,
    CircuitBreakerState,
    ErrorCategory,
    ErrorCode,
    RetryConfig,
    ServiceDegradationInfo,
    StructuredErrorResponse,
    UploadErrorResponse,
    calculate_retry_delay,
    check_embedding_service_health,
    log_operation_timing,
    make_device_recognition_error,
    make_service_degradation_response,
    make_upload_error,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(coro):
    """Run a coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Property 55: Device Recognition Error Handling (Req 17.1)
# ---------------------------------------------------------------------------


class TestDeviceRecognitionErrorHandling:
    """
    **Property 55: Device Recognition Error Handling**
    Validates: Requirements 17.1

    For any device recognition error, the system SHALL provide specific
    error messages with suggested solutions.
    """

    @given(
        error_code=st.sampled_from([
            ErrorCode.IMAGE_TOO_LARGE,
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            ErrorCode.IMAGE_EMPTY,
            ErrorCode.RECOGNITION_LOW_CONFIDENCE,
            ErrorCode.RECOGNITION_FAILED,
            ErrorCode.QR_NOT_DETECTED,
            ErrorCode.QR_INVALID_FORMAT,
        ]),
        detail=st.text(min_size=0, max_size=200),
    )
    @settings(max_examples=100)
    def test_device_recognition_error_always_has_user_message(
        self, error_code: ErrorCode, detail: str
    ):
        """
        **Property 55: Device Recognition Error Handling**
        Validates: Requirements 17.1

        For any device recognition error code, the response SHALL always
        contain a non-empty user-friendly message.
        """
        response = make_device_recognition_error(error_code, detail)

        assert isinstance(response, StructuredErrorResponse)
        assert response.user_message, "User message must not be empty"
        assert len(response.user_message) > 0

    @given(
        error_code=st.sampled_from([
            ErrorCode.IMAGE_TOO_LARGE,
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            ErrorCode.IMAGE_EMPTY,
            ErrorCode.RECOGNITION_LOW_CONFIDENCE,
            ErrorCode.RECOGNITION_FAILED,
            ErrorCode.QR_NOT_DETECTED,
            ErrorCode.QR_INVALID_FORMAT,
        ]),
    )
    @settings(max_examples=50)
    def test_device_recognition_error_has_suggestions(self, error_code: ErrorCode):
        """
        **Property 55: Device Recognition Error Handling**
        Validates: Requirements 17.1

        For any device recognition error, the response SHALL include
        at least one suggested solution.
        """
        response = make_device_recognition_error(error_code)

        assert isinstance(response.suggestions, list)
        assert len(response.suggestions) >= 1, (
            f"Error code {error_code} must have at least one suggestion"
        )

    @given(
        error_code=st.sampled_from([
            ErrorCode.IMAGE_TOO_LARGE,
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            ErrorCode.IMAGE_EMPTY,
            ErrorCode.RECOGNITION_LOW_CONFIDENCE,
            ErrorCode.RECOGNITION_FAILED,
            ErrorCode.QR_NOT_DETECTED,
            ErrorCode.QR_INVALID_FORMAT,
        ]),
    )
    @settings(max_examples=50)
    def test_device_recognition_error_category_is_correct(self, error_code: ErrorCode):
        """
        **Property 55: Device Recognition Error Handling**
        Validates: Requirements 17.1

        For any device recognition error, the category SHALL be
        'device_recognition'.
        """
        response = make_device_recognition_error(error_code)
        assert response.category == ErrorCategory.DEVICE_RECOGNITION.value

    @given(
        error_code=st.sampled_from([
            ErrorCode.IMAGE_TOO_LARGE,
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            ErrorCode.IMAGE_EMPTY,
            ErrorCode.RECOGNITION_LOW_CONFIDENCE,
            ErrorCode.RECOGNITION_FAILED,
            ErrorCode.QR_NOT_DETECTED,
            ErrorCode.QR_INVALID_FORMAT,
        ]),
    )
    @settings(max_examples=50)
    def test_device_recognition_error_code_preserved(self, error_code: ErrorCode):
        """
        **Property 55: Device Recognition Error Handling**
        Validates: Requirements 17.1

        The error_code in the response SHALL match the input error code.
        """
        response = make_device_recognition_error(error_code)
        assert response.error_code == error_code.value

    def test_image_too_large_suggests_compression(self):
        """IMAGE_TOO_LARGE error should suggest file compression."""
        response = make_device_recognition_error(ErrorCode.IMAGE_TOO_LARGE)
        suggestion_actions = [s.action.lower() for s in response.suggestions]
        # At least one suggestion should mention compression or size reduction
        assert any(
            "comprimi" in a or "riduc" in a or "compress" in a
            for a in suggestion_actions
        ), "IMAGE_TOO_LARGE should suggest compression"

    def test_recognition_low_confidence_suggests_manual_fallback(self):
        """Low confidence should suggest manual device selection."""
        response = make_device_recognition_error(ErrorCode.RECOGNITION_LOW_CONFIDENCE)
        suggestion_actions = [s.action.lower() for s in response.suggestions]
        assert any(
            "manuale" in a or "manual" in a
            for a in suggestion_actions
        ), "Low confidence should suggest manual selection"

    def test_recognition_failed_can_retry(self):
        """RECOGNITION_FAILED should be retryable."""
        response = make_device_recognition_error(ErrorCode.RECOGNITION_FAILED)
        assert response.can_retry is True


# ---------------------------------------------------------------------------
# Property 56: Graceful Service Degradation (Req 17.2)
# ---------------------------------------------------------------------------


class TestGracefulServiceDegradation:
    """
    **Property 56: Graceful Service Degradation**
    Validates: Requirements 17.2

    For any external service unavailability, the system SHALL implement
    graceful degradation.
    """

    @given(
        service_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
        error_message=st.text(min_size=1, max_size=200),
        fallback=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    )
    @settings(max_examples=100)
    def test_service_degradation_always_has_user_message(
        self, service_name: str, error_message: str, fallback
    ):
        """
        **Property 56: Graceful Service Degradation**
        Validates: Requirements 17.2

        For any service failure, the degradation response SHALL always
        contain a non-empty user-friendly message.
        """
        error = Exception(error_message)
        response = make_service_degradation_response(service_name, error, fallback)

        assert isinstance(response, ServiceDegradationInfo)
        assert response.user_message, "User message must not be empty"
        assert len(response.user_message) > 0

    @given(
        service_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
        error_message=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=100)
    def test_service_degradation_marks_service_unavailable(
        self, service_name: str, error_message: str
    ):
        """
        **Property 56: Graceful Service Degradation**
        Validates: Requirements 17.2

        When a service fails, the degradation response SHALL mark
        is_available as False.
        """
        error = Exception(error_message)
        response = make_service_degradation_response(service_name, error)

        assert response.is_available is False

    @given(
        service_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
        error_message=st.text(min_size=1, max_size=200),
        fallback_desc=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_service_degradation_with_fallback_marks_fallback_available(
        self, service_name: str, error_message: str, fallback_desc: str
    ):
        """
        **Property 56: Graceful Service Degradation**
        Validates: Requirements 17.2

        When a fallback description is provided, fallback_available SHALL be True.
        """
        error = Exception(error_message)
        response = make_service_degradation_response(service_name, error, fallback_desc)

        assert response.fallback_available is True
        assert response.fallback_description == fallback_desc

    @given(
        service_name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
        error_message=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=100)
    def test_service_degradation_without_fallback_marks_fallback_unavailable(
        self, service_name: str, error_message: str
    ):
        """
        **Property 56: Graceful Service Degradation**
        Validates: Requirements 17.2

        When no fallback is provided, fallback_available SHALL be False.
        """
        error = Exception(error_message)
        response = make_service_degradation_response(service_name, error, None)

        assert response.fallback_available is False


class TestCircuitBreaker:
    """Unit tests for CircuitBreaker (supports Req 17.2)."""

    def test_circuit_starts_closed(self):
        """Circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker("test-service")
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_available() is True

    def test_circuit_opens_after_threshold_failures(self):
        """Circuit opens after reaching failure threshold."""
        cb = CircuitBreaker("test-service", failure_threshold=3)
        error = Exception("service error")

        cb.record_failure(error)
        assert cb.state == CircuitBreakerState.CLOSED

        cb.record_failure(error)
        assert cb.state == CircuitBreakerState.CLOSED

        cb.record_failure(error)
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_available() is False

    def test_circuit_resets_on_success(self):
        """Circuit resets to CLOSED after a successful call."""
        cb = CircuitBreaker("test-service", failure_threshold=2)
        error = Exception("service error")

        cb.record_failure(error)
        cb.record_failure(error)
        assert cb.state == CircuitBreakerState.OPEN

        # Simulate timeout passing
        cb.last_failure_time = time.monotonic() - 61
        assert cb.is_available() is True  # Transitions to HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_status_returns_dict(self):
        """get_status returns a dict with required fields."""
        cb = CircuitBreaker("test-service")
        status = cb.get_status()

        assert "service" in status
        assert "state" in status
        assert "failure_count" in status
        assert "is_available" in status


# ---------------------------------------------------------------------------
# Property 57: Upload Error Handling (Req 17.3)
# ---------------------------------------------------------------------------


class TestUploadErrorHandling:
    """
    **Property 57: Upload Error Handling**
    Validates: Requirements 17.3

    For any upload operation failure, the system SHALL display detailed
    error information and retry options.
    """

    @given(
        filename=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pd"))).map(lambda s: s + ".pdf"),
        error_code=st.sampled_from([
            ErrorCode.UPLOAD_FILE_TOO_LARGE,
            ErrorCode.UPLOAD_FORMAT_UNSUPPORTED,
            ErrorCode.UPLOAD_EXTRACTION_FAILED,
            ErrorCode.UPLOAD_INDEXING_FAILED,
            ErrorCode.UPLOAD_NETWORK_ERROR,
            ErrorCode.UPLOAD_NO_TEXT,
        ]),
        detail=st.text(min_size=0, max_size=200),
    )
    @settings(max_examples=100)
    def test_upload_error_always_has_user_message(
        self, filename: str, error_code: ErrorCode, detail: str
    ):
        """
        **Property 57: Upload Error Handling**
        Validates: Requirements 17.3

        For any upload failure, the response SHALL always contain a
        non-empty user-friendly message.
        """
        response = make_upload_error(filename, error_code, detail)

        assert isinstance(response, UploadErrorResponse)
        assert response.user_message, "User message must not be empty"
        assert len(response.user_message) > 0

    @given(
        filename=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pd"))).map(lambda s: s + ".pdf"),
        error_code=st.sampled_from([
            ErrorCode.UPLOAD_FILE_TOO_LARGE,
            ErrorCode.UPLOAD_FORMAT_UNSUPPORTED,
            ErrorCode.UPLOAD_EXTRACTION_FAILED,
            ErrorCode.UPLOAD_INDEXING_FAILED,
            ErrorCode.UPLOAD_NETWORK_ERROR,
            ErrorCode.UPLOAD_NO_TEXT,
        ]),
    )
    @settings(max_examples=100)
    def test_upload_error_has_retry_options(
        self, filename: str, error_code: ErrorCode
    ):
        """
        **Property 57: Upload Error Handling**
        Validates: Requirements 17.3

        For any upload failure, the response SHALL include at least one
        retry option or suggestion.
        """
        response = make_upload_error(filename, error_code)

        assert isinstance(response.retry_options, list)
        assert len(response.retry_options) >= 1, (
            f"Upload error {error_code} must have at least one retry option"
        )

    @given(
        filename=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pd"))).map(lambda s: s + ".pdf"),
        error_code=st.sampled_from([
            ErrorCode.UPLOAD_FILE_TOO_LARGE,
            ErrorCode.UPLOAD_FORMAT_UNSUPPORTED,
            ErrorCode.UPLOAD_EXTRACTION_FAILED,
            ErrorCode.UPLOAD_INDEXING_FAILED,
            ErrorCode.UPLOAD_NETWORK_ERROR,
            ErrorCode.UPLOAD_NO_TEXT,
        ]),
    )
    @settings(max_examples=100)
    def test_upload_error_filename_preserved(
        self, filename: str, error_code: ErrorCode
    ):
        """
        **Property 57: Upload Error Handling**
        Validates: Requirements 17.3

        The filename in the upload error response SHALL match the input filename.
        """
        response = make_upload_error(filename, error_code)
        assert response.filename == filename

    @given(
        filename=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Pd"))).map(lambda s: s + ".pdf"),
        error_code=st.sampled_from([
            ErrorCode.UPLOAD_FILE_TOO_LARGE,
            ErrorCode.UPLOAD_FORMAT_UNSUPPORTED,
            ErrorCode.UPLOAD_EXTRACTION_FAILED,
            ErrorCode.UPLOAD_INDEXING_FAILED,
            ErrorCode.UPLOAD_NETWORK_ERROR,
            ErrorCode.UPLOAD_NO_TEXT,
        ]),
    )
    @settings(max_examples=100)
    def test_upload_error_code_preserved(
        self, filename: str, error_code: ErrorCode
    ):
        """
        **Property 57: Upload Error Handling**
        Validates: Requirements 17.3

        The error_code in the upload error response SHALL match the input error code.
        """
        response = make_upload_error(filename, error_code)
        assert response.error_code == error_code.value

    def test_network_error_is_retryable(self):
        """Network errors should be retryable."""
        response = make_upload_error("test.pdf", ErrorCode.UPLOAD_NETWORK_ERROR)
        assert response.can_retry is True

    def test_indexing_error_is_retryable(self):
        """Indexing errors should be retryable."""
        response = make_upload_error("test.pdf", ErrorCode.UPLOAD_INDEXING_FAILED)
        assert response.can_retry is True

    def test_format_error_is_not_retryable(self):
        """Format errors are not retryable without user action."""
        response = make_upload_error("test.txt", ErrorCode.UPLOAD_FORMAT_UNSUPPORTED)
        assert response.can_retry is False


# ---------------------------------------------------------------------------
# Property 58: Loading Indicators (Req 17.4)
# ---------------------------------------------------------------------------


class TestLoadingIndicators:
    """
    **Property 58: Loading Indicators**
    Validates: Requirements 17.4

    For any asynchronous operation exceeding 1 second, the system SHALL
    provide loading indicators (backend: timing metadata).
    """

    @given(
        operation_name=st.text(min_size=1, max_size=50),
        elapsed_ms=st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_timing_function_returns_elapsed_ms(
        self, operation_name: str, elapsed_ms: float
    ):
        """
        **Property 58: Loading Indicators**
        Validates: Requirements 17.4

        The timing function SHALL return elapsed milliseconds as a float.
        """
        test_logger = logging.getLogger("test")
        # Simulate a start time that gives us the desired elapsed_ms
        start_time = time.monotonic() - (elapsed_ms / 1000.0)

        result = log_operation_timing(test_logger, operation_name, start_time)

        assert isinstance(result, float)
        # Allow 50ms tolerance for test execution time
        assert abs(result - elapsed_ms) < 50.0, (
            f"Expected ~{elapsed_ms}ms, got {result}ms"
        )

    def test_slow_operation_returns_positive_elapsed(self):
        """Operations that take time should return positive elapsed ms."""
        test_logger = logging.getLogger("test")
        start = time.monotonic()
        time.sleep(0.02)  # 20ms sleep for more reliable timing
        elapsed = log_operation_timing(test_logger, "test_op", start)

        assert elapsed > 0
        assert elapsed >= 5.0  # At least 5ms (generous lower bound for CI)

    def test_timing_function_returns_float(self):
        """log_operation_timing always returns a float."""
        test_logger = logging.getLogger("test")
        start = time.monotonic()
        result = log_operation_timing(test_logger, "test_op", start)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Property 59: Error Logging and User Messages (Req 17.5)
# ---------------------------------------------------------------------------


class TestErrorLoggingAndUserMessages:
    """
    **Property 59: Error Logging and User Messages**
    Validates: Requirements 17.5

    For any error condition, the system SHALL log errors for debugging
    while displaying user-friendly messages.
    """

    @given(
        error_code=st.sampled_from([
            ErrorCode.IMAGE_TOO_LARGE,
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            ErrorCode.RECOGNITION_FAILED,
            ErrorCode.QR_NOT_DETECTED,
        ]),
        detail=st.text(min_size=0, max_size=200),
    )
    @settings(max_examples=100)
    def test_user_message_does_not_contain_raw_exception(
        self, error_code: ErrorCode, detail: str
    ):
        """
        **Property 59: Error Logging and User Messages**
        Validates: Requirements 17.5

        User-facing messages SHALL NOT contain raw exception details
        (stack traces, internal paths, etc.).
        """
        response = make_device_recognition_error(error_code, detail)

        # User message should not contain typical exception artifacts
        user_msg = response.user_message
        assert "Traceback" not in user_msg
        assert "File \"" not in user_msg
        assert "line " not in user_msg or "linea" in user_msg.lower()

    @given(
        filename=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))).map(lambda s: s + ".pdf"),
        error_code=st.sampled_from([
            ErrorCode.UPLOAD_FILE_TOO_LARGE,
            ErrorCode.UPLOAD_FORMAT_UNSUPPORTED,
            ErrorCode.UPLOAD_EXTRACTION_FAILED,
        ]),
        detail=st.text(min_size=0, max_size=200),
    )
    @settings(max_examples=100)
    def test_upload_user_message_does_not_contain_raw_exception(
        self, filename: str, error_code: ErrorCode, detail: str
    ):
        """
        **Property 59: Error Logging and User Messages**
        Validates: Requirements 17.5

        Upload error user messages SHALL NOT contain raw exception details.
        """
        response = make_upload_error(filename, error_code, detail)

        user_msg = response.user_message
        assert "Traceback" not in user_msg
        assert "File \"" not in user_msg

    @given(
        error_code=st.sampled_from([
            ErrorCode.IMAGE_TOO_LARGE,
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            ErrorCode.RECOGNITION_FAILED,
            ErrorCode.QR_NOT_DETECTED,
        ]),
    )
    @settings(max_examples=50)
    def test_error_response_is_serializable(self, error_code: ErrorCode):
        """
        **Property 59: Error Logging and User Messages**
        Validates: Requirements 17.5

        All error responses SHALL be serializable to dict (for JSON responses).
        """
        response = make_device_recognition_error(error_code)
        # Pydantic model_dump should work without errors
        data = response.model_dump()
        assert isinstance(data, dict)
        assert "user_message" in data
        assert "error_code" in data
        assert "suggestions" in data

    @given(
        filename=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))).map(lambda s: s + ".pdf"),
        error_code=st.sampled_from([
            ErrorCode.UPLOAD_FILE_TOO_LARGE,
            ErrorCode.UPLOAD_FORMAT_UNSUPPORTED,
        ]),
    )
    @settings(max_examples=50)
    def test_upload_error_response_is_serializable(
        self, filename: str, error_code: ErrorCode
    ):
        """
        **Property 59: Error Logging and User Messages**
        Validates: Requirements 17.5

        Upload error responses SHALL be serializable to dict.
        """
        response = make_upload_error(filename, error_code)
        data = response.model_dump()
        assert isinstance(data, dict)
        assert "user_message" in data
        assert "filename" in data
        assert "retry_options" in data


# ---------------------------------------------------------------------------
# Retry configuration tests
# ---------------------------------------------------------------------------


class TestRetryConfiguration:
    """Unit tests for retry delay calculation (supports Req 17.3)."""

    @given(
        attempt=st.integers(min_value=0, max_value=10),
        base_delay=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
        max_delay=st.floats(min_value=1.0, max_value=300.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_retry_delay_never_exceeds_max(
        self, attempt: int, base_delay: float, max_delay: float
    ):
        """
        Retry delay SHALL never exceed max_delay_seconds.
        """
        if base_delay > max_delay:
            max_delay = base_delay * 2  # Ensure max > base

        config = RetryConfig(
            max_retries=10,
            base_delay_seconds=base_delay,
            max_delay_seconds=max_delay,
        )
        delay = calculate_retry_delay(attempt, config)
        assert delay <= max_delay

    @given(
        attempt=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=50)
    def test_retry_delay_is_non_negative(self, attempt: int):
        """Retry delay SHALL always be non-negative."""
        config = RetryConfig()
        delay = calculate_retry_delay(attempt, config)
        assert delay >= 0.0

    def test_retry_delay_increases_with_attempts(self):
        """Retry delay SHALL increase with each attempt (exponential backoff)."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=1000.0,
            exponential_base=2.0,
        )
        delays = [calculate_retry_delay(i, config) for i in range(5)]
        # Each delay should be greater than the previous
        for i in range(1, len(delays)):
            assert delays[i] > delays[i - 1], (
                f"Delay at attempt {i} ({delays[i]}) should be > attempt {i-1} ({delays[i-1]})"
            )
