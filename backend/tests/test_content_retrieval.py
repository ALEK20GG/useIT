"""
Tests for the multi-source content retrieval service.

Covers Requirements 3.1-3.5, 13.1-13.5:
- 3.1: Internal database search
- 3.2: External web content fetching
- 3.3: YouTube video content retrieval
- 3.4: Content aggregation
- 3.5: Caching
- 13.1: Source configuration
- 13.2: Connectivity validation
- 13.3: Rate limiting and caching
- 13.4: Source priority
- 13.5: Metrics and logging
"""

import sys
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import pytest_asyncio

from app.content_retrieval_service import (
    ContentCache,
    ContentCollection,
    ContentItem,
    ContentRetrievalService,
    ContentSource,
    RateLimiter,
    SourceConfig,
    SourceConfigManager,
    SourceMetrics,
    get_content_retrieval_service,
)
from app.device_database import DeviceDatabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_db(tmp_path: Path) -> DeviceDatabase:
    """Create a DeviceDatabase backed by a temporary file."""
    return DeviceDatabase(storage_path=str(tmp_path / "devices.json"))


def make_service(tmp_path: Path) -> ContentRetrievalService:
    """Create a ContentRetrievalService with a fresh in-memory state."""
    db = make_db(tmp_path)
    return ContentRetrievalService(device_database=db)


# ---------------------------------------------------------------------------
# ContentCache tests
# ---------------------------------------------------------------------------


class TestContentCache:
    """Unit tests for ContentCache."""

    def test_get_returns_none_for_missing_key(self):
        cache = ContentCache()
        assert cache.get("nonexistent") is None

    def test_set_and_get_returns_items(self):
        cache = ContentCache()
        items = [
            ContentItem(
                source=ContentSource.WEB_SEARCH,
                title="Test",
                content="Content",
                relevance_score=0.9,
            )
        ]
        cache.set("key1", items)
        result = cache.get("key1")
        assert result is not None
        assert len(result) == 1
        assert result[0].title == "Test"

    def test_expired_entry_returns_none(self):
        cache = ContentCache()
        items = [
            ContentItem(
                source=ContentSource.WEB_SEARCH,
                title="Expired",
                content="Content",
            )
        ]
        # Set with 0 TTL – immediately expired
        cache.set("key_exp", items, ttl_seconds=0)
        # Sleep briefly to ensure expiry
        time.sleep(0.01)
        assert cache.get("key_exp") is None

    def test_make_key_is_deterministic(self):
        device_info = {"name": "Arduino Uno", "manufacturer": "Arduino"}
        key1 = ContentCache.make_key(device_info)
        key2 = ContentCache.make_key(device_info)
        assert key1 == key2

    def test_make_key_differs_for_different_devices(self):
        key1 = ContentCache.make_key({"name": "Arduino Uno"})
        key2 = ContentCache.make_key({"name": "Raspberry Pi"})
        assert key1 != key2

    def test_stats_tracks_hits_and_misses(self):
        cache = ContentCache()
        items = [ContentItem(source=ContentSource.WEB_SEARCH, title="T", content="C")]
        cache.set("k", items)

        cache.get("k")   # hit
        cache.get("k")   # hit
        cache.get("x")   # miss

        stats = cache.stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_clear_removes_all_entries(self):
        cache = ContentCache()
        cache.set("k1", [])
        cache.set("k2", [])
        cache.clear()
        assert cache.stats()["size"] == 0

    def test_invalidate_removes_specific_entry(self):
        cache = ContentCache()
        cache.set("k1", [])
        cache.set("k2", [])
        cache.invalidate("k1")
        assert cache.get("k1") is None
        assert cache.get("k2") is not None


