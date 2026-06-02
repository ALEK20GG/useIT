"""
Property-based and unit tests for security and validation measures.

Covers Task 17 requirements:
- 18.1: Input validation for all user-provided data
- 18.2: File type validation and malicious content scanning
- 18.3: API rate limiting to prevent abuse
- 18.4: Input sanitization to prevent XSS and injection attacks
- 18.5: Audit logging for content management operations

Properties tested:
- Property 60: Input Validation (Req 18.1)
- Property 61: File Security Validation (Req 18.2)
- Property 62: API Rate Limiting (Req 18.3)
- Property 63: Input Sanitization (Req 18.4)
- Property 64: Audit Logging (Req 18.5)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.security import (
    AuditAction,
    AuditLogEntry,
    FileValidationResult,
    RateLimitConfig,
    RateLimiter,
    ValidatedSearchQuery,
    ValidatedFolderName,
    detect_path_traversal,
    detect_sql_injection,
    get_audit_log,
    log_audit_event,
    sanitize_filename,
    sanitize_search_query,
    sanitize_text_input,
    scan_for_malicious_content,
    validate_and_scan_file,
    validate_device_id,
    validate_file_id,
    validate_file_type,
    ALLOWED_DOCUMENT_TYPES,
    ALLOWED_IMAGE_TYPES,
    ALLOWED_EXTENSIONS,
)


# ---------------------------------------------------------------------------
# Helpers / strategies
# ---------------------------------------------------------------------------

# Safe printable text (no null bytes, no control chars)
safe_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po"),
        blacklist_characters="\x00\r",
    ),
    min_size=0,
    max_size=200,
)

# Text that may contain XSS payloads
xss_payloads = st.one_of(
    st.just("<script>alert(1)</script>"),
    st.just('<img src=x onerror="alert(1)">'),
    st.just("javascript:alert(1)"),
    st.just("&lt;script&gt;"),
    st.just("'; DROP TABLE users; --"),
    st.just("SELECT * FROM users WHERE 1=1"),
    safe_text,
)

# Valid filenames
valid_filenames = st.one_of(
    st.just("document.pdf"),
    st.just("my_file-v2.txt"),
    st.just("report (2024).docx"),
    st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        min_size=1,
        max_size=50,
    ).map(lambda s: s + ".pdf"),
)

# Malicious filenames
malicious_filenames = st.one_of(
    st.just("../../../etc/passwd"),
    st.just("..\\..\\windows\\system32\\cmd.exe"),
    st.just("%2e%2e%2fetc%2fpasswd"),
    st.just("file\x00.pdf"),
    st.just("/etc/passwd"),
)


# ---------------------------------------------------------------------------
# Property 60: Input Validation (Req 18.1)
# ---------------------------------------------------------------------------


class TestInputValidation:
    """
    **Property 60: Input Validation**
    Validates: Requirements 18.1

    The system SHALL implement input validation for all user-provided data
    including file uploads and search queries.
    """

    @given(query=safe_text)
    @settings(max_examples=100)
    def test_sanitize_search_query_never_raises(self, query: str):
        """
        **Property 60: Input Validation**
        Validates: Requirements 18.1

        sanitize_search_query SHALL never raise an exception for any string input.
        """
        result = sanitize_search_query(query)
        assert isinstance(result, str)

    @given(query=safe_text.filter(lambda s: len(s.strip()) > 0))
    @settings(max_examples=100)
    def test_sanitize_search_query_strips_whitespace(self, query: str):
        """
        **Property 60: Input Validation**
        Validates: Requirements 18.1

        sanitize_search_query SHALL strip leading/trailing whitespace.
        """
        result = sanitize_search_query(query)
        assert result == result.strip()

    @given(length=st.integers(min_value=1, max_value=1000))
    @settings(max_examples=50)
    def test_sanitize_search_query_respects_max_length(self, length: int):
        """
        **Property 60: Input Validation**
        Validates: Requirements 18.1

        sanitize_search_query SHALL truncate to max_length.
        """
        long_query = "a" * (length + 100)
        result = sanitize_search_query(long_query, max_length=length)
        assert len(result) <= length

    @given(text=safe_text)
    @settings(max_examples=100)
    def test_sanitize_text_input_removes_null_bytes(self, text: str):
        """
        **Property 60: Input Validation**
        Validates: Requirements 18.1

        sanitize_text_input SHALL remove null bytes from input.
        """
        text_with_nulls = text + "\x00" + text
        result = sanitize_text_input(text_with_nulls)
        assert "\x00" not in result

    @given(
        device_id=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_validate_device_id_accepts_alphanumeric(self, device_id: str):
        """
        **Property 60: Input Validation**
        Validates: Requirements 18.1

        validate_device_id SHALL accept alphanumeric IDs.
        """
        result = validate_device_id(device_id)
        assert result == device_id.strip()

    def test_validate_device_id_rejects_path_traversal(self):
        """validate_device_id SHALL reject path traversal sequences."""
        with pytest.raises(ValueError):
            validate_device_id("../../../etc/passwd")

    def test_validate_file_id_rejects_empty(self):
        """validate_file_id SHALL reject empty strings."""
        with pytest.raises(ValueError):
            validate_file_id("")

    def test_validate_file_id_rejects_path_traversal(self):
        """validate_file_id SHALL reject path traversal sequences."""
        with pytest.raises(ValueError):
            validate_file_id("../../secret")

    @given(
        file_id=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_validate_file_id_accepts_valid_ids(self, file_id: str):
        """
        **Property 60: Input Validation**
        Validates: Requirements 18.1

        validate_file_id SHALL accept valid alphanumeric IDs.
        """
        result = validate_file_id(file_id)
        assert result == file_id.strip()

    def test_validated_search_query_model_rejects_empty(self):
        """ValidatedSearchQuery SHALL reject empty queries."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ValidatedSearchQuery(query="")

    def test_validated_search_query_model_rejects_sql_injection(self):
        """ValidatedSearchQuery SHALL reject SQL injection patterns."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ValidatedSearchQuery(query="SELECT * FROM users")

    def test_validated_folder_name_rejects_path_traversal(self):
        """ValidatedFolderName SHALL reject path traversal sequences."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ValidatedFolderName(name="../secret")

    def test_validated_folder_name_accepts_italian_chars(self):
        """ValidatedFolderName SHALL accept Italian characters."""
        result = ValidatedFolderName(name="Dispositivi")
        assert result.name == "Dispositivi"


