"""
Multi-source content retrieval service.

Implements Requirements 3.1-3.5, 13.1-13.5:
- 3.1: Search internal Device_Database for existing documentation
- 3.2: Query external internet sources for device specs/manuals
- 3.3: Retrieve YouTube videos related to the device
- 3.4: Aggregate retrieved content in a unified interface
- 3.5: Cache external content locally to improve performance
- 13.1: Support configuration of external content sources
- 13.2: Validate connectivity and access permissions
- 13.3: Rate limiting and caching to respect external service limits
- 13.4: Source priority configuration
- 13.5: Log retrieval activities and provide source reliability metrics
"""

import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ContentSource(str, Enum):
    """Supported content source types."""

    INTERNAL_DATABASE = "internal_database"
    WEB_SEARCH = "web_search"
    YOUTUBE = "youtube"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ContentItem:
    """A single piece of retrieved content from any source."""

    source: ContentSource
    title: str
    content: str
    url: Optional[str] = None
    relevance_score: float = 0.0
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.value,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "relevance_score": self.relevance_score,
            "retrieved_at": self.retrieved_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ContentCollection:
    """Aggregated content from multiple sources for a device."""

    device_info: Dict[str, Any]
    items: List[ContentItem] = field(default_factory=list)
    sources_queried: List[ContentSource] = field(default_factory=list)
    total_count: int = 0
    retrieval_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_info": self.device_info,
            "items": [item.to_dict() for item in self.items],
            "sources_queried": [s.value for s in self.sources_queried],
            "total_count": self.total_count,
            "retrieval_time_ms": self.retrieval_time_ms,
        }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class ContentCache:
    """
    Simple in-memory cache with TTL expiry.

    Cache key is a hash of the device_info dict.  Entries expire after
    ``ttl_seconds`` (default 3600 s = 1 hour).
    """

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}  # key -> {items, expires_at}
        self._hits: int = 0
        self._misses: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def make_key(device_info: Dict[str, Any]) -> str:
        """Deterministic cache key from device_info dict."""
        serialised = json.dumps(device_info, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialised.encode()).hexdigest()

    def get(self, key: str) -> Optional[List[ContentItem]]:
        """Return cached items or None if missing / expired."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.monotonic() > entry["expires_at"]:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry["items"]

    def set(self, key: str, items: List[ContentItem], ttl_seconds: int = 3600) -> None:
        """Store items under *key* with the given TTL."""
        self._store[key] = {
            "items": items,
            "expires_at": time.monotonic() + ttl_seconds,
        }

    def invalidate(self, key: str) -> None:
        """Remove a specific cache entry."""
        self._store.pop(key, None)

    def clear(self) -> None:
        """Remove all cache entries."""
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics."""
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": (
                self._hits / (self._hits + self._misses)
                if (self._hits + self._misses) > 0
                else 0.0
            ),
        }


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """
    Simple token-bucket rate limiter per content source.

    Default limits:
    - INTERNAL_DATABASE: 100 requests / minute (effectively unlimited)
    - WEB_SEARCH:        10 requests / minute
    - YOUTUBE:           5 requests / minute
    """

    DEFAULT_LIMITS: Dict[ContentSource, int] = {
        ContentSource.INTERNAL_DATABASE: 100,
        ContentSource.WEB_SEARCH: 10,
        ContentSource.YOUTUBE: 5,
    }
    WINDOW_SECONDS: int = 60

    def __init__(
        self,
        limits: Optional[Dict[ContentSource, int]] = None,
        window_seconds: int = WINDOW_SECONDS,
    ) -> None:
        self._limits = limits or dict(self.DEFAULT_LIMITS)
        self._window = window_seconds
        # source -> list of request timestamps (monotonic)
        self._timestamps: Dict[ContentSource, List[float]] = defaultdict(list)

    def is_allowed(self, source: ContentSource) -> bool:
        """Return True if a request to *source* is within the rate limit."""
        self._evict_old(source)
        limit = self._limits.get(source, 10)
        return len(self._timestamps[source]) < limit

    def record_request(self, source: ContentSource) -> None:
        """Record that a request to *source* was made right now."""
        self._timestamps[source].append(time.monotonic())

    def _evict_old(self, source: ContentSource) -> None:
        """Remove timestamps older than the window."""
        cutoff = time.monotonic() - self._window
        self._timestamps[source] = [
            ts for ts in self._timestamps[source] if ts > cutoff
        ]

    def get_remaining(self, source: ContentSource) -> int:
        """Return how many more requests are allowed in the current window."""
        self._evict_old(source)
        limit = self._limits.get(source, 10)
        return max(0, limit - len(self._timestamps[source]))

    def status(self) -> Dict[str, Any]:
        """Return rate-limit status for all sources."""
        return {
            source.value: {
                "limit_per_minute": self._limits.get(source, 10),
                "remaining": self.get_remaining(source),
            }
            for source in ContentSource
        }