# ---------------------------------------------------------------------------
# RateLimiter tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Unit tests for RateLimiter."""

    def test_allows_requests_within_limit(self):
        limiter = RateLimiter(limits={ContentSource.WEB_SEARCH: 5})
        for _ in range(5):
            assert limiter.is_allowed(ContentSource.WEB_SEARCH)
            limiter.record_request(ContentSource.WEB_SEARCH)

    def test_blocks_requests_over_limit(self):
        limiter = RateLimiter(limits={ContentSource.WEB_SEARCH: 2})
        limiter.record_request(ContentSource.WEB_SEARCH)
        limiter.record_request(ContentSource.WEB_SEARCH)
        assert not limiter.is_allowed(ContentSource.WEB_SEARCH)

    def test_get_remaining_decreases_with_requests(self):
        limiter = RateLimiter(limits={ContentSource.YOUTUBE: 5})
        assert limiter.get_remaining(ContentSource.YOUTUBE) == 5
        limiter.record_request(ContentSource.YOUTUBE)
        assert limiter.get_remaining(ContentSource.YOUTUBE) == 4

    def test_status_returns_all_sources(self):
        limiter = RateLimiter()
        status = limiter.status()
        assert ContentSource.INTERNAL_DATABASE.value in status
        assert ContentSource.WEB_SEARCH.value in status
        assert ContentSource.YOUTUBE.value in status

    def test_internal_database_has_high_limit(self):
        limiter = RateLimiter()
        # Internal DB should have a high limit (100 by default)
        assert limiter.get_remaining(ContentSource.INTERNAL_DATABASE) >= 50

    def test_youtube_has_lower_limit_than_web(self):
        limiter = RateLimiter()
        yt_limit = limiter._limits[ContentSource.YOUTUBE]
        web_limit = limiter._limits[ContentSource.WEB_SEARCH]
        assert yt_limit <= web_limit


# ---------------------------------------------------------------------------
# SourceConfigManager tests
# ---------------------------------------------------------------------------


class TestSourceConfigManager:
    """Unit tests for SourceConfigManager."""

    def test_default_sources_are_all_enabled(self):
        mgr = SourceConfigManager()
        for source in ContentSource:
            cfg = mgr.get_config(source)
            assert cfg.enabled

    def test_ordered_sources_respects_priority(self):
        mgr = SourceConfigManager()
        ordered = mgr.get_ordered_sources()
        # Internal DB should come first (priority 0)
        assert ordered[0] == ContentSource.INTERNAL_DATABASE

    def test_validate_connectivity_returns_all_sources(self):
        mgr = SourceConfigManager()
        result = mgr.validate_connectivity()
        for source in ContentSource:
            assert source.value in result

    def test_validate_connectivity_enabled_sources_are_reachable(self):
        mgr = SourceConfigManager()
        result = mgr.validate_connectivity()
        for source in ContentSource:
            assert result[source.value]["reachable"] == result[source.value]["enabled"]


# ---------------------------------------------------------------------------
# SourceMetrics tests
# ---------------------------------------------------------------------------


class TestSourceMetrics:
    """Unit tests for SourceMetrics."""

    def test_initial_metrics_are_zero(self):
        metrics = SourceMetrics()
        data = metrics.get_metrics()
        for source in ContentSource:
            assert data[source.value]["total_requests"] == 0
            assert data[source.value]["reliability_score"] == 1.0

    def test_record_success_increments_counters(self):
        metrics = SourceMetrics()
        metrics.record_success(ContentSource.WEB_SEARCH, items_returned=3, latency_ms=50.0)
        data = metrics.get_metrics()
        assert data[ContentSource.WEB_SEARCH.value]["total_requests"] == 1
        assert data[ContentSource.WEB_SEARCH.value]["successes"] == 1
        assert data[ContentSource.WEB_SEARCH.value]["total_items_returned"] == 3

    def test_record_failure_increments_failure_counter(self):
        metrics = SourceMetrics()
        metrics.record_failure(ContentSource.YOUTUBE)
        data = metrics.get_metrics()
        assert data[ContentSource.YOUTUBE.value]["failures"] == 1
        assert data[ContentSource.YOUTUBE.value]["reliability_score"] == 0.0

    def test_reliability_score_with_mixed_results(self):
        metrics = SourceMetrics()
        metrics.record_success(ContentSource.WEB_SEARCH, 2, 30.0)
        metrics.record_success(ContentSource.WEB_SEARCH, 2, 30.0)
        metrics.record_failure(ContentSource.WEB_SEARCH)
        data = metrics.get_metrics()
        # 2 successes out of 3 requests = 0.6667
        assert abs(data[ContentSource.WEB_SEARCH.value]["reliability_score"] - 2 / 3) < 0.01


