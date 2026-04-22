"""
Comprehensive error handling utilities for the intelligent device documentation platform.

Implements Requirements 17.1-17.5:
- 17.1: Specific error messages with suggested solutions for device recognition failures
- 17.2: Graceful degradation when external services are unavailable
- 17.3: Detailed error information and retry options for upload failures
- 17.4: Loading indicators support (backend side: timing metadata)
- 17.5: Error logging for debugging while providing user-friendly messages
"""

import logging
import time
import traceback
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error categories
# ---------------------------------------------------------------------------


class ErrorCategory(str, Enum):
    """High-level error categories for structured error responses."""

    DEVICE_RECOGNITION = "device_recognition"
    QR_CODE = "qr_code"
    UPLOAD = "upload"
    CONTENT_RETRIEVAL = "content_retrieval"
    SEARCH = "search"
    EXTERNAL_SERVICE = "external_service"
    VALIDATION = "validation"
    INTERNAL = "internal"


class ErrorCode(str, Enum):
    """Specific error codes for machine-readable error identification."""

    # Device recognition errors (Req 17.1)
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    IMAGE_FORMAT_UNSUPPORTED = "IMAGE_FORMAT_UNSUPPORTED"
    IMAGE_EMPTY = "IMAGE_EMPTY"
    RECOGNITION_LOW_CONFIDENCE = "RECOGNITION_LOW_CONFIDENCE"
    RECOGNITION_FAILED = "RECOGNITION_FAILED"
    QR_NOT_DETECTED = "QR_NOT_DETECTED"
    QR_INVALID_FORMAT = "QR_INVALID_FORMAT"

    # Upload errors (Req 17.3)
    UPLOAD_FILE_TOO_LARGE = "UPLOAD_FILE_TOO_LARGE"
    UPLOAD_FORMAT_UNSUPPORTED = "UPLOAD_FORMAT_UNSUPPORTED"
    UPLOAD_EXTRACTION_FAILED = "UPLOAD_EXTRACTION_FAILED"
    UPLOAD_INDEXING_FAILED = "UPLOAD_INDEXING_FAILED"
    UPLOAD_NETWORK_ERROR = "UPLOAD_NETWORK_ERROR"
    UPLOAD_NO_TEXT = "UPLOAD_NO_TEXT"

    # External service errors (Req 17.2)
    QDRANT_UNAVAILABLE = "QDRANT_UNAVAILABLE"
    EXTERNAL_API_UNAVAILABLE = "EXTERNAL_API_UNAVAILABLE"
    EMBEDDING_SERVICE_UNAVAILABLE = "EMBEDDING_SERVICE_UNAVAILABLE"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"

    # Search errors
    COLLECTION_NOT_FOUND = "COLLECTION_NOT_FOUND"
    SEARCH_FAILED = "SEARCH_FAILED"
    INVALID_QUERY = "INVALID_QUERY"

    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Error response models
# ---------------------------------------------------------------------------


class ErrorSuggestion(BaseModel):
    """A single actionable suggestion for resolving an error."""

    action: str
    description: str
    can_retry: bool = False


class StructuredErrorResponse(BaseModel):
    """
    Structured error response with user-friendly message and debugging info.

    Implements Requirement 17.5: user-friendly messages + debug logging.
    """

    error_code: str
    category: str
    user_message: str
    suggestions: List[ErrorSuggestion] = []
    can_retry: bool = False
    retry_after_seconds: Optional[int] = None
    debug_info: Optional[Dict[str, Any]] = None  # Only included in debug mode


class UploadErrorResponse(BaseModel):
    """
    Detailed upload error response with retry options.

    Implements Requirement 17.3.
    """

    filename: str
    error_code: str
    user_message: str
    details: str
    retry_options: List[str] = []
    can_retry: bool = False
    suggestions: List[ErrorSuggestion] = []


class ServiceDegradationInfo(BaseModel):
    """
    Information about service degradation and available fallbacks.

    Implements Requirement 17.2.
    """

    service_name: str
    is_available: bool
    fallback_available: bool
    fallback_description: Optional[str] = None
    user_message: str


# ---------------------------------------------------------------------------
# Error factory functions
# ---------------------------------------------------------------------------


