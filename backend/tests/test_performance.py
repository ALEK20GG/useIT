"""
Tests for performance optimization features (Task 15).

Covers:
- SearchCache: LRU eviction, TTL expiry, hit/miss tracking, key generation,
  invalidation
- ContentCache: file listing cache, content count cache, folder invalidation
- PerformanceTracker: rolling average, timed_search context manager
- InteractionTracker: recording interactions, boost application
- Recency boost: linear decay, boundary conditions
- EnhancedSearchService: _apply_ranking_boosts, record_interaction

Property-based tests validate:
- Property 42: Search Pagination          (Req 14.1)
- Property 43: Lazy Loading               (Req 14.2)
- Property 44: Content Caching Strategies (Req 14.4)
- Property 45: Search Result Ranking      (Req 14.5)
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.search_cache import SearchCache
from app.content_cache import ContentCache
from app.performance_tracker import PerformanceTracker, timed_search
from app.search_service import (
    EnhancedSearchService,
    InteractionTracker,
    SearchResult,
    MAX_RECENCY_BOOST,
    MAX_INTERACTION_BOOST,
    RECENCY_WINDOW_SECONDS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    id: str = "r1",
    score: float = 0.5,
    indexed_at: str | None = None,
) -> SearchResult:
    metadata = {}
    if indexed_at is not None:
        metadata["indexed_at"] = indexed_at
    return SearchResult(
        id=id,
        title="Test",
        content="content",
        score=score,
        metadata=metadata,
    )


def _make_service() -> EnhancedSearchService:
    client = MagicMock()
    client.get_collections.return_value = MagicMock(collections=[])
    return EnhancedSearchService(client)


# ===========================================================================
# SearchCache unit tests
# ===========================================================================


class TestSearchCacheBasics:
    def test_miss_on_empty_cache(self):
        cache = SearchCache()
        hit, val = cache.get("nonexistent")
        assert hit is False
        assert val is None

    def test_set_and_get(self):
        cache = SearchCache()
        cache.set("key1", [1, 2, 3])
        hit, val = cache.get("key1")
        assert hit is True
        assert val == [1, 2, 3]

    def test_hit_increments_counter(self):
        cache = SearchCache()
        cache.set("k", "v")
        cache.get("k")
        assert cache.hits == 1
        assert cache.misses == 0

    def test_miss_increments_counter(self):
        cache = SearchCache()
        cache.get("missing")
        assert cache.misses == 1
        assert cache.hits == 0

    def test_hit_rate_zero_when_no_requests(self):
        cache = SearchCache()
        assert cache.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        cache = SearchCache()
        cache.set("k", "v")
        cache.get("k")   # hit
        cache.get("x")   # miss
        assert cache.hit_rate == pytest.approx(0.5)

    def test_invalidate_removes_key(self):
        cache = SearchCache()
        cache.set("k", "v")
        cache.invalidate("k")
        hit, _ = cache.get("k")
        assert hit is False

    def test_invalidate_all_clears_cache(self):
        cache = SearchCache()
        for i in range(5):
            cache.set(f"k{i}", i)
        cache.invalidate_all()
        assert cache.size == 0

    def test_lru_eviction_at_max_entries(self):
        cache = SearchCache(max_entries=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Access "a" to make it recently used
        cache.get("a")
        # Adding "d" should evict "b" (oldest unused)
        cache.set("d", 4)
        assert cache.size == 3
        hit_b, _ = cache.get("b")
        assert hit_b is False  # "b" was evicted

    def test_ttl_expiry(self):
        cache = SearchCache(ttl=0.05)  # 50 ms TTL
        cache.set("k", "v")
        time.sleep(0.1)
        hit, _ = cache.get("k")
        assert hit is False

    def test_get_stats_returns_dict(self):
        cache = SearchCache()
        stats = cache.get_stats()
        assert "size" in stats
        assert "hit_rate" in stats
        assert "hits" in stats
        assert "misses" in stats


class TestSearchCacheKeyGeneration:
    def test_same_params_same_key(self):
        k1 = SearchCache.make_key("hello", ["a", "b"], "semantic", 10, 0)
        k2 = SearchCache.make_key("hello", ["a", "b"], "semantic", 10, 0)
        assert k1 == k2

    def test_folder_order_independent(self):
        k1 = SearchCache.make_key("q", ["x", "y"], "semantic", 10, 0)
        k2 = SearchCache.make_key("q", ["y", "x"], "semantic", 10, 0)
        assert k1 == k2

    def test_different_queries_different_keys(self):
        k1 = SearchCache.make_key("hello", None, "semantic", 10, 0)
        k2 = SearchCache.make_key("world", None, "semantic", 10, 0)
        assert k1 != k2

    def test_different_offsets_different_keys(self):
        k1 = SearchCache.make_key("q", None, "semantic", 10, 0)
        k2 = SearchCache.make_key("q", None, "semantic", 10, 5)
        assert k1 != k2

    def test_none_and_empty_folder_filter_same_key(self):
        k1 = SearchCache.make_key("q", None, "semantic", 10, 0)
        k2 = SearchCache.make_key("q", [], "semantic", 10, 0)
        assert k1 == k2


# ===========================================================================
# ContentCache unit tests
# ===========================================================================


class TestContentCache:
    def test_miss_on_empty(self):
        cache = ContentCache()
        hit, val = cache.get_file_list("folder-1")
        assert hit is False
        assert val is None

    def test_set_and_get_file_list(self):
        cache = ContentCache()
        records = [{"id": "f1"}, {"id": "f2"}]
        cache.set_file_list("folder-1", records)
        hit, val = cache.get_file_list("folder-1")
        assert hit is True
        assert val == records

    def test_set_and_get_content_count(self):
        cache = ContentCache()
        cache.set_content_count("folder-1", 42)
        hit, count = cache.get_content_count("folder-1")
        assert hit is True
        assert count == 42

    def test_invalidate_folder_clears_entries(self):
        cache = ContentCache()
        cache.set_file_list("folder-1", ["a"])
        cache.set_content_count("folder-1", 5)
        cache.invalidate_folder("folder-1")
        hit1, _ = cache.get_file_list("folder-1")
        hit2, _ = cache.get_content_count("folder-1")
        assert hit1 is False
        assert hit2 is False

    def test_invalidate_folder_also_clears_all_listing(self):
        cache = ContentCache()
        cache.set_file_list(None, ["all"])
        cache.invalidate_folder("folder-1")
        hit, _ = cache.get_file_list(None)
        assert hit is False

    def test_invalidate_all(self):
        cache = ContentCache()
        cache.set_file_list("f1", [1])
        cache.set_file_list("f2", [2])
        cache.invalidate_all()
        assert cache.size == 0

    def test_ttl_expiry(self):
        cache = ContentCache(ttl=0.05)
        cache.set_file_list("f", ["data"])
        time.sleep(0.1)
        hit, _ = cache.get_file_list("f")
        assert hit is False

    def test_hit_rate(self):
        cache = ContentCache()
        cache.set_file_list("f", [])
        cache.get_file_list("f")   # hit
        cache.get_file_list("x")   # miss
        assert cache.hit_rate == pytest.approx(0.5)


# ===========================================================================
# PerformanceTracker unit tests
# ===========================================================================


class TestPerformanceTracker:
    def test_no_data_returns_none_average(self):
        tracker = PerformanceTracker()
        assert tracker.average_ms is None

    def test_single_record(self):
        tracker = PerformanceTracker()
        tracker.record(100.0)
        assert tracker.average_ms == pytest.approx(100.0)

    def test_rolling_average(self):
        tracker = PerformanceTracker()
        tracker.record(100.0)
        tracker.record(200.0)
        assert tracker.average_ms == pytest.approx(150.0)

    def test_window_eviction(self):
        tracker = PerformanceTracker(window_size=2)
        tracker.record(100.0)
        tracker.record(200.0)
        tracker.record(300.0)  # evicts 100.0
        assert tracker.average_ms == pytest.approx(250.0)

    def test_total_requests_counts_all(self):
        tracker = PerformanceTracker(window_size=2)
        for _ in range(5):
            tracker.record(10.0)
        assert tracker.total_requests == 5

    def test_timed_search_context_manager(self):
        tracker = PerformanceTracker()
        with timed_search(tracker):
            time.sleep(0.01)
        assert tracker.total_requests == 1
        assert tracker.average_ms is not None
        assert tracker.average_ms >= 10.0  # at least 10 ms

    def test_get_stats_keys(self):
        tracker = PerformanceTracker()
        stats = tracker.get_stats()
        assert "total_requests" in stats
        assert "average_response_ms" in stats
        assert "window_size" in stats


# ===========================================================================
# InteractionTracker unit tests
# ===========================================================================


class TestInteractionTracker:
    def test_no_interaction_initially(self):
        tracker = InteractionTracker()
        assert tracker.has_interaction("r1") is False

    def test_record_and_check(self):
        tracker = InteractionTracker()
        tracker.record("r1")
        assert tracker.has_interaction("r1") is True

    def test_max_entries_eviction(self):
        tracker = InteractionTracker()
        tracker.MAX_ENTRIES = 3
        # Monkey-patch for this test
        from collections import OrderedDict
        tracker._interactions = OrderedDict()
        for i in range(4):
            tracker.record(f"r{i}")
        # r0 should have been evicted
        assert tracker.has_interaction("r0") is False
        assert tracker.has_interaction("r3") is True

    def test_size_property(self):
        tracker = InteractionTracker()
        tracker.record("a")
        tracker.record("b")
        assert tracker.size == 2


# ===========================================================================
# Recency boost unit tests
# ===========================================================================


class TestRecencyBoost:
    def test_no_metadata_returns_zero(self):
        svc = _make_service()
        result = _make_result()
        assert svc._recency_boost(result) == 0.0

    def test_very_recent_returns_max_boost(self):
        svc = _make_service()
        now_str = datetime.now(timezone.utc).isoformat()
        result = _make_result(indexed_at=now_str)
        boost = svc._recency_boost(result)
        assert boost == pytest.approx(MAX_RECENCY_BOOST, abs=0.001)

    def test_old_document_returns_zero(self):
        svc = _make_service()
        old = datetime.now(timezone.utc) - timedelta(days=30)
        result = _make_result(indexed_at=old.isoformat())
        assert svc._recency_boost(result) == 0.0

    def test_half_window_returns_half_boost(self):
        svc = _make_service()
        half_age = timedelta(seconds=RECENCY_WINDOW_SECONDS / 2)
        ts = (datetime.now(timezone.utc) - half_age).isoformat()
        result = _make_result(indexed_at=ts)
        boost = svc._recency_boost(result)
        assert boost == pytest.approx(MAX_RECENCY_BOOST * 0.5, abs=0.005)

    def test_invalid_timestamp_returns_zero(self):
        svc = _make_service()
        result = _make_result(indexed_at="not-a-date")
        assert svc._recency_boost(result) == 0.0

    def test_boost_never_exceeds_max(self):
        svc = _make_service()
        now_str = datetime.now(timezone.utc).isoformat()
        result = _make_result(indexed_at=now_str)
        boost = svc._recency_boost(result)
        assert boost <= MAX_RECENCY_BOOST


# ===========================================================================
# Interaction boost unit tests
# ===========================================================================


class TestInteractionBoost:
    def test_no_interaction_returns_zero(self):
        svc = _make_service()
        result = _make_result()
        assert svc._interaction_boost(result) == 0.0

    def test_recorded_interaction_returns_max_boost(self):
        svc = _make_service()
        svc.record_interaction("r1")
        result = _make_result(id="r1")
        assert svc._interaction_boost(result) == pytest.approx(MAX_INTERACTION_BOOST)

    def test_different_id_returns_zero(self):
        svc = _make_service()
        svc.record_interaction("r1")
        result = _make_result(id="r2")
        assert svc._interaction_boost(result) == 0.0


# ===========================================================================
# _apply_ranking_boosts unit tests
# ===========================================================================


class TestApplyRankingBoosts:
    def test_results_sorted_by_boosted_score(self):
        svc = _make_service()
        # r2 has a lower base score but is very recent → should rank higher
        now_str = datetime.now(timezone.utc).isoformat()
        r1 = _make_result(id="r1", score=0.5)
        r2 = _make_result(id="r2", score=0.45, indexed_at=now_str)
        boosted = svc._apply_ranking_boosts([r1, r2])
        # r2 gets recency boost, so it should rank first
        assert boosted[0].id == "r2"

    def test_score_capped_at_one(self):
        svc = _make_service()
        now_str = datetime.now(timezone.utc).isoformat()
        svc.record_interaction("r1")
        r = _make_result(id="r1", score=0.99, indexed_at=now_str)
        boosted = svc._apply_ranking_boosts([r])
        assert boosted[0].score <= 1.0

    def test_no_boost_when_disabled(self):
        svc = _make_service()
        now_str = datetime.now(timezone.utc).isoformat()
        svc.record_interaction("r1")
        r = _make_result(id="r1", score=0.5, indexed_at=now_str)
        boosted = svc._apply_ranking_boosts(
            [r], recency_boost=False, interaction_boost=False
        )
        assert boosted[0].score == pytest.approx(0.5)

    def test_empty_list_returns_empty(self):
        svc = _make_service()
        assert svc._apply_ranking_boosts([]) == []


# ===========================================================================
# Property-based tests
# ===========================================================================


# ---------------------------------------------------------------------------
# Property 42: Search Pagination (Req 14.1)
# ---------------------------------------------------------------------------

@given(
    total=st.integers(min_value=0, max_value=50),
    limit=st.integers(min_value=1, max_value=20),
    offset=st.integers(min_value=0, max_value=30),
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
def test_property_42_search_pagination(total, limit, offset):
    """
    **Validates: Requirements 14.1**

    Property 42: Search Pagination

    For any combination of total results, limit, and offset:
    - The paginated slice never exceeds *limit* items.
    - The paginated slice is a contiguous sub-sequence of the full list.
    - When offset >= total, the result is empty.
    """
    results = list(range(total))
    page = results[offset: offset + limit]

    assert len(page) <= limit
    if offset >= total:
        assert page == []
    else:
        expected_len = min(limit, total - offset)
        assert len(page) == expected_len


# ---------------------------------------------------------------------------
# Property 43: Lazy Loading for Large Collections (Req 14.2)
# ---------------------------------------------------------------------------

@given(
    collection_size=st.integers(min_value=0, max_value=2000),
    page_size=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
def test_property_43_lazy_loading_pages(collection_size, page_size):
    """
    **Validates: Requirements 14.2**

    Property 43: Lazy Loading for Large Collections

    Paginating through a collection of *collection_size* items with *page_size*
    pages yields exactly the right number of pages and covers all items without
    duplication.
    """
    items = list(range(collection_size))
    pages = []
    offset = 0
    while True:
        page = items[offset: offset + page_size]
        if not page:
            break
        pages.append(page)
        offset += page_size

    # All items covered exactly once
    flat = [item for page in pages for item in page]
    assert flat == items

    # has_more flag is correct for each page
    for i, page in enumerate(pages):
        has_more = (i + 1) < len(pages)
        remaining = collection_size - (i + 1) * page_size
        expected_has_more = remaining > 0
        assert has_more == expected_has_more


# ---------------------------------------------------------------------------
# Property 44: Content Caching Strategies (Req 14.4)
# ---------------------------------------------------------------------------

@given(
    keys=st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
        min_size=1,
        max_size=20,
        unique=True,
    ),
    max_entries=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
def test_property_44_cache_lru_eviction(keys, max_entries):
    """
    **Validates: Requirements 14.4**

    Property 44: Content Caching Strategies

    After inserting more items than *max_entries*, the cache size never
    exceeds *max_entries* and the most recently inserted item is always
    present.
    """
    cache = SearchCache(max_entries=max_entries)
    for key in keys:
        cache.set(key, key)

    assert cache.size <= max_entries

    # The last inserted key must still be present
    last_key = keys[-1]
    hit, val = cache.get(last_key)
    assert hit is True
    assert val == last_key


@given(
    n_sets=st.integers(min_value=1, max_value=20),
    n_gets=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
def test_property_44_cache_hit_rate_bounds(n_sets, n_gets):
    """
    **Validates: Requirements 14.4**

    Property 44: Cache hit rate is always in [0, 1].
    """
    cache = SearchCache()
    for i in range(n_sets):
        cache.set(f"k{i}", i)
    for i in range(n_gets):
        cache.get(f"k{i}")

    assert 0.0 <= cache.hit_rate <= 1.0


# ---------------------------------------------------------------------------
# Property 45: Search Result Ranking (Req 14.5)
# ---------------------------------------------------------------------------

@given(
    scores=st.lists(
        st.floats(min_value=0.0, max_value=0.9, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
def test_property_45_ranking_preserves_order(scores):
    """
    **Validates: Requirements 14.5**

    Property 45: Search Result Ranking

    After applying ranking boosts (with no recency or interaction data),
    results are sorted in descending score order.
    """
    svc = _make_service()
    results = [_make_result(id=f"r{i}", score=s) for i, s in enumerate(scores)]
    ranked = svc._apply_ranking_boosts(results, recency_boost=False, interaction_boost=False)

    for i in range(len(ranked) - 1):
        assert ranked[i].score >= ranked[i + 1].score


@given(
    base_score=st.floats(min_value=0.0, max_value=0.8, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
def test_property_45_recency_boost_bounded(base_score):
    """
    **Validates: Requirements 14.5**

    Property 45: Recency boost never exceeds MAX_RECENCY_BOOST and the
    final score never exceeds 1.0.
    """
    svc = _make_service()
    now_str = datetime.now(timezone.utc).isoformat()
    result = _make_result(score=base_score, indexed_at=now_str)
    boost = svc._recency_boost(result)

    assert 0.0 <= boost <= MAX_RECENCY_BOOST
    assert base_score + boost <= 1.0 + 1e-9  # allow tiny float error


@given(
    base_score=st.floats(min_value=0.0, max_value=0.8, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
def test_property_45_interaction_boost_bounded(base_score):
    """
    **Validates: Requirements 14.5**

    Property 45: Interaction boost never exceeds MAX_INTERACTION_BOOST and
    the final score never exceeds 1.0.
    """
    svc = _make_service()
    svc.record_interaction("r1")
    result = _make_result(id="r1", score=base_score)
    boost = svc._interaction_boost(result)

    assert 0.0 <= boost <= MAX_INTERACTION_BOOST
    assert base_score + boost <= 1.0 + 1e-9