# ---------------------------------------------------------------------------
# ContentItem tests
# ---------------------------------------------------------------------------


class TestContentItem:
    """Unit tests for ContentItem."""

    def test_to_dict_contains_required_fields(self):
        item = ContentItem(
            source=ContentSource.WEB_SEARCH,
            title="Test Title",
            content="Test content",
            url="https://example.com",
            relevance_score=0.85,
        )
        d = item.to_dict()
        assert d["source"] == "web_search"
        assert d["title"] == "Test Title"
        assert d["content"] == "Test content"
        assert d["url"] == "https://example.com"
        assert d["relevance_score"] == 0.85
        assert "retrieved_at" in d

    def test_default_relevance_score_is_zero(self):
        item = ContentItem(
            source=ContentSource.YOUTUBE,
            title="Video",
            content="Description",
        )
        assert item.relevance_score == 0.0


# ---------------------------------------------------------------------------
# ContentRetrievalService – internal database search (Req 3.1)
# ---------------------------------------------------------------------------


class TestInternalDatabaseSearch:
    """Tests for search_internal_database (Requirement 3.1)."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_db(self):
        service = ContentRetrievalService(device_database=None)
        result = await service.search_internal_database({"name": "Arduino"})
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_device_info(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.search_internal_database({})
        assert result == []

    @pytest.mark.asyncio
    async def test_finds_matching_device(self, tmp_path):
        db = make_db(tmp_path)
        db.create(
            name="Arduino Uno",
            manufacturer="Arduino",
            model="Uno R3",
            documentation_urls=["https://arduino.cc/docs"],
        )
        service = ContentRetrievalService(device_database=db)
        result = await service.search_internal_database(
            {"name": "Arduino Uno", "manufacturer": "Arduino"}
        )
        assert len(result) >= 1
        assert result[0].source == ContentSource.INTERNAL_DATABASE
        assert "Arduino" in result[0].title

    @pytest.mark.asyncio
    async def test_result_contains_documentation_url(self, tmp_path):
        db = make_db(tmp_path)
        db.create(
            name="ESP32",
            manufacturer="Espressif",
            model="ESP32-WROOM",
            documentation_urls=["https://espressif.com/docs"],
        )
        service = ContentRetrievalService(device_database=db)
        result = await service.search_internal_database({"name": "ESP32"})
        assert any(item.url == "https://espressif.com/docs" for item in result)

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="Arduino Uno", manufacturer="Arduino", model="Uno R3")
        service = ContentRetrievalService(device_database=db)
        result = await service.search_internal_database({"name": "zyxwvuts"})
        assert result == []

    @pytest.mark.asyncio
    async def test_relevance_score_is_between_0_and_1(self, tmp_path):
        db = make_db(tmp_path)
        db.create(name="Arduino Uno", manufacturer="Arduino", model="Uno R3")
        service = ContentRetrievalService(device_database=db)
        result = await service.search_internal_database({"name": "Arduino Uno"})
        for item in result:
            assert 0.0 <= item.relevance_score <= 1.0


# ---------------------------------------------------------------------------
# ContentRetrievalService – external web content (Req 3.2)
# ---------------------------------------------------------------------------


class TestExternalWebContent:
    """Tests for fetch_external_content (Requirement 3.2)."""

    @pytest.mark.asyncio
    async def test_returns_items_for_known_device(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.fetch_external_content(
            {"name": "Arduino Uno", "manufacturer": "Arduino"}
        )
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_device_info(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.fetch_external_content({})
        assert result == []

    @pytest.mark.asyncio
    async def test_all_items_have_web_search_source(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.fetch_external_content({"name": "Raspberry Pi"})
        for item in result:
            assert item.source == ContentSource.WEB_SEARCH

    @pytest.mark.asyncio
    async def test_items_have_urls(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.fetch_external_content({"name": "ESP32"})
        for item in result:
            assert item.url is not None
            assert item.url.startswith("https://")

    @pytest.mark.asyncio
    async def test_results_are_deterministic(self, tmp_path):
        service = make_service(tmp_path)
        device_info = {"name": "Arduino Uno", "manufacturer": "Arduino"}
        result1 = await service.fetch_external_content(device_info)
        result2 = await service.fetch_external_content(device_info)
        assert [i.title for i in result1] == [i.title for i in result2]

    @pytest.mark.asyncio
    async def test_relevance_scores_are_valid(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.fetch_external_content({"name": "Arduino Uno"})
        for item in result:
            assert 0.0 <= item.relevance_score <= 1.0


# ---------------------------------------------------------------------------
# ContentRetrievalService – YouTube content (Req 3.3)
# ---------------------------------------------------------------------------


class TestYouTubeContent:
    """Tests for get_video_content (Requirement 3.3)."""

    @pytest.mark.asyncio
    async def test_returns_items_for_known_device(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.get_video_content({"name": "Arduino Uno"})
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_device_info(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.get_video_content({})
        assert result == []

    @pytest.mark.asyncio
    async def test_all_items_have_youtube_source(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.get_video_content({"name": "Raspberry Pi"})
        for item in result:
            assert item.source == ContentSource.YOUTUBE

    @pytest.mark.asyncio
    async def test_items_have_youtube_urls(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.get_video_content({"name": "ESP32"})
        for item in result:
            assert item.url is not None
            assert "youtube.com" in item.url

    @pytest.mark.asyncio
    async def test_metadata_contains_video_id(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.get_video_content({"name": "Arduino Uno"})
        for item in result:
            assert "video_id" in item.metadata

    @pytest.mark.asyncio
    async def test_results_are_deterministic(self, tmp_path):
        service = make_service(tmp_path)
        device_info = {"name": "Arduino Uno"}
        result1 = await service.get_video_content(device_info)
        result2 = await service.get_video_content(device_info)
        assert [i.url for i in result1] == [i.url for i in result2]


# ---------------------------------------------------------------------------
# ContentRetrievalService – aggregation (Req 3.4)
# ---------------------------------------------------------------------------


class TestContentAggregation:
    """Tests for retrieve_device_content aggregation (Requirement 3.4)."""

    @pytest.mark.asyncio
    async def test_returns_content_collection(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.retrieve_device_content({"name": "Arduino Uno"})
        assert isinstance(result, ContentCollection)

    @pytest.mark.asyncio
    async def test_queries_all_sources(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.retrieve_device_content({"name": "Arduino Uno"})
        # All three sources should be queried
        assert ContentSource.INTERNAL_DATABASE in result.sources_queried
        assert ContentSource.WEB_SEARCH in result.sources_queried
        assert ContentSource.YOUTUBE in result.sources_queried

    @pytest.mark.asyncio
    async def test_total_count_matches_items_length(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.retrieve_device_content({"name": "Arduino Uno"})
        assert result.total_count == len(result.items)

    @pytest.mark.asyncio
    async def test_items_sorted_by_relevance_descending(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.retrieve_device_content({"name": "Arduino Uno"})
        scores = [item.relevance_score for item in result.items]
        assert scores == sorted(scores, reverse=True)

    @pytest.mark.asyncio
    async def test_retrieval_time_is_positive(self, tmp_path):
        service = make_service(tmp_path)
        result = await service.retrieve_device_content({"name": "Arduino Uno"})
        assert result.retrieval_time_ms >= 0

    @pytest.mark.asyncio
    async def test_device_info_preserved_in_collection(self, tmp_path):
        service = make_service(tmp_path)
        device_info = {"name": "Arduino Uno", "manufacturer": "Arduino"}
        result = await service.retrieve_device_content(device_info)
        assert result.device_info == device_info

    @pytest.mark.asyncio
    async def test_includes_internal_db_results_when_device_exists(self, tmp_path):
        db = make_db(tmp_path)
        db.create(
            name="Arduino Uno",
            manufacturer="Arduino",
            model="Uno R3",
            documentation_urls=["https://arduino.cc/docs"],
        )
        service = ContentRetrievalService(device_database=db)
        result = await service.retrieve_device_content(
            {"name": "Arduino Uno", "manufacturer": "Arduino"}
        )
        internal_items = [
            i for i in result.items if i.source == ContentSource.INTERNAL_DATABASE
        ]
        assert len(internal_items) >= 1


# ---------------------------------------------------------------------------
# ContentRetrievalService – caching (Req 3.5, 13.3)
# ---------------------------------------------------------------------------


class TestContentCaching:
    """Tests for content caching (Requirements 3.5, 13.3)."""

    @pytest.mark.asyncio
    async def test_second_call_uses_cache(self, tmp_path):
        service = make_service(tmp_path)
        device_info = {"name": "Arduino Uno"}

        result1 = await service.retrieve_device_content(device_info)
        # After first call, cache should have an entry
        cache_key = ContentCache.make_key(device_info)
        assert service._cache.get(cache_key) is not None

        result2 = await service.retrieve_device_content(device_info)
        # Both results should have the same items
        assert len(result1.items) == len(result2.items)

    @pytest.mark.asyncio
    async def test_cache_stats_reflect_hits(self, tmp_path):
        service = make_service(tmp_path)
        device_info = {"name": "Arduino Uno"}

        await service.retrieve_device_content(device_info)  # miss
        await service.retrieve_device_content(device_info)  # hit

        stats = service._cache.stats()
        assert stats["hits"] >= 1

    @pytest.mark.asyncio
    async def test_different_devices_have_separate_cache_entries(self, tmp_path):
        service = make_service(tmp_path)

        await service.retrieve_device_content({"name": "Arduino Uno"})
        await service.retrieve_device_content({"name": "Raspberry Pi"})

        stats = service._cache.stats()
        assert stats["size"] == 2


# ---------------------------------------------------------------------------
# ContentRetrievalService – metrics (Req 13.5)
# ---------------------------------------------------------------------------


class TestSourceMetricsIntegration:
    """Tests for source metrics (Requirement 13.5)."""

    @pytest.mark.asyncio
    async def test_get_source_metrics_returns_all_keys(self, tmp_path):
        service = make_service(tmp_path)
        await service.retrieve_device_content({"name": "Arduino Uno"})
        metrics = service.get_source_metrics()
        assert "source_metrics" in metrics
        assert "cache_stats" in metrics
        assert "rate_limit_status" in metrics
        assert "source_config" in metrics

    @pytest.mark.asyncio
    async def test_metrics_track_requests_per_source(self, tmp_path):
        service = make_service(tmp_path)
        await service.retrieve_device_content({"name": "Arduino Uno"})
        metrics = service.get_source_metrics()
        for source in ContentSource:
            assert source.value in metrics["source_metrics"]

    @pytest.mark.asyncio
    async def test_reliability_score_is_1_after_successful_retrieval(self, tmp_path):
        service = make_service(tmp_path)
        await service.retrieve_device_content({"name": "Arduino Uno"})
        metrics = service.get_source_metrics()
        for source in ContentSource:
            score = metrics["source_metrics"][source.value]["reliability_score"]
            assert score == 1.0


# ---------------------------------------------------------------------------
# ContentRetrievalService – rate limiting (Req 13.3)
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Tests for rate limiting (Requirement 13.3)."""

    @pytest.mark.asyncio
    async def test_rate_limited_source_is_skipped(self, tmp_path):
        # Set YouTube limit to 0 so it's always rate-limited
        limiter = RateLimiter(limits={
            ContentSource.INTERNAL_DATABASE: 100,
            ContentSource.WEB_SEARCH: 100,
            ContentSource.YOUTUBE: 0,
        })
        service = ContentRetrievalService(
            device_database=make_db(tmp_path),
            rate_limiter=limiter,
        )
        result = await service.retrieve_device_content({"name": "Arduino Uno"})
        # YouTube should not appear in sources queried
        assert ContentSource.YOUTUBE not in result.sources_queried

    @pytest.mark.asyncio
    async def test_rate_limit_status_in_metrics(self, tmp_path):
        service = make_service(tmp_path)
        metrics = service.get_source_metrics()
        status = metrics["rate_limit_status"]
        for source in ContentSource:
            assert source.value in status
            assert "limit_per_minute" in status[source.value]
            assert "remaining" in status[source.value]


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    """Create a TestClient with isolated dependencies."""
    from app.main import app
    from app.device_database import DeviceDatabase, get_device_database
    from app.content_retrieval_service import (
        ContentRetrievalService,
        get_content_retrieval_service,
    )

    test_db = DeviceDatabase(storage_path=str(tmp_path / "test_devices.json"))
    test_service = ContentRetrievalService(device_database=test_db)

    app.dependency_overrides[get_device_database] = lambda: test_db
    app.dependency_overrides[get_content_retrieval_service] = lambda: test_service

    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestContentAPIEndpoints:
    """Integration tests for content retrieval API endpoints."""

    def test_retrieve_content_returns_200(self, client):
        response = client.post(
            "/content/retrieve",
            json={"name": "Arduino Uno", "manufacturer": "Arduino"},
        )
        assert response.status_code == 200

    def test_retrieve_content_response_structure(self, client):
        response = client.post(
            "/content/retrieve",
            json={"name": "Arduino Uno"},
        )
        data = response.json()
        assert "items" in data
        assert "sources_queried" in data
        assert "total_count" in data
        assert "retrieval_time_ms" in data
        assert "device_info" in data

    def test_retrieve_content_total_count_matches_items(self, client):
        response = client.post(
            "/content/retrieve",
            json={"name": "Arduino Uno"},
        )
        data = response.json()
        assert data["total_count"] == len(data["items"])

    def test_retrieve_content_items_have_required_fields(self, client):
        response = client.post(
            "/content/retrieve",
            json={"name": "Arduino Uno"},
        )
        data = response.json()
        for item in data["items"]:
            assert "source" in item
            assert "title" in item
            assert "content" in item
            assert "relevance_score" in item

    def test_list_sources_returns_200(self, client):
        response = client.get("/content/sources")
        assert response.status_code == 200

    def test_list_sources_response_structure(self, client):
        response = client.get("/content/sources")
        data = response.json()
        assert "sources" in data
        assert "source_metrics" in data
        assert "cache_stats" in data
        assert "rate_limit_status" in data

    def test_list_sources_contains_all_sources(self, client):
        response = client.get("/content/sources")
        data = response.json()
        sources = data["sources"]
        assert "internal_database" in sources
        assert "web_search" in sources
        assert "youtube" in sources

    def test_cache_stats_returns_200(self, client):
        response = client.get("/content/cache/stats")
        assert response.status_code == 200

    def test_cache_stats_response_structure(self, client):
        response = client.get("/content/cache/stats")
        data = response.json()
        assert "size" in data
        assert "hits" in data
        assert "misses" in data
        assert "hit_rate" in data

    def test_cache_stats_hit_rate_increases_after_repeated_calls(self, client):
        device_info = {"name": "Arduino Uno"}
        # First call – cache miss
        client.post("/content/retrieve", json=device_info)
        # Second call – cache hit
        client.post("/content/retrieve", json=device_info)

        response = client.get("/content/cache/stats")
        data = response.json()
        assert data["hits"] >= 1

    def test_retrieve_content_with_empty_device_info(self, client):
        response = client.post("/content/retrieve", json={})
        assert response.status_code == 200
        data = response.json()
        # Empty device info should return empty or minimal results
        assert "items" in data

    def test_retrieve_content_sources_queried_are_valid(self, client):
        response = client.post(
            "/content/retrieve",
            json={"name": "Arduino Uno"},
        )
        data = response.json()
        valid_sources = {s.value for s in ContentSource}
        for source in data["sources_queried"]:
            assert source in valid_sources

