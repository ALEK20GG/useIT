"""
Content list caching for folder content counts and file listings.

Implements Requirement 14.2 (lazy loading support) and Requirement 14.4
(caching strategies for frequently accessed content).
"""

import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TTL_SECONDS = 120       # 2 minutes
DEFAULT_MAX_ENTRIES = 200


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------


class _ContentCacheEntry:
    """A single cached content value with an expiry timestamp."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


# ---------------------------------------------------------------------------
# ContentCache
# ---------------------------------------------------------------------------


class ContentCache:
    """
    In-memory LRU cache for folder content counts and file listings.

    Entries expire after *ttl* seconds (default 2 minutes).  The cache is
    invalidated on file upload or delete operations so that stale counts are
    never served.

    Typical usage::

        cache = ContentCache()

        # Cache a folder's file listing
        cache.set_file_list("folder-123", records)

        # Retrieve it
        hit, records = cache.get_file_list("folder-123")

        # Invalidate after an upload/delete
        cache.invalidate_folder("folder-123")
    """

    def __init__(
        self,
        ttl: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        self._store: OrderedDict[str, _ContentCacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, key: str) -> Tuple[bool, Any]:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return False, None
        if entry.is_expired():
            del self._store[key]
            self._misses += 1
            return False, None
        self._store.move_to_end(key)
        self._hits += 1
        return True, entry.value

    def _set(self, key: str, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = _ContentCacheEntry(value, self._ttl)
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    # ------------------------------------------------------------------
    # File listing cache
    # ------------------------------------------------------------------

    @staticmethod
    def _file_list_key(folder_id: Optional[str]) -> str:
        return f"file_list:{folder_id or '__all__'}"

    def get_file_list(self, folder_id: Optional[str] = None) -> Tuple[bool, Any]:
        """Return ``(hit, records)`` for the given folder's file listing."""
        return self._get(self._file_list_key(folder_id))

    def set_file_list(self, folder_id: Optional[str], records: Any) -> None:
        """Cache the file listing for *folder_id*."""
        self._set(self._file_list_key(folder_id), records)

    # ------------------------------------------------------------------
    # Folder content count cache
    # ------------------------------------------------------------------

    @staticmethod
    def _count_key(folder_id: str) -> str:
        return f"count:{folder_id}"

    def get_content_count(self, folder_id: str) -> Tuple[bool, Optional[int]]:
        """Return ``(hit, count)`` for the given folder."""
        return self._get(self._count_key(folder_id))

    def set_content_count(self, folder_id: str, count: int) -> None:
        """Cache the content count for *folder_id*."""
        self._set(self._count_key(folder_id), count)

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def invalidate_folder(self, folder_id: str) -> None:
        """
        Invalidate all cached data for *folder_id*.

        Should be called after any upload or delete operation that affects
        the folder's contents.
        """
        keys_to_remove = [
            self._file_list_key(folder_id),
            self._file_list_key(None),   # also invalidate the "all files" listing
            self._count_key(folder_id),
        ]
        for key in keys_to_remove:
            self._store.pop(key, None)
        logger.debug("Content cache invalidated for folder '%s'", folder_id)

    def invalidate_all(self) -> None:
        """Clear the entire content cache."""
        self._store.clear()
        logger.debug("Content cache fully cleared")

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "size": self.size,
            "max_entries": self._max_entries,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_content_cache: Optional[ContentCache] = None


def get_content_cache() -> ContentCache:
    """Return (or create) the module-level ContentCache singleton."""
    global _content_cache
    if _content_cache is None:
        _content_cache = ContentCache()
    return _content_cache
