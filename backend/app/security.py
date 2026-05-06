"""
Security utilities for the Intelligent Device Documentation Platform.

Implements Requirements 18.1-18.5:
- 18.1: Input validation for all user-provided data
- 18.2: File type validation and malicious content scanning
- 18.3: API rate limiting to prevent abuse
- 18.4: Input sanitization to prevent XSS and injection attacks
- 18.5: Audit logging for content management operations
"""

import hashlib
import html
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audit logging (Requirement 18.5)
# ---------------------------------------------------------------------------


class AuditAction(str, Enum):
    """Audit log action types for content management operations."""

    FILE_UPLOAD = "file_upload"
    FILE_DELETE = "file_delete"
    FILE_BULK_DELETE = "file_bulk_delete"
    FILE_DOWNLOAD = "file_download"
    FOLDER_CREATE = "folder_create"
    FOLDER_UPDATE = "folder_update"
    FOLDER_DELETE = "folder_delete"
    CONTENT_ASSIGN = "content_assign"
    CONTENT_MOVE = "content_move"
    DEVICE_CREATE = "device_create"
    DEVICE_UPDATE = "device_update"
    DEVICE_DELETE = "device_delete"
    SEARCH_QUERY = "search_query"
    PDF_UPLOAD = "pdf_upload"
    PDF_DELETE = "pdf_delete"


class AuditLogEntry(BaseModel):
    """A single audit log entry."""

    timestamp: str = Field(description="ISO-8601 UTC timestamp")
    action: str = Field(description="Action performed")
    resource_type: str = Field(description="Type of resource affected")
    resource_id: str | None = Field(None, description="ID of the affected resource")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")
    success: bool = Field(description="Whether the operation succeeded")
    error_message: str | None = Field(None, description="Error message if operation failed")
    client_ip: str | None = Field(None, description="Client IP address if available")


# Module-level in-memory audit log (last 1000 entries)
_audit_log: list[AuditLogEntry] = []
_MAX_AUDIT_LOG_SIZE = 1000

# Dedicated audit logger for structured output
_audit_logger = logging.getLogger("audit")


def log_audit_event(
    action: AuditAction,
    resource_type: str,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    success: bool = True,
    error_message: str | None = None,
    client_ip: str | None = None,
) -> AuditLogEntry:
    """
    Record an audit log entry for a content management operation.

    Requirement 18.5: audit logging for content management operations.
    """
    entry = AuditLogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        action=action.value,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        success=success,
        error_message=error_message,
        client_ip=client_ip,
    )

    # Append to in-memory log (ring buffer)
    global _audit_log
    _audit_log.append(entry)
    if len(_audit_log) > _MAX_AUDIT_LOG_SIZE:
        _audit_log = _audit_log[-_MAX_AUDIT_LOG_SIZE:]

    # Emit to structured logger
    log_level = logging.INFO if success else logging.WARNING
    _audit_logger.log(
        log_level,
        "AUDIT | action=%s resource_type=%s resource_id=%s success=%s",
        entry.action,
        entry.resource_type,
        entry.resource_id or "-",
        entry.success,
        extra={"audit_entry": entry.model_dump()},
    )

    return entry


def get_audit_log(limit: int = 100) -> list[AuditLogEntry]:
    """Return the most recent audit log entries."""
    return _audit_log[-limit:]


# ---------------------------------------------------------------------------
# Rate limiting (Requirement 18.3)
# ---------------------------------------------------------------------------


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""

    requests_per_minute: int = 60
    requests_per_hour: int = 600
    burst_size: int = 10  # Max requests in a short burst window (10 seconds)


@dataclass
class _RateLimitBucket:
    """Sliding-window counters for a single client key."""

    minute_window: list[float] = field(default_factory=list)
    hour_window: list[float] = field(default_factory=list)
    burst_window: list[float] = field(default_factory=list)