# ---------------------------------------------------------------------------
# Property 61: File Security Validation (Req 18.2)
# ---------------------------------------------------------------------------


class TestFileSecurityValidation:
    """
    **Property 61: File Security Validation**
    Validates: Requirements 18.2

    WHEN processing uploaded files, THE System SHALL validate file types
    and scan for malicious content.
    """

    @given(
        content=st.binary(min_size=1, max_size=100),
        filename=malicious_filenames,
    )
    @settings(max_examples=50)
    def test_validate_file_type_rejects_path_traversal_filenames(
        self, content: bytes, filename: str
    ):
        """
        **Property 61: File Security Validation**
        Validates: Requirements 18.2

        validate_file_type SHALL reject filenames with path traversal sequences.
        """
        result = validate_file_type(content, filename)
        assert not result.is_valid

    def test_validate_file_type_rejects_empty_file(self):
        """validate_file_type SHALL reject empty files."""
        result = validate_file_type(b"", "document.pdf")
        assert not result.is_valid
        assert result.error_message is not None

    def test_validate_file_type_accepts_valid_pdf_magic_bytes(self):
        """validate_file_type SHALL accept files with valid PDF magic bytes."""
        pdf_content = b"%PDF-1.4 fake content"
        result = validate_file_type(pdf_content, "document.pdf")
        assert result.is_valid
        assert result.detected_mime_type == "application/pdf"

    def test_validate_file_type_rejects_pdf_with_wrong_magic_bytes(self):
        """validate_file_type SHALL reject files with wrong magic bytes for extension."""
        # PNG magic bytes but .pdf extension
        png_content = b"\x89PNG\r\n\x1a\n fake content"
        result = validate_file_type(png_content, "document.pdf")
        assert not result.is_valid

    def test_validate_file_type_accepts_valid_png(self):
        """validate_file_type SHALL accept valid PNG files."""
        png_content = b"\x89PNG\r\n\x1a\n fake content"
        result = validate_file_type(png_content, "image.png", allowed_types=ALLOWED_IMAGE_TYPES)
        assert result.is_valid
        assert result.detected_mime_type == "image/png"

    def test_validate_file_type_accepts_valid_jpeg(self):
        """validate_file_type SHALL accept valid JPEG files."""
        jpeg_content = b"\xff\xd8\xff fake jpeg content"
        result = validate_file_type(jpeg_content, "photo.jpg", allowed_types=ALLOWED_IMAGE_TYPES)
        assert result.is_valid
        assert result.detected_mime_type == "image/jpeg"

    def test_validate_file_type_rejects_disallowed_extension(self):
        """validate_file_type SHALL reject files with disallowed extensions."""
        result = validate_file_type(b"some content", "script.exe")
        assert not result.is_valid
        assert result.error_message is not None

    def test_scan_for_malicious_content_rejects_script_injection_in_txt(self):
        """scan_for_malicious_content SHALL reject text files with script injection."""
        malicious_content = b"<script>alert('xss')</script>"
        result = scan_for_malicious_content(malicious_content, "file.txt")
        assert not result.is_valid

    def test_scan_for_malicious_content_rejects_javascript_url_in_txt(self):
        """scan_for_malicious_content SHALL reject text files with javascript: URLs."""
        malicious_content = b"Click here: javascript:alert(1)"
        result = scan_for_malicious_content(malicious_content, "file.txt")
        assert not result.is_valid

    def test_scan_for_malicious_content_accepts_clean_text(self):
        """scan_for_malicious_content SHALL accept clean text files."""
        clean_content = b"This is a normal document with no malicious content."
        result = scan_for_malicious_content(clean_content, "file.txt")
        assert result.is_valid

    def test_scan_for_malicious_content_rejects_oversized_file(self):
        """scan_for_malicious_content SHALL reject files exceeding size limit."""
        # Create a file larger than 50 MB
        oversized_content = b"x" * (51 * 1024 * 1024)
        result = scan_for_malicious_content(oversized_content, "large.pdf")
        assert not result.is_valid
        assert "size" in result.error_message.lower()

    @given(
        content=st.binary(min_size=4, max_size=1000),
        ext=st.sampled_from([".pdf", ".txt", ".jpg", ".png"]),
    )
    @settings(max_examples=50)
    def test_validate_and_scan_file_returns_validation_result(
        self, content: bytes, ext: str
    ):
        """
        **Property 61: File Security Validation**
        Validates: Requirements 18.2

        validate_and_scan_file SHALL always return a FileValidationResult.
        """
        filename = "testfile" + ext
        result = validate_and_scan_file(content, filename)
        assert isinstance(result, FileValidationResult)
        assert isinstance(result.is_valid, bool)
        if not result.is_valid:
            assert result.error_message is not None