def make_device_recognition_error(
    error_code: ErrorCode,
    detail: str = "",
    debug_info: Optional[Dict[str, Any]] = None,
) -> StructuredErrorResponse:
    """
    Build a structured error response for device recognition failures.

    Implements Requirement 17.1: specific messages with suggested solutions.
    """
    suggestions_map: Dict[ErrorCode, List[ErrorSuggestion]] = {
        ErrorCode.IMAGE_TOO_LARGE: [
            ErrorSuggestion(
                action="Comprimi l'immagine",
                description="Riduci la dimensione del file a meno di 10 MB prima di caricarla.",
                can_retry=True,
            ),
            ErrorSuggestion(
                action="Usa un formato più compresso",
                description="Converti l'immagine in JPEG con qualità ridotta.",
                can_retry=True,
            ),
        ],
        ErrorCode.IMAGE_FORMAT_UNSUPPORTED: [
            ErrorSuggestion(
                action="Converti il formato",
                description="Usa JPEG, PNG o WebP per le immagini del dispositivo.",
                can_retry=True,
            ),
        ],
        ErrorCode.IMAGE_EMPTY: [
            ErrorSuggestion(
                action="Ricarica l'immagine",
                description="Il file sembra vuoto. Seleziona un'immagine valida.",
                can_retry=True,
            ),
        ],
        ErrorCode.RECOGNITION_LOW_CONFIDENCE: [
            ErrorSuggestion(
                action="Migliora la foto",
                description="Scatta una foto con migliore illuminazione e il dispositivo ben visibile.",
                can_retry=True,
            ),
            ErrorSuggestion(
                action="Usa la selezione manuale",
                description="Inserisci manualmente il nome del dispositivo per trovare la documentazione.",
                can_retry=False,
            ),
            ErrorSuggestion(
                action="Scansiona il QR",
                description="Se il dispositivo ha un codice QR, usa la modalità di scansione QR.",
                can_retry=False,
            ),
        ],
        ErrorCode.RECOGNITION_FAILED: [
            ErrorSuggestion(
                action="Riprova",
                description="Il servizio di riconoscimento ha riscontrato un errore temporaneo.",
                can_retry=True,
            ),
            ErrorSuggestion(
                action="Usa la selezione manuale",
                description="Inserisci manualmente il nome del dispositivo.",
                can_retry=False,
            ),
        ],
        ErrorCode.QR_NOT_DETECTED: [
            ErrorSuggestion(
                action="Migliora l'inquadratura",
                description="Assicurati che il codice QR sia ben visibile e non rifletta la luce.",
                can_retry=True,
            ),
            ErrorSuggestion(
                action="Carica un'immagine",
                description="Carica direttamente un'immagine del codice QR.",
                can_retry=True,
            ),
        ],
        ErrorCode.QR_INVALID_FORMAT: [
            ErrorSuggestion(
                action="Verifica il codice QR",
                description="Il codice QR non contiene informazioni sul dispositivo riconoscibili.",
                can_retry=False,
            ),
            ErrorSuggestion(
                action="Usa la ricerca manuale",
                description="Cerca il dispositivo manualmente usando il nome o il modello.",
                can_retry=False,
            ),
        ],
    }

    user_messages: Dict[ErrorCode, str] = {
        ErrorCode.IMAGE_TOO_LARGE: "L'immagine supera il limite di 10 MB.",
        ErrorCode.IMAGE_FORMAT_UNSUPPORTED: "Formato immagine non supportato. Usa JPEG, PNG o WebP.",
        ErrorCode.IMAGE_EMPTY: "L'immagine è vuota o non valida.",
        ErrorCode.RECOGNITION_LOW_CONFIDENCE: "Il dispositivo non è stato riconosciuto con sufficiente certezza.",
        ErrorCode.RECOGNITION_FAILED: "Errore durante il riconoscimento del dispositivo.",
        ErrorCode.QR_NOT_DETECTED: "Nessun codice QR rilevato nell'immagine.",
        ErrorCode.QR_INVALID_FORMAT: "Il codice QR non contiene informazioni sul dispositivo.",
    }

    user_msg = user_messages.get(error_code, "Errore durante il riconoscimento del dispositivo.")
    if detail:
        logger.error(
            "Device recognition error [%s]: %s",
            error_code.value,
            detail,
            extra={"debug_info": debug_info},
        )

    return StructuredErrorResponse(
        error_code=error_code.value,
        category=ErrorCategory.DEVICE_RECOGNITION.value,
        user_message=user_msg,
        suggestions=suggestions_map.get(error_code, []),
        can_retry=error_code
        in (
            ErrorCode.RECOGNITION_FAILED,
            ErrorCode.RECOGNITION_LOW_CONFIDENCE,
            ErrorCode.QR_NOT_DETECTED,
            ErrorCode.IMAGE_TOO_LARGE,
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            ErrorCode.IMAGE_EMPTY,
        ),
        debug_info=debug_info,
    )