class RateLimiter:
    """
    In-memory sliding-window rate limiter.

    Requirement 18.3: rate limiting for API endpoints to prevent abuse.
    """

    # Default configs per endpoint category
    DEFAULT_CONFIG = RateLimitConfig(
        requests_per_minute=60,
        requests_per_hour=600,
        burst_size=10,
    )
    UPLOAD_CONFIG = RateLimitConfig(
        requests_per_minute=20,
        requests_per_hour=100,
        burst_size=5,
    )
    SEARCH_CONFIG = RateLimitConfig(
        requests_per_minute=120,
        requests_per_hour=1200,
        burst_size=20,
    )
    DEVICE_RECOGNITION_CONFIG = RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=200,
        burst_size=5,
    )

    def __init__(self) -> None:
        self._buckets: dict[str, _RateLimitBucket] = defaultdict(_RateLimitBucket)

    def _clean_window(self, timestamps: list[float], window_seconds: float) -> list[float]:
        """Remove timestamps outside the sliding window."""
        cutoff = time.monotonic() - window_seconds
        return [t for t in timestamps if t > cutoff]

    def check_rate_limit(
        self,
        client_key: str,
        config: RateLimitConfig | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check whether a request from *client_key* is within rate limits.

        Returns (allowed, info_dict).
        - allowed=True  → request is permitted
        - allowed=False → request is rate-limited
        """
        cfg = config or self.DEFAULT_CONFIG
        bucket = self._buckets[client_key]
        now = time.monotonic()

        # Clean expired entries
        bucket.minute_window = self._clean_window(bucket.minute_window, 60)
        bucket.hour_window = self._clean_window(bucket.hour_window, 3600)
        bucket.burst_window = self._clean_window(bucket.burst_window, 10)

        minute_count = len(bucket.minute_window)
        hour_count = len(bucket.hour_window)
        burst_count = len(bucket.burst_window)

        # Check limits
        if burst_count >= cfg.burst_size:
            return False, {
                "reason": "burst_limit_exceeded",
                "limit": cfg.burst_size,
                "window": "10s",
                "current": burst_count,
                "retry_after": 10,
            }
        if minute_count >= cfg.requests_per_minute:
            return False, {
                "reason": "minute_limit_exceeded",
                "limit": cfg.requests_per_minute,
                "window": "60s",
                "current": minute_count,
                "retry_after": 60,
            }
        if hour_count >= cfg.requests_per_hour:
            return False, {
                "reason": "hour_limit_exceeded",
                "limit": cfg.requests_per_hour,
                "window": "3600s",
                "current": hour_count,
                "retry_after": 3600,
            }

        # Record the request
        bucket.minute_window.append(now)
        bucket.hour_window.append(now)
        bucket.burst_window.append(now)

        return True, {
            "minute_remaining": cfg.requests_per_minute - minute_count - 1,
            "hour_remaining": cfg.requests_per_hour - hour_count - 1,
        }

    def get_stats(self, client_key: str) -> dict[str, Any]:
        """Return current rate limit counters for a client key."""
        bucket = self._buckets.get(client_key)
        if bucket is None:
            return {"minute_count": 0, "hour_count": 0, "burst_count": 0}
        return {
            "minute_count": len(self._clean_window(bucket.minute_window, 60)),
            "hour_count": len(self._clean_window(bucket.hour_window, 3600)),
            "burst_count": len(self._clean_window(bucket.burst_window, 10)),
        }


# Module-level singleton
_rate_limiter = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Return the global RateLimiter instance."""
    return _rate_limiter


# ---------------------------------------------------------------------------
# Input sanitization (Requirement 18.4)
# ---------------------------------------------------------------------------

# Patterns that indicate potential injection attempts
_SQL_INJECTION_PATTERNS = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION|SCRIPT)\b"
    r"|--|;|\bOR\b\s+\d+\s*=\s*\d+|\bAND\b\s+\d+\s*=\s*\d+)",
    re.IGNORECASE,
)

_PATH_TRAVERSAL_PATTERN = re.compile(r"\.\./|\.\.\\|%2e%2e%2f|%2e%2e/|\.\.%2f", re.IGNORECASE)

_NULL_BYTE_PATTERN = re.compile(r"\x00|%00")

# Characters that are safe in filenames
_SAFE_FILENAME_PATTERN = re.compile(r"[^\w\s\-_\.\(\)\[\]]+", re.UNICODE)


def sanitize_text_input(text: str, max_length: int = 10_000) -> str:
    """
    Sanitize a text input to prevent XSS and injection attacks.

    - Strips leading/trailing whitespace
    - Removes null bytes
    - HTML-escapes special characters
    - Truncates to max_length

    Requirement 18.4: sanitize user input to prevent XSS and injection attacks.
    """
    if not isinstance(text, str):
        text = str(text)

    # Remove null bytes
    text = _NULL_BYTE_PATTERN.sub("", text)

    # Strip whitespace
    text = text.strip()

    # Truncate
    if len(text) > max_length:
        text = text[:max_length]

    # HTML-escape to prevent XSS
    text = html.escape(text, quote=True)

    return text