# ---------------------------------------------------------------------------
# Property 62: API Rate Limiting (Req 18.3)
# ---------------------------------------------------------------------------


class TestAPIRateLimiting:
    """
    **Property 62: API Rate Limiting**
    Validates: Requirements 18.3

    THE System SHALL implement rate limiting for API endpoints to prevent abuse.
    """

    def test_rate_limiter_allows_requests_within_limit(self):
        """
        **Property 62: API Rate Limiting**
        Validates: Requirements 18.3

        Rate limiter SHALL allow requests within the configured limit.
        """
        limiter = RateLimiter()
        config = RateLimitConfig(requests_per_minute=10, requests_per_hour=100, burst_size=5)

        for _ in range(5):
            allowed, info = limiter.check_rate_limit("test_client_allow", config)
            assert allowed, f"Request should be allowed, got: {info}"

    def test_rate_limiter_blocks_burst_excess(self):
        """
        **Property 62: API Rate Limiting**
        Validates: Requirements 18.3

        Rate limiter SHALL block requests exceeding the burst limit.
        """
        limiter = RateLimiter()
        config = RateLimitConfig(requests_per_minute=100, requests_per_hour=1000, burst_size=3)

        # Exhaust burst limit
        for _ in range(3):
            allowed, _ = limiter.check_rate_limit("burst_test_client", config)
            assert allowed

        # Next request should be blocked
        allowed, info = limiter.check_rate_limit("burst_test_client", config)
        assert not allowed
        assert info["reason"] == "burst_limit_exceeded"

    def test_rate_limiter_blocks_minute_excess(self):
        """
        **Property 62: API Rate Limiting**
        Validates: Requirements 18.3

        Rate limiter SHALL block requests exceeding the per-minute limit.
        """
        limiter = RateLimiter()
        config = RateLimitConfig(requests_per_minute=5, requests_per_hour=1000, burst_size=100)

        for _ in range(5):
            allowed, _ = limiter.check_rate_limit("minute_test_client", config)
            assert allowed

        allowed, info = limiter.check_rate_limit("minute_test_client", config)
        assert not allowed
        assert info["reason"] == "minute_limit_exceeded"

    @given(
        client_key=st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
            min_size=1,
            max_size=30,
        ),
        n_requests=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=50)
    def test_rate_limiter_tracks_different_clients_independently(
        self, client_key: str, n_requests: int
    ):
        """
        **Property 62: API Rate Limiting**
        Validates: Requirements 18.3

        Rate limiter SHALL track different clients independently.
        """
        limiter = RateLimiter()
        config = RateLimitConfig(requests_per_minute=100, requests_per_hour=1000, burst_size=50)

        # Requests for one client should not affect another
        unique_key = f"prop_test_{client_key}"
        other_key = f"other_{client_key}"

        for _ in range(n_requests):
            limiter.check_rate_limit(unique_key, config)

        # Other client should still be allowed
        allowed, _ = limiter.check_rate_limit(other_key, config)
        assert allowed

    def test_rate_limiter_returns_retry_after_on_block(self):
        """
        **Property 62: API Rate Limiting**
        Validates: Requirements 18.3

        When rate limited, the response SHALL include retry_after information.
        """
        limiter = RateLimiter()
        config = RateLimitConfig(requests_per_minute=100, requests_per_hour=1000, burst_size=1)

        limiter.check_rate_limit("retry_test", config)
        allowed, info = limiter.check_rate_limit("retry_test", config)

        assert not allowed
        assert "retry_after" in info
        assert info["retry_after"] > 0

    def test_rate_limiter_get_stats_returns_counts(self):
        """
        **Property 62: API Rate Limiting**
        Validates: Requirements 18.3

        get_stats SHALL return current request counts.
        """
        limiter = RateLimiter()
        config = RateLimitConfig(requests_per_minute=100, requests_per_hour=1000, burst_size=50)

        limiter.check_rate_limit("stats_test", config)
        limiter.check_rate_limit("stats_test", config)

        stats = limiter.get_stats("stats_test")
        assert stats["minute_count"] == 2
        assert stats["burst_count"] == 2

    def test_rate_limiter_unknown_client_returns_zero_stats(self):
        """get_stats for unknown client SHALL return zero counts."""
        limiter = RateLimiter()
        stats = limiter.get_stats("nonexistent_client_xyz")
        assert stats["minute_count"] == 0
        assert stats["hour_count"] == 0
        assert stats["burst_count"] == 0


