"""
Search result caching with TTL and LRU eviction.

Implements Requirement 14.4: caching strategies for frequently accessed
content and search results.
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TTL_SECONDS = 300       # 5 minutes
DEFAULT_MAX_ENTRIES = 500


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------


class _CacheEntry:
    """A single cached value with an expiry timestamp."""

    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl

    def is_expired(self) -> bool:
        return time.monotonic() > self.expires_at


# ---------------------------------------------------------------------------
# SearchCache
# ---------------------------------------------------------------------------


class SearchCache:
    """
    In-memory LRU cache for search results with TTL expiry.

    Cache key is derived from (query, folder_filter, search_type, limit, offset).
    Entries expire after *ttl* seconds and the cache holds at most *max_entries*
    items (oldest entries are evicted first when the limit is reached).

    Thread-safety note: this implementation is not thread-safe by design –
    FastAPI runs in a single-threaded async event loop so no locking is needed
    for typical usage.
    """

    def __init__(
        self,
        ttl: float = DEFAULT_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl
        self._max_entries = max_entries
        # OrderedDict gives O(1) move-to-end (LRU update) and O(1) popitem
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    # Key generation
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(
        query: str,
        folder_filter: Optional[List[str]],
        search_type: str,
        limit: int,
        offset: int,
    ) -> str:
        """
        Build a deterministic cache key from search parameters.

        The key is a hex digest of the JSON-serialised parameters so that
        equivalent queries always map to the same key regardless of list
        ordering for *folder_filter*.
        """
        canonical = json.dumps(
            {
                "q": query.strip().lower(),
                "folders": sorted(folder_filter) if folder_filter else [],
                "type": search_type,
                "limit": limit,
                "offset": offset,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Core cache operations
    # ------------------------------------------------------------------

    def get(self, key: str) -> Tuple[bool, Any]:
        """
        Look up *key* in the cache.

        Returns ``(True, value)`` on a cache hit, ``(False, None)`` on a miss
        or if the entry has expired.
        """
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return False, None

        if entry.is_expired():
            # Lazy eviction of expired entry
            del self._store[key]
            self._misses += 1
            return False, None

        # Move to end to mark as recently used
        self._store.move_to_end(key)
        self._hits += 1
        return True, entry.value

    def set(self, key: str, value: Any) -> None:
        """Store *value* under *key* with the configured TTL."""
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = _CacheEntry(value, self._ttl)

        # Evict oldest entries if over capacity
        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        self._store.pop(key, None)

    def invalidate_all(self) -> None:
        """Clear the entire cache (e.g. after new content is indexed)."""
        self._store.clear()
        logger.debug("Search cache cleared")

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        """Current number of entries (including potentially expired ones)."""
        return len(self._store)

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a fraction in [0, 1]."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, Any]:
        """Return a dict of cache statistics."""
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

_search_cache: Optional[SearchCache] = None


def get_search_cache() -> SearchCache:
    """Return (or create) the module-level SearchCache singleton."""
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchCache()
    return _search_cache
