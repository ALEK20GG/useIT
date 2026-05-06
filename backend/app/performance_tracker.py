"""
Performance tracking utilities.

Tracks search response times with a rolling average and exposes aggregate
statistics for the /performance/stats endpoint.
"""

import time
from collections import deque
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Rolling average tracker
# ---------------------------------------------------------------------------

_WINDOW_SIZE = 100   # keep the last N response times


class PerformanceTracker:
    """
    Lightweight tracker for search response times.

    Uses a fixed-size deque so memory usage is bounded regardless of how many
    searches are performed.
    """

    def __init__(self, window_size: int = _WINDOW_SIZE) -> None:
        self._window_size = window_size
        self._times: deque[float] = deque(maxlen=window_size)
        self._total_requests = 0

    def record(self, elapsed_ms: float) -> None:
        """Record a single search response time in milliseconds."""
        self._times.append(elapsed_ms)
        self._total_requests += 1

    @property
    def average_ms(self) -> Optional[float]:
        """Rolling average response time in milliseconds, or None if no data."""
        if not self._times:
            return None
        return sum(self._times) / len(self._times)

    @property
    def total_requests(self) -> int:
        return self._total_requests

    def get_stats(self) -> Dict[str, Any]:
        avg = self.average_ms
        return {
            "total_requests": self._total_requests,
            "average_response_ms": round(avg, 2) if avg is not None else None,
            "window_size": self._window_size,
            "samples_in_window": len(self._times),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """Return (or create) the module-level PerformanceTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker


# ---------------------------------------------------------------------------
# Context manager helper
# ---------------------------------------------------------------------------


class _Timer:
    """Simple context manager that records elapsed time to a tracker."""

    def __init__(self, tracker: PerformanceTracker) -> None:
        self._tracker = tracker
        self._start: float = 0.0

    def __enter__(self) -> "_Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_: Any) -> None:
        elapsed_ms = (time.perf_counter() - self._start) * 1000
        self._tracker.record(elapsed_ms)


def timed_search(tracker: Optional[PerformanceTracker] = None) -> _Timer:
    """
    Return a context manager that records the elapsed time to *tracker*.

    Usage::

        with timed_search():
            results = await service.semantic_search(...)
    """
    if tracker is None:
        tracker = get_performance_tracker()
    return _Timer(tracker)