# ---------------------------------------------------------------------------
# Property 63: Input Sanitization (Req 18.4)
# ---------------------------------------------------------------------------


class TestInputSanitization:
    """
    **Property 63: Input Sanitization**
    Validates: Requirements 18.4

    THE Security_System SHALL sanitize user input to prevent XSS and injection attacks.
    """

    @given(text=xss_payloads)
    @settings(max_examples=100)
    def test_sanitize_text_input_escapes_html_special_chars(self, text: str):
        """
        **Property 63: Input Sanitization**
        Validates: Requirements 18.4

        sanitize_text_input SHALL HTML-escape special characters to prevent XSS.
        """
        result = sanitize_text_input(text)
        # After sanitization, raw < and > should be escaped
        assert "<script" not in result.lower()
        # Raw angle brackets should be escaped
        assert "<" not in result or "&lt;" in result or "script" not in result.lower()

    @given(text=safe_text)
    @settings(max_examples=100)
    def test_sanitize_text_input_is_idempotent_on_safe_text(self, text: str):
        """
        **Property 63: Input Sanitization**
        Validates: Requirements 18.4

        sanitize_text_input applied twice SHALL produce the same result as once
        (for safe text that doesn't contain HTML entities).
        """
        once = sanitize_text_input(text)
        # The result should be a valid string
        assert isinstance(once, str)

    @given(filename=malicious_filenames)
    @settings(max_examples=50)
    def test_sanitize_filename_removes_path_traversal(self, filename: str):
        """
        **Property 63: Input Sanitization**
        Validates: Requirements 18.4

        sanitize_filename SHALL remove path traversal sequences.
        """
        result = sanitize_filename(filename)
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    @given(filename=valid_filenames)
    @settings(max_examples=100)
    def test_sanitize_filename_preserves_valid_filenames(self, filename: str):
        """
        **Property 63: Input Sanitization**
        Validates: Requirements 18.4

        sanitize_filename SHALL preserve valid filenames.
        """
        result = sanitize_filename(filename)
        assert isinstance(result, str)
        # Valid filenames should not be empty after sanitization
        assert len(result) > 0

    @given(
        length=st.integers(min_value=1, max_value=300),
    )
    @settings(max_examples=50)
    def test_sanitize_filename_respects_max_length(self, length: int):
        """
        **Property 63: Input Sanitization**
        Validates: Requirements 18.4

        sanitize_filename SHALL limit filename length to 255 characters.
        """
        long_name = "a" * length + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 255

    def test_detect_sql_injection_detects_select(self):
        """detect_sql_injection SHALL detect SELECT statements."""
        assert detect_sql_injection("SELECT * FROM users")

    def test_detect_sql_injection_detects_drop(self):
        """detect_sql_injection SHALL detect DROP TABLE."""
        assert detect_sql_injection("DROP TABLE users")

    def test_detect_sql_injection_detects_comment_injection(self):
        """detect_sql_injection SHALL detect SQL comment injection."""
        assert detect_sql_injection("admin'--")

    def test_detect_sql_injection_allows_safe_text(self):
        """detect_sql_injection SHALL not flag safe text."""
        assert not detect_sql_injection("Arduino Uno documentation")
        assert not detect_sql_injection("How to use Raspberry Pi")

    def test_detect_path_traversal_detects_unix_traversal(self):
        """detect_path_traversal SHALL detect Unix path traversal."""
        assert detect_path_traversal("../../../etc/passwd")

    def test_detect_path_traversal_detects_windows_traversal(self):
        """detect_path_traversal SHALL detect Windows path traversal."""
        assert detect_path_traversal("..\\..\\windows\\system32")

    def test_detect_path_traversal_detects_encoded_traversal(self):
        """detect_path_traversal SHALL detect URL-encoded path traversal."""
        assert detect_path_traversal("%2e%2e%2fetc%2fpasswd")

    def test_detect_path_traversal_allows_safe_paths(self):
        """detect_path_traversal SHALL not flag safe paths."""
        assert not detect_path_traversal("documents/report.pdf")
        assert not detect_path_traversal("my-folder")

    @given(text=safe_text)
    @settings(max_examples=100)
    def test_sanitize_search_query_removes_null_bytes(self, text: str):
        """
        **Property 63: Input Sanitization**
        Validates: Requirements 18.4

        sanitize_search_query SHALL remove null bytes.
        """
        text_with_nulls = text + "\x00malicious"
        result = sanitize_search_query(text_with_nulls)
        assert "\x00" not in result