def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """
    Sanitize a search query.

    Lighter sanitization than full HTML escaping so that the query remains
    useful for semantic search while still being safe.

    Requirement 18.4 + 18.1.
    """
    if not isinstance(query, str):
        query = str(query)

    # Remove null bytes
    query = _NULL_BYTE_PATTERN.sub("", query)

    # Strip whitespace
    query = query.strip()

    # Truncate
    if len(query) > max_length:
        query = query[:max_length]

    return query


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and injection.

    - Removes path separators and traversal sequences
    - Replaces unsafe characters with underscores
    - Limits length to 255 characters

    Requirement 18.4.
    """
    if not isinstance(filename, str):
        filename = str(filename)

    # Remove null bytes
    filename = _NULL_BYTE_PATTERN.sub("", filename)

    # Remove path traversal sequences
    filename = _PATH_TRAVERSAL_PATTERN.sub("", filename)

    # Remove directory separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Replace unsafe characters
    filename = _SAFE_FILENAME_PATTERN.sub("_", filename)

    # Limit length (preserve extension)
    if len(filename) > 255:
        stem = Path(filename).stem[:240]
        suffix = Path(filename).suffix[:15]
        filename = stem + suffix

    return filename.strip("._")


def detect_sql_injection(text: str) -> bool:
    """
    Return True if the text contains patterns that look like SQL injection.

    Requirement 18.4.
    """
    return bool(_SQL_INJECTION_PATTERNS.search(text))


def detect_path_traversal(text: str) -> bool:
    """
    Return True if the text contains path traversal sequences.

    Requirement 18.4.
    """
    return bool(_PATH_TRAVERSAL_PATTERN.search(text))


# ---------------------------------------------------------------------------
# File type validation and malicious content scanning (Requirement 18.2)
# ---------------------------------------------------------------------------

# Magic bytes for allowed file types
_MAGIC_BYTES: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],  # RIFF....WEBP
    "image/gif": [b"GIF87a", b"GIF89a"],
    "text/plain": [],  # No magic bytes; validated by content check
    "application/msword": [b"\xd0\xcf\x11\xe0"],  # OLE2 compound document
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        b"PK\x03\x04"  # ZIP-based OOXML
    ],
}

# Allowed MIME types for document uploads
ALLOWED_DOCUMENT_TYPES = {
    "application/pdf",
    "text/plain",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Allowed MIME types for image uploads
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

# Allowed file extensions mapped to MIME types
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

# Patterns that indicate potentially malicious content in text files
_MALICIOUS_PATTERNS = [
    re.compile(r"<script[\s>]", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"vbscript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # onload=, onclick=, etc.
    re.compile(r"data:text/html", re.IGNORECASE),
    re.compile(r"eval\s*\(", re.IGNORECASE),
]

# Maximum file sizes
MAX_DOCUMENT_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@dataclass
class FileValidationResult:
    """Result of file type and content validation."""

    is_valid: bool
    detected_mime_type: str | None
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)


def validate_file_type(
    file_data: bytes,
    filename: str,
    allowed_types: set[str] | None = None,
) -> FileValidationResult:
    """
    Validate a file's type using magic bytes and extension checks.

    Requirement 18.2: validate file types when processing uploaded files.
    """
    if not file_data:
        return FileValidationResult(
            is_valid=False,
            detected_mime_type=None,
            error_message="File is empty",
        )

    # Determine allowed types
    if allowed_types is None:
        allowed_types = ALLOWED_DOCUMENT_TYPES | ALLOWED_IMAGE_TYPES

    # Check extension
    ext = Path(filename).suffix.lower()
    expected_mime = ALLOWED_EXTENSIONS.get(ext)
    if expected_mime is None:
        return FileValidationResult(
            is_valid=False,
            detected_mime_type=None,
            error_message=f"File extension '{ext}' is not allowed. "
            f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS.keys()))}",
        )

    if expected_mime not in allowed_types:
        return FileValidationResult(
            is_valid=False,
            detected_mime_type=expected_mime,
            error_message=f"File type '{expected_mime}' is not allowed for this operation.",
        )

    # Validate magic bytes
    magic_signatures = _MAGIC_BYTES.get(expected_mime, [])
    if magic_signatures:
        header = file_data[:16]
        matched = any(header.startswith(sig) for sig in magic_signatures)

        # Special case: WebP has RIFF....WEBP structure
        if expected_mime == "image/webp" and not matched:
            matched = file_data[:4] == b"RIFF" and file_data[8:12] == b"WEBP"

        if not matched:
            return FileValidationResult(
                is_valid=False,
                detected_mime_type=None,
                error_message=f"File content does not match the expected type for '{ext}'. "
                "The file may be corrupted or misnamed.",
            )

    return FileValidationResult(
        is_valid=True,
        detected_mime_type=expected_mime,
    )


def scan_for_malicious_content(file_data: bytes, filename: str) -> FileValidationResult:
    """
    Scan file content for potentially malicious patterns.

    Performs a lightweight heuristic scan:
    - Checks text files for embedded scripts and injection patterns
    - Checks for suspicious embedded content in documents

    Requirement 18.2: scan for malicious content.
    """
    ext = Path(filename).suffix.lower()
    warnings: list[str] = []

    # For text files, scan for script injection
    if ext == ".txt":
        try:
            text_content = file_data.decode("utf-8", errors="replace")
            for pattern in _MALICIOUS_PATTERNS:
                if pattern.search(text_content):
                    return FileValidationResult(
                        is_valid=False,
                        detected_mime_type="text/plain",
                        error_message="File contains potentially malicious content (script injection detected).",
                    )
        except Exception:
            pass

    # Check for embedded null bytes in text files (common in malicious files)
    if ext in (".txt", ".doc", ".docx") and b"\x00" in file_data[:1024]:
        warnings.append("File contains null bytes which may indicate binary content in a text file.")

    # Check for suspiciously large files
    if len(file_data) > MAX_DOCUMENT_SIZE_BYTES:
        return FileValidationResult(
            is_valid=False,
            detected_mime_type=None,
            error_message=f"File size ({len(file_data) / 1024 / 1024:.1f} MB) exceeds the maximum "
            f"allowed size ({MAX_DOCUMENT_SIZE_BYTES / 1024 / 1024:.0f} MB).",
        )

    return FileValidationResult(
        is_valid=True,
        detected_mime_type=ALLOWED_EXTENSIONS.get(ext),
        warnings=warnings,
    )


def validate_and_scan_file(
    file_data: bytes,
    filename: str,
    allowed_types: set[str] | None = None,
) -> FileValidationResult:
    """
    Run both file type validation and malicious content scanning.

    Requirement 18.2: validate file types AND scan for malicious content.
    """
    # First validate type
    type_result = validate_file_type(file_data, filename, allowed_types)
    if not type_result.is_valid:
        return type_result

    # Then scan for malicious content
    scan_result = scan_for_malicious_content(file_data, filename)
    if not scan_result.is_valid:
        return scan_result

    # Merge warnings
    all_warnings = type_result.warnings + scan_result.warnings
    return FileValidationResult(
        is_valid=True,
        detected_mime_type=type_result.detected_mime_type,
        warnings=all_warnings,
    )


# ---------------------------------------------------------------------------
# Input validation models (Requirement 18.1)
# ---------------------------------------------------------------------------


class ValidatedSearchQuery(BaseModel):
    """
    Validated and sanitized search query.

    Requirement 18.1: input validation for search queries.
    """

    query: str = Field(min_length=1, max_length=500, description="Search query text")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        sanitized = sanitize_search_query(v)
        if not sanitized:
            raise ValueError("Query cannot be empty after sanitization")
        if detect_sql_injection(sanitized):
            raise ValueError("Query contains invalid characters")
        return sanitized


class ValidatedFolderName(BaseModel):
    """
    Validated folder name.

    Requirement 18.1: input validation for folder names.
    """

    name: str = Field(min_length=1, max_length=100, description="Folder name")

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Folder name cannot be empty")
        if detect_path_traversal(v):
            raise ValueError("Folder name contains invalid path characters")
        # Only allow alphanumeric, spaces, hyphens, underscores, and parentheses
        if re.search(r"[^\w\s\-_()\[\]àèéìòùÀÈÉÌÒÙ]", v, re.UNICODE):
            raise ValueError("Folder name contains invalid characters")
        return v


def validate_device_id(device_id: str) -> str:
    """
    Validate and sanitize a device ID path parameter.

    Requirement 18.1.
    """
    device_id = device_id.strip()
    if not device_id:
        raise ValueError("Device ID cannot be empty")
    if detect_path_traversal(device_id):
        raise ValueError("Device ID contains invalid characters")
    # Allow alphanumeric, hyphens, underscores
    if not re.match(r"^[\w\-]+$", device_id):
        raise ValueError("Device ID contains invalid characters")
    return device_id


def validate_file_id(file_id: str) -> str:
    """
    Validate and sanitize a file ID path parameter.

    Requirement 18.1.
    """
    file_id = file_id.strip()
    if not file_id:
        raise ValueError("File ID cannot be empty")
    if detect_path_traversal(file_id):
        raise ValueError("File ID contains invalid characters")
    if not re.match(r"^[\w\-]+$", file_id):
        raise ValueError("File ID contains invalid characters")
    return file_id


def validate_pdf_filename(filename: str) -> str:
    """
    Validate a PDF filename used in path parameters.

    Requirement 18.1.
    """
    filename = filename.strip()
    if not filename:
        raise ValueError("Filename cannot be empty")
    if detect_path_traversal(filename):
        raise ValueError("Filename contains path traversal sequences")
    sanitized = sanitize_filename(filename)
    if not sanitized:
        raise ValueError("Filename is invalid after sanitization")
    return sanitized