def make_upload_error(
    filename: str,
    error_code: ErrorCode,
    detail: str = "",
) -> UploadErrorResponse:
    """
    Build a detailed upload error response with retry options.

    Implements Requirement 17.3.
    """
    retry_options_map: Dict[ErrorCode, List[str]] = {
        ErrorCode.UPLOAD_FILE_TOO_LARGE: [
            "Comprimi il file prima di caricarlo",
            "Dividi il documento in parti più piccole",
        ],
        ErrorCode.UPLOAD_FORMAT_UNSUPPORTED: [
            "Converti il file in PDF, DOC, DOCX o TXT",
            "Usa un convertitore online per cambiare il formato",
        ],
        ErrorCode.UPLOAD_EXTRACTION_FAILED: [
            "Verifica che il PDF non sia protetto da password",
            "Prova a riesportare il documento dall'applicazione originale",
        ],
        ErrorCode.UPLOAD_NO_TEXT: [
            "Il PDF potrebbe contenere solo immagini scansionate",
            "Usa un software OCR per estrarre il testo prima del caricamento",
        ],
        ErrorCode.UPLOAD_INDEXING_FAILED: [
            "Riprova il caricamento tra qualche secondo",
            "Verifica che il servizio backend sia in esecuzione",
        ],
        ErrorCode.UPLOAD_NETWORK_ERROR: [
            "Controlla la connessione di rete",
            "Riprova il caricamento",
        ],
    }

    user_messages: Dict[ErrorCode, str] = {
        ErrorCode.UPLOAD_FILE_TOO_LARGE: f"Il file '{filename}' supera la dimensione massima consentita.",
        ErrorCode.UPLOAD_FORMAT_UNSUPPORTED: f"Il formato del file '{filename}' non è supportato.",
        ErrorCode.UPLOAD_EXTRACTION_FAILED: f"Impossibile estrarre il testo da '{filename}'.",
        ErrorCode.UPLOAD_NO_TEXT: f"Il file '{filename}' non contiene testo estraibile.",
        ErrorCode.UPLOAD_INDEXING_FAILED: f"Errore durante l'indicizzazione di '{filename}'.",
        ErrorCode.UPLOAD_NETWORK_ERROR: f"Errore di rete durante il caricamento di '{filename}'.",
    }

    user_msg = user_messages.get(
        error_code, f"Errore durante il caricamento di '{filename}'."
    )
    retry_opts = retry_options_map.get(error_code, ["Riprova il caricamento"])
    can_retry = error_code in (
        ErrorCode.UPLOAD_INDEXING_FAILED,
        ErrorCode.UPLOAD_NETWORK_ERROR,
    )

    logger.error(
        "Upload error [%s] for file '%s': %s",
        error_code.value,
        filename,
        detail,
    )

    return UploadErrorResponse(
        filename=filename,
        error_code=error_code.value,
        user_message=user_msg,
        details=detail,
        retry_options=retry_opts,
        can_retry=can_retry,
        suggestions=[
            ErrorSuggestion(action=opt, description=opt, can_retry=can_retry)
            for opt in retry_opts
        ],
    )


def make_service_degradation_response(
    service_name: str,
    error: Exception,
    fallback_description: Optional[str] = None,
) -> ServiceDegradationInfo:
    """
    Build a service degradation info object for graceful degradation.

    Implements Requirement 17.2.
    """
    logger.warning(
        "Service '%s' is unavailable: %s. Fallback: %s",
        service_name,
        str(error),
        fallback_description or "none",
    )

    return ServiceDegradationInfo(
        service_name=service_name,
        is_available=False,
        fallback_available=fallback_description is not None,
        fallback_description=fallback_description,
        user_message=(
            f"Il servizio '{service_name}' non è al momento disponibile. "
            + (
                f"Utilizzo alternativo: {fallback_description}."
                if fallback_description
                else "Alcune funzionalità potrebbero essere limitate."
            )
        ),
    )


# ---------------------------------------------------------------------------
# Logging utilities (Req 17.5)
# ---------------------------------------------------------------------------


def log_error_with_context(
    logger_instance: logging.Logger,
    message: str,
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: int = logging.ERROR,
) -> None:
    """
    Log an error with full context for debugging while keeping user messages clean.

    Implements Requirement 17.5: log errors for debugging.
    """
    extra = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
    }
    if context:
        extra.update(context)

    logger_instance.log(level, "%s | %s: %s", message, type(error).__name__, str(error))
    logger_instance.debug("Full traceback:\n%s", traceback.format_exc())