# ---------------------------------------------------------------------------
# Source metrics tracker
# ---------------------------------------------------------------------------


class SourceMetrics:
    """Tracks reliability and usage metrics per content source."""

    def __init__(self) -> None:
        self._requests: Dict[ContentSource, int] = defaultdict(int)
        self._successes: Dict[ContentSource, int] = defaultdict(int)
        self._failures: Dict[ContentSource, int] = defaultdict(int)
        self._total_items: Dict[ContentSource, int] = defaultdict(int)
        self._total_latency_ms: Dict[ContentSource, float] = defaultdict(float)

    def record_success(
        self,
        source: ContentSource,
        items_returned: int,
        latency_ms: float,
    ) -> None:
        self._requests[source] += 1
        self._successes[source] += 1
        self._total_items[source] += items_returned
        self._total_latency_ms[source] += latency_ms

    def record_failure(self, source: ContentSource) -> None:
        self._requests[source] += 1
        self._failures[source] += 1

    def get_metrics(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for source in ContentSource:
            total = self._requests[source]
            successes = self._successes[source]
            reliability = successes / total if total > 0 else 1.0
            avg_latency = (
                self._total_latency_ms[source] / successes
                if successes > 0
                else 0.0
            )
            result[source.value] = {
                "total_requests": total,
                "successes": successes,
                "failures": self._failures[source],
                "reliability_score": round(reliability, 4),
                "total_items_returned": self._total_items[source],
                "avg_latency_ms": round(avg_latency, 2),
            }
        return result


# ---------------------------------------------------------------------------
# Source configuration
# ---------------------------------------------------------------------------


@dataclass
class SourceConfig:
    """Configuration for a single content source."""

    source: ContentSource
    enabled: bool = True
    priority: int = 0  # lower = higher priority
    timeout_seconds: float = 10.0
    max_results: int = 5
    extra: Dict[str, Any] = field(default_factory=dict)


class SourceConfigManager:
    """
    Manages configuration for all content sources.

    Supports loading from a JSON file (``backend/config/source-config.json``)
    and falls back to sensible defaults.

    Implements Requirement 13.1 (source configuration) and
    13.4 (source priority configuration).
    """

    DEFAULT_PRIORITY: List[ContentSource] = [
        ContentSource.INTERNAL_DATABASE,
        ContentSource.WEB_SEARCH,
        ContentSource.YOUTUBE,
    ]

    def __init__(self, config_path: Optional[str] = None) -> None:
        self._configs: Dict[ContentSource, SourceConfig] = {
            ContentSource.INTERNAL_DATABASE: SourceConfig(
                source=ContentSource.INTERNAL_DATABASE,
                enabled=True,
                priority=0,
                max_results=10,
            ),
            ContentSource.WEB_SEARCH: SourceConfig(
                source=ContentSource.WEB_SEARCH,
                enabled=True,
                priority=1,
                max_results=5,
            ),
            ContentSource.YOUTUBE: SourceConfig(
                source=ContentSource.YOUTUBE,
                enabled=True,
                priority=2,
                max_results=3,
            ),
        }

        if config_path:
            self._load_from_file(config_path)

    def _load_from_file(self, path: str) -> None:
        """Load source configuration from a JSON file."""
        try:
            config_file = Path(path)
            if config_file.exists():
                with open(config_file, encoding="utf-8") as f:
                    data = json.load(f)
                for source_str, cfg in data.items():
                    try:
                        source = ContentSource(source_str)
                        self._configs[source] = SourceConfig(
                            source=source,
                            enabled=cfg.get("enabled", True),
                            priority=cfg.get("priority", 99),
                            timeout_seconds=cfg.get("timeout_seconds", 10.0),
                            max_results=cfg.get("max_results", 5),
                            extra=cfg.get("extra", {}),
                        )
                    except ValueError:
                        logger.warning("Unknown source in config: %s", source_str)
        except Exception as exc:
            logger.warning("Failed to load source config from %s: %s", path, exc)

    def get_config(self, source: ContentSource) -> SourceConfig:
        return self._configs[source]

    def get_ordered_sources(self) -> List[ContentSource]:
        """Return enabled sources ordered by priority (ascending)."""
        enabled = [cfg for cfg in self._configs.values() if cfg.enabled]
        enabled.sort(key=lambda c: c.priority)
        return [cfg.source for cfg in enabled]

    def validate_connectivity(self) -> Dict[str, Any]:
        """
        Validate connectivity for each configured source.

        For mock sources this always returns True.
        Implements Requirement 13.2.
        """
        results: Dict[str, Any] = {}
        for source, cfg in self._configs.items():
            results[source.value] = {
                "enabled": cfg.enabled,
                "reachable": cfg.enabled,  # mock: always reachable when enabled
                "priority": cfg.priority,
            }
        return results


# ---------------------------------------------------------------------------
# Content retrieval service
# ---------------------------------------------------------------------------


class ContentRetrievalService:
    """
    Aggregates device content from multiple sources.

    Implements Requirements 3.1-3.5 and 13.1-13.5.

    External web search and YouTube are implemented as mock services that
    return plausible results based on device name/manufacturer.  In
    production these would call real APIs (e.g. Google Custom Search,
    YouTube Data API v3).
    """

    def __init__(
        self,
        device_database=None,
        cache: Optional[ContentCache] = None,
        rate_limiter: Optional[RateLimiter] = None,
        source_config: Optional[SourceConfigManager] = None,
    ) -> None:
        self._db = device_database  # DeviceDatabase instance (may be None)
        self._cache = cache or ContentCache()
        self._rate_limiter = rate_limiter or RateLimiter()
        self._source_config = source_config or SourceConfigManager()
        self._metrics = SourceMetrics()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def retrieve_device_content(
        self, device_info: Dict[str, Any]
    ) -> ContentCollection:
        """
        Retrieve content for a device from all configured sources.

        Sources are queried in priority order.  Results are aggregated and
        returned as a :class:`ContentCollection`.

        Implements Requirements 3.1-3.4.
        """
        start = time.monotonic()
        cache_key = ContentCache.make_key(device_info)

        # Check cache first (Req 3.5)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info(
                "Cache hit for device: %s",
                device_info.get("name", "unknown"),
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            collection = ContentCollection(
                device_info=device_info,
                items=cached,
                sources_queried=[item.source for item in cached],
                total_count=len(cached),
                retrieval_time_ms=elapsed_ms,
            )
            return collection

        ordered_sources = self._source_config.get_ordered_sources()
        all_items: List[ContentItem] = []
        sources_queried: List[ContentSource] = []

        for source in ordered_sources:
            if not self._rate_limiter.is_allowed(source):
                logger.warning(
                    "Rate limit exceeded for source %s – skipping", source.value
                )
                continue

            self._rate_limiter.record_request(source)
            source_start = time.monotonic()

            try:
                if source == ContentSource.INTERNAL_DATABASE:
                    items = await self.search_internal_database(device_info)
                elif source == ContentSource.WEB_SEARCH:
                    items = await self.fetch_external_content(device_info)
                elif source == ContentSource.YOUTUBE:
                    items = await self.get_video_content(device_info)
                else:
                    items = []

                latency_ms = (time.monotonic() - source_start) * 1000
                self._metrics.record_success(source, len(items), latency_ms)
                all_items.extend(items)
                sources_queried.append(source)

                logger.info(
                    "Source %s returned %d items in %.1f ms",
                    source.value,
                    len(items),
                    latency_ms,
                )

            except Exception as exc:
                self._metrics.record_failure(source)
                logger.error(
                    "Error retrieving content from %s: %s", source.value, exc
                )

        # Sort by relevance score descending
        all_items.sort(key=lambda x: x.relevance_score, reverse=True)

        # Cache the result (Req 3.5, 13.3)
        self._cache.set(cache_key, all_items, ttl_seconds=3600)

        elapsed_ms = (time.monotonic() - start) * 1000
        collection = ContentCollection(
            device_info=device_info,
            items=all_items,
            sources_queried=sources_queried,
            total_count=len(all_items),
            retrieval_time_ms=elapsed_ms,
        )

        logger.info(
            "Retrieved %d total items for device '%s' in %.1f ms",
            len(all_items),
            device_info.get("name", "unknown"),
            elapsed_ms,
        )
        return collection

    async def search_internal_database(
        self, device_info: Dict[str, Any]
    ) -> List[ContentItem]:
        """
        Search the internal Device_Database for existing documentation.

        Implements Requirement 3.1.
        """
        items: List[ContentItem] = []

        if self._db is None:
            logger.debug("No device database configured – skipping internal search")
            return items

        # Build search queries from individual device_info fields.
        # We search each field separately and deduplicate by record ID so that
        # the substring matching in DeviceDatabase.search() works correctly.
        query_parts = [
            device_info.get("name", ""),
            device_info.get("manufacturer", ""),
            device_info.get("model", ""),
        ]
        queries = [p.strip() for p in query_parts if p and p.strip()]

        if not queries:
            return items

        try:
            seen_ids: set = set()
            records = []
            for query in queries:
                for record in self._db.search(query):
                    if record.id not in seen_ids:
                        seen_ids.add(record.id)
                        records.append(record)
            for record in records:
                # Score based on how many fields match
                score = self._compute_db_relevance(record, device_info)

                # Add a content item for the device record itself
                content_text = self._format_device_record(record)
                items.append(
                    ContentItem(
                        source=ContentSource.INTERNAL_DATABASE,
                        title=f"{record.name} – {record.manufacturer} {record.model}",
                        content=content_text,
                        url=record.documentation_urls[0]
                        if record.documentation_urls
                        else None,
                        relevance_score=score,
                        metadata={
                            "device_id": record.id,
                            "category": record.category,
                            "documentation_urls": record.documentation_urls,
                            "qr_codes": record.qr_codes,
                        },
                    )
                )

                # Add individual documentation URL items
                for url in record.documentation_urls[1:]:
                    items.append(
                        ContentItem(
                            source=ContentSource.INTERNAL_DATABASE,
                            title=f"Documentation: {record.name}",
                            content=f"Documentation resource for {record.name}",
                            url=url,
                            relevance_score=score * 0.9,
                            metadata={"device_id": record.id},
                        )
                    )

        except Exception as exc:
            logger.error("Internal database search failed: %s", exc)

        return items

    async def fetch_external_content(
        self, device_info: Dict[str, Any]
    ) -> List[ContentItem]:
        """
        Fetch device specifications and manuals from external web sources.

        This is a **mock implementation** that returns plausible results
        based on device name/manufacturer.  In production this would call
        a real search API (e.g. Google Custom Search API).

        Implements Requirement 3.2.
        """
        name = device_info.get("name", "")
        manufacturer = device_info.get("manufacturer", "")
        model = device_info.get("model", "")

        if not name and not manufacturer and not model:
            return []

        device_label = " ".join(p for p in [manufacturer, name, model] if p)
        cfg = self._source_config.get_config(ContentSource.WEB_SEARCH)
        max_results = cfg.max_results

        # Mock results – deterministic based on device label
        mock_results = self._generate_mock_web_results(device_label, max_results)

        logger.info(
            "Mock web search returned %d results for '%s'",
            len(mock_results),
            device_label,
        )
        return mock_results

    async def get_video_content(
        self, device_info: Dict[str, Any]
    ) -> List[ContentItem]:
        """
        Retrieve YouTube videos related to the device.

        This is a **mock implementation** that returns plausible YouTube
        search results.  In production this would call the YouTube Data
        API v3.

        Implements Requirement 3.3.
        """
        name = device_info.get("name", "")
        manufacturer = device_info.get("manufacturer", "")
        model = device_info.get("model", "")

        if not name and not manufacturer and not model:
            return []

        device_label = " ".join(p for p in [manufacturer, name, model] if p)
        cfg = self._source_config.get_config(ContentSource.YOUTUBE)
        max_results = cfg.max_results

        mock_results = self._generate_mock_youtube_results(device_label, max_results)

        logger.info(
            "Mock YouTube search returned %d results for '%s'",
            len(mock_results),
            device_label,
        )
        return mock_results

    def get_source_metrics(self) -> Dict[str, Any]:
        """
        Return source reliability metrics and usage statistics.

        Implements Requirement 13.5.
        """
        return {
            "source_metrics": self._metrics.get_metrics(),
            "cache_stats": self._cache.stats(),
            "rate_limit_status": self._rate_limiter.status(),
            "source_config": self._source_config.validate_connectivity(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_db_relevance(record: Any, device_info: Dict[str, Any]) -> float:
        """Compute a relevance score [0, 1] for a database record."""
        score = 0.0
        total = 0

        fields = [
            ("name", "name"),
            ("manufacturer", "manufacturer"),
            ("model", "model"),
        ]
        for record_field, info_field in fields:
            record_val = getattr(record, record_field, "").lower()
            info_val = device_info.get(info_field, "").lower()
            if record_val and info_val:
                total += 1
                if record_val == info_val:
                    score += 1.0
                elif info_val in record_val or record_val in info_val:
                    score += 0.7

        return score / total if total > 0 else 0.5

    @staticmethod
    def _format_device_record(record: Any) -> str:
        """Format a DeviceRecord as a human-readable content string."""
        lines = [
            f"Device: {record.name}",
            f"Manufacturer: {record.manufacturer}",
            f"Model: {record.model}",
            f"Category: {record.category}",
        ]
        if record.specifications:
            lines.append("Specifications:")
            for k, v in record.specifications.items():
                lines.append(f"  {k}: {v}")
        if record.documentation_urls:
            lines.append("Documentation:")
            for url in record.documentation_urls:
                lines.append(f"  {url}")
        return "\n".join(lines)

    @staticmethod
    def _generate_mock_web_results(
        device_label: str, max_results: int
    ) -> List[ContentItem]:
        """
        Generate deterministic mock web search results for a device.

        The results are plausible but not real – they simulate what a
        production web search API would return.
        """
        # Use a hash of the label to make results deterministic
        label_hash = hashlib.md5(device_label.encode()).hexdigest()
        seed = int(label_hash[:4], 16)

        templates = [
            {
                "title": "{device} – Official Documentation",
                "content": (
                    "Official documentation and technical specifications for {device}. "
                    "Includes datasheet, pinout diagrams, and getting-started guide."
                ),
                "url_template": "https://docs.example.com/{slug}/overview",
                "score": 0.92,
            },
            {
                "title": "{device} Datasheet (PDF)",
                "content": (
                    "Complete datasheet for {device} with electrical characteristics, "
                    "absolute maximum ratings, and application circuits."
                ),
                "url_template": "https://datasheets.example.com/{slug}.pdf",
                "score": 0.88,
            },
            {
                "title": "Getting Started with {device}",
                "content": (
                    "Step-by-step tutorial for setting up and programming {device}. "
                    "Covers installation, first project, and common troubleshooting."
                ),
                "url_template": "https://tutorials.example.com/{slug}/getting-started",
                "score": 0.80,
            },
            {
                "title": "{device} User Manual",
                "content": (
                    "Comprehensive user manual for {device} covering all features, "
                    "configuration options, and maintenance procedures."
                ),
                "url_template": "https://manuals.example.com/{slug}/user-manual",
                "score": 0.75,
            },
            {
                "title": "{device} Community Forum",
                "content": (
                    "Community discussions, Q&A, and project examples for {device}. "
                    "Find solutions to common problems and share your projects."
                ),
                "url_template": "https://forum.example.com/t/{slug}",
                "score": 0.65,
            },
        ]

        slug = device_label.lower().replace(" ", "-").replace("/", "-")
        results: List[ContentItem] = []

        for i, template in enumerate(templates[:max_results]):
            # Vary score slightly based on seed for realism
            score_variation = ((seed + i) % 10) * 0.005
            score = min(1.0, template["score"] + score_variation)

            results.append(
                ContentItem(
                    source=ContentSource.WEB_SEARCH,
                    title=template["title"].format(device=device_label),
                    content=template["content"].format(device=device_label),
                    url=template["url_template"].format(slug=slug),
                    relevance_score=score,
                    metadata={"is_mock": True, "query": device_label},
                )
            )

        return results

    @staticmethod
    def _generate_mock_youtube_results(
        device_label: str, max_results: int
    ) -> List[ContentItem]:
        """
        Generate deterministic mock YouTube search results for a device.

        Simulates what the YouTube Data API v3 would return.
        """
        label_hash = hashlib.md5(device_label.encode()).hexdigest()
        seed = int(label_hash[:4], 16)

        templates = [
            {
                "title": "{device} – Complete Beginner's Guide",
                "content": (
                    "A comprehensive beginner's guide to {device}. "
                    "Learn how to set up, program, and build your first project."
                ),
                "video_id_offset": 0,
                "score": 0.90,
                "duration": "15:32",
                "channel": "TechTutorials",
            },
            {
                "title": "{device} Tutorial – Getting Started",
                "content": (
                    "Quick start tutorial for {device}. "
                    "Covers unboxing, setup, and a simple hello-world project."
                ),
                "video_id_offset": 1,
                "score": 0.85,
                "duration": "8:47",
                "channel": "MakerSpace",
            },
            {
                "title": "{device} Review and Teardown",
                "content": (
                    "In-depth review and hardware teardown of {device}. "
                    "Examines build quality, components, and performance benchmarks."
                ),
                "video_id_offset": 2,
                "score": 0.72,
                "duration": "22:15",
                "channel": "HardwareReviews",
            },
        ]

        slug = label_hash[:11]  # YouTube-style video ID
        results: List[ContentItem] = []

        for i, template in enumerate(templates[:max_results]):
            score_variation = ((seed + i) % 10) * 0.005
            score = min(1.0, template["score"] + score_variation)
            video_id = f"{slug}{template['video_id_offset']}"

            results.append(
                ContentItem(
                    source=ContentSource.YOUTUBE,
                    title=template["title"].format(device=device_label),
                    content=template["content"].format(device=device_label),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    relevance_score=score,
                    metadata={
                        "is_mock": True,
                        "video_id": video_id,
                        "duration": template["duration"],
                        "channel": template["channel"],
                        "query": device_label,
                    },
                )
            )

        return results


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_content_retrieval_service: Optional[ContentRetrievalService] = None


def get_content_retrieval_service(
    device_database=None,
) -> ContentRetrievalService:
    """Return the module-level ContentRetrievalService singleton."""
    global _content_retrieval_service
    if _content_retrieval_service is None:
        _content_retrieval_service = ContentRetrievalService(
            device_database=device_database
        )
    return _content_retrieval_service