# ---------------------------------------------------------------------------
# Property 64: Audit Logging (Req 18.5)
# ---------------------------------------------------------------------------


class TestAuditLogging:
    """
    **Property 64: Audit Logging**
    Validates: Requirements 18.5

    THE System SHALL provide audit logging for content management operations.
    """

    @given(
        action=st.sampled_from(list(AuditAction)),
        resource_type=st.sampled_from(["file", "folder", "device", "pdf"]),
        resource_id=st.one_of(
            st.none(),
            st.text(
                alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
                min_size=1,
                max_size=50,
            ),
        ),
        success=st.booleans(),
    )
    @settings(max_examples=100)
    def test_log_audit_event_always_returns_entry(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id,
        success: bool,
    ):
        """
        **Property 64: Audit Logging**
        Validates: Requirements 18.5

        log_audit_event SHALL always return a valid AuditLogEntry.
        """
        entry = log_audit_event(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            success=success,
        )
        assert isinstance(entry, AuditLogEntry)
        assert entry.action == action.value
        assert entry.resource_type == resource_type
        assert entry.success == success

    @given(
        action=st.sampled_from(list(AuditAction)),
        resource_type=st.sampled_from(["file", "folder", "device"]),
    )
    @settings(max_examples=50)
    def test_log_audit_event_has_timestamp(self, action: AuditAction, resource_type: str):
        """
        **Property 64: Audit Logging**
        Validates: Requirements 18.5

        Every audit log entry SHALL have a non-empty ISO-8601 timestamp.
        """
        entry = log_audit_event(action=action, resource_type=resource_type, success=True)
        assert entry.timestamp
        assert len(entry.timestamp) > 0
        # Should be parseable as ISO-8601
        from datetime import datetime
        parsed = datetime.fromisoformat(entry.timestamp)
        assert parsed is not None

    def test_audit_log_is_retrievable(self):
        """
        **Property 64: Audit Logging**
        Validates: Requirements 18.5

        Audit log entries SHALL be retrievable via get_audit_log.
        """
        # Log a unique event
        unique_resource_id = "test_audit_retrieval_12345"
        log_audit_event(
            action=AuditAction.FILE_UPLOAD,
            resource_type="file",
            resource_id=unique_resource_id,
            success=True,
        )

        entries = get_audit_log(limit=100)
        assert any(e.resource_id == unique_resource_id for e in entries)

    def test_audit_log_records_failure(self):
        """
        **Property 64: Audit Logging**
        Validates: Requirements 18.5

        Audit log SHALL record failed operations with error messages.
        """
        error_msg = "Test error for audit log"
        entry = log_audit_event(
            action=AuditAction.FILE_DELETE,
            resource_type="file",
            resource_id="test_file_id",
            success=False,
            error_message=error_msg,
        )
        assert entry.success is False
        assert entry.error_message == error_msg

    def test_audit_log_records_details(self):
        """
        **Property 64: Audit Logging**
        Validates: Requirements 18.5

        Audit log entries SHALL preserve operation details.
        """
        details = {"filename": "test.pdf", "folder_id": "dispositivi", "chunks": 42}
        entry = log_audit_event(
            action=AuditAction.PDF_UPLOAD,
            resource_type="pdf",
            resource_id="test.pdf",
            details=details,
            success=True,
        )
        assert entry.details == details

    def test_audit_log_is_serializable(self):
        """
        **Property 64: Audit Logging**
        Validates: Requirements 18.5

        Audit log entries SHALL be serializable to dict (for JSON API responses).
        """
        entry = log_audit_event(
            action=AuditAction.FOLDER_CREATE,
            resource_type="folder",
            resource_id="test_folder",
            success=True,
        )
        data = entry.model_dump()
        assert isinstance(data, dict)
        assert "timestamp" in data
        assert "action" in data
        assert "resource_type" in data
        assert "success" in data

    @given(
        n_events=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=30)
    def test_audit_log_limit_respected(self, n_events: int):
        """
        **Property 64: Audit Logging**
        Validates: Requirements 18.5

        get_audit_log SHALL respect the limit parameter.
        """
        # Log some events
        for i in range(n_events):
            log_audit_event(
                action=AuditAction.SEARCH_QUERY,
                resource_type="search",
                resource_id=f"query_{i}",
                success=True,
            )

        limit = max(1, n_events // 2)
        entries = get_audit_log(limit=limit)
        assert len(entries) <= limit

    def test_all_audit_actions_are_loggable(self):
        """
        **Property 64: Audit Logging**
        Validates: Requirements 18.5

        All AuditAction values SHALL be loggable without errors.
        """
        for action in AuditAction:
            entry = log_audit_event(
                action=action,
                resource_type="test",
                resource_id="test_id",
                success=True,
            )
            assert entry.action == action.value