def log_operation_timing(
    logger_instance: logging.Logger,
    operation_name: str,
    start_time: float,
    success: bool = True,
    extra_info: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Log operation timing for performance monitoring.

    Returns elapsed milliseconds.
    Supports Requirement 17.4: tracking operations that exceed 1 second.
    """
    elapsed_ms = (time.monotonic() - start_time) * 1000
    level = logging.WARNING if elapsed_ms > 1000 else logging.DEBUG
    status = "completed" if success else "failed"

    logger_instance.log(
        level,
        "Operation '%s' %s in %.1f ms%s",
        operation_name,
        status,
        elapsed_ms,
        " [SLOW - exceeded 1s threshold]" if elapsed_ms > 1000 else "",
    )
    if extra_info:
        logger_instance.debug("Operation details: %s", extra_info)

    return elapsed_ms


# ---------------------------------------------------------------------------
# Circuit breaker for external services (Req 17.2)
# ---------------------------------------------------------------------------


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls.

    Implements graceful degradation (Requirement 17.2) by preventing
    repeated calls to failing services and providing fallback behavior.
    """

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitBreakerState.CLOSED

    def is_available(self) -> bool:
        """Check if the service is available (circuit not open)."""
        if self.state == CircuitBreakerState.OPEN:
            if (
                self.last_failure_time is not None
                and time.monotonic() - self.last_failure_time > self.timeout_seconds
            ):
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info(
                    "Circuit breaker for '%s' entering HALF_OPEN state",
                    self.service_name,
                )
                return True
            return False
        return True

    def record_success(self) -> None:
        """Record a successful call, resetting the circuit breaker."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            logger.info(
                "Circuit breaker for '%s' CLOSED after successful call",
                self.service_name,
            )
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self, error: Exception) -> None:
        """Record a failed call, potentially opening the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitBreakerState.OPEN:
                logger.warning(
                    "Circuit breaker for '%s' OPENED after %d failures. Last error: %s",
                    self.service_name,
                    self.failure_count,
                    str(error),
                )
            self.state = CircuitBreakerState.OPEN

    def get_status(self) -> Dict[str, Any]:
        """Return current circuit breaker status."""
        return {
            "service": self.service_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "is_available": self.is_available(),
        }


# ---------------------------------------------------------------------------
# Retry utilities (Req 17.3)
# ---------------------------------------------------------------------------


class RetryConfig(BaseModel):
    """Configuration for automatic retry mechanisms."""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0


def calculate_retry_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate exponential backoff delay for retry attempts.

    Returns delay in seconds.
    """
    delay = config.base_delay_seconds * (config.exponential_base ** attempt)
    return min(delay, config.max_delay_seconds)


# ---------------------------------------------------------------------------
# Health check utilities (Req 17.2)
# ---------------------------------------------------------------------------


def check_qdrant_health(client: Any) -> ServiceDegradationInfo:
    """
    Check Qdrant availability and return degradation info if unavailable.

    Implements Requirement 17.2: graceful degradation for external services.
    """
    try:
        client.get_collections()
        return ServiceDegradationInfo(
            service_name="Qdrant",
            is_available=True,
            fallback_available=False,
            user_message="Il servizio di ricerca è operativo.",
        )
    except Exception as e:
        logger.error("Qdrant health check failed: %s", str(e))
        return ServiceDegradationInfo(
            service_name="Qdrant",
            is_available=False,
            fallback_available=False,
            fallback_description=None,
            user_message=(
                "Il servizio di ricerca vettoriale non è disponibile. "
                "Alcune funzionalità di ricerca potrebbero essere limitate."
            ),
        )


def check_embedding_service_health() -> ServiceDegradationInfo:
    """
    Check embedding service availability.

    Implements Requirement 17.2.
    """
    try:
        from .embeddings import embed_text_batch

        test_vector = embed_text_batch(["test"])
        if test_vector and len(test_vector) > 0:
            return ServiceDegradationInfo(
                service_name="EmbeddingService",
                is_available=True,
                fallback_available=False,
                user_message="Il servizio di embedding è operativo.",
            )
        raise ValueError("Empty embedding result")
    except Exception as e:
        logger.error("Embedding service health check failed: %s", str(e))
        return ServiceDegradationInfo(
            service_name="EmbeddingService",
            is_available=False,
            fallback_available=True,
            fallback_description="Ricerca per parole chiave",
            user_message=(
                "Il servizio di embedding non è disponibile. "
                "La ricerca semantica è temporaneamente disabilitata."
            ),
        )
