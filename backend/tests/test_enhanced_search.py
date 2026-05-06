"""
Tests for the enhanced search service (Task 7).

Covers:
- SearchHistory: add, get_recent, get_suggestions
- EnhancedSearchService: folder filtering, keyword scoring, deduplication,
  ranking, device relevance boost, graceful Qdrant unavailability
- Pydantic schemas: EnhancedSearchRequest, EnhancedSearchResponse,
  DeviceContextSearchRequest, SearchSuggestionsResponse, SearchHistoryResponse

Property-based tests validate:
- Property 9:  Folder-Based Search Filtering  (Req 4.3)
- Property 10: Global Search Coverage         (Req 4.4)
- Property 38: Search History and Suggestions (Req 12.5)
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.search_service import (
    EnhancedSearchService,
    SearchHistory,
    SearchResult,
    SearchType,
)
from app.schemas import (
    EnhancedSearchRequest,
    EnhancedSearchResponse,
    EnhancedSearchResult,
    DeviceContextSearchRequest,
    SearchSuggestionsResponse,
    SearchHistoryResponse,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_mock_client(collections=None, search_hits=None, scroll_points=None):
    """Build a minimal mock QdrantClient."""
    client = MagicMock()

    # get_collections
    if collections is not None:
        col_objects = [MagicMock(name=c) for c in collections]
        for obj, name in zip(col_objects, collections):
            obj.name = name
        client.get_collections.return_value = MagicMock(collections=col_objects)
    else:
        client.get_collections.return_value = MagicMock(collections=[])

    # search
    client.search.return_value = search_hits or []

    # scroll
    client.scroll.return_value = (scroll_points or [], None)

    return client


def _make_hit(id_: str, score: float, payload: dict | None = None):
    hit = MagicMock()
    hit.id = id_
    hit.score = score
    hit.payload = payload or {}
    return hit


def _make_point(id_: str, payload: dict | None = None, vector=None):
    point = MagicMock()
    point.id = id_
    point.payload = payload or {}
    point.vector = vector
    return point


# ---------------------------------------------------------------------------
# SearchHistory unit tests
# ---------------------------------------------------------------------------


class TestSearchHistory:
    def test_add_and_get_recent(self):
        h = SearchHistory()
        h.add("query one")
        h.add("query two")
        recent = h.get_recent(10)
        assert len(recent) == 2
        # Newest first
        assert recent[0]["query"] == "query two"
        assert recent[1]["query"] == "query one"

    def test_get_recent_respects_limit(self):
        h = SearchHistory()
        for i in range(20):
            h.add(f"query {i}")
        assert len(h.get_recent(5)) == 5

    def test_max_entries_eviction(self):
        h = SearchHistory()
        for i in range(110):
            h.add(f"query {i}")
        # Should not exceed MAX_ENTRIES
        assert len(h.get_recent(200)) == SearchHistory.MAX_ENTRIES

    def test_empty_query_not_stored(self):
        h = SearchHistory()
        h.add("")
        h.add("   ")
        assert h.get_recent(10) == []

    def test_get_suggestions_prefix_match(self):
        h = SearchHistory()
        h.add("arduino uno")
        h.add("arduino mega")
        h.add("raspberry pi")
        suggestions = h.get_suggestions("arduino", 5)
        assert len(suggestions) == 2
        assert all(s.lower().startswith("arduino") for s in suggestions)

    def test_get_suggestions_case_insensitive(self):
        h = SearchHistory()
        h.add("Arduino Uno")
        suggestions = h.get_suggestions("arduino", 5)
        assert "Arduino Uno" in suggestions

    def test_get_suggestions_empty_partial(self):
        h = SearchHistory()
        h.add("something")
        assert h.get_suggestions("", 5) == []

    def test_get_suggestions_deduplicates(self):
        h = SearchHistory()
        h.add("arduino uno")
        h.add("arduino uno")  # duplicate
        suggestions = h.get_suggestions("arduino", 5)
        assert suggestions.count("arduino uno") == 1

    def test_folder_filter_stored(self):
        h = SearchHistory()
        h.add("query", folder_filter=["dispositivi"])
        recent = h.get_recent(1)
        assert recent[0]["folder_filter"] == ["dispositivi"]


# ---------------------------------------------------------------------------
# EnhancedSearchService unit tests
# ---------------------------------------------------------------------------


class TestEnhancedSearchServiceHelpers:
    def test_keyword_score_full_match(self):
        score = EnhancedSearchService._keyword_score("arduino uno", "arduino uno board")
        assert score == 1.0

    def test_keyword_score_partial_match(self):
        score = EnhancedSearchService._keyword_score("arduino uno", "arduino board")
        assert 0.0 < score < 1.0

    def test_keyword_score_no_match(self):
        score = EnhancedSearchService._keyword_score("xyz", "arduino board")
        assert score == 0.0

    def test_keyword_score_empty_query(self):
        assert EnhancedSearchService._keyword_score("", "some text") == 0.0

    def test_keyword_score_empty_text(self):
        assert EnhancedSearchService._keyword_score("query", "") == 0.0

    def test_deduplicate_keeps_highest_score(self):
        r1 = SearchResult(id="1", title="t", content="c", score=0.5)
        r2 = SearchResult(id="1", title="t", content="c", score=0.9)
        r3 = SearchResult(id="2", title="t2", content="c2", score=0.3)
        deduped = EnhancedSearchService._deduplicate([r1, r2, r3])
        ids = {r.id: r.score for r in deduped}
        assert ids["1"] == 0.9
        assert ids["2"] == 0.3

    def test_rank_descending(self):
        results = [
            SearchResult(id="a", title="", content="", score=0.3),
            SearchResult(id="b", title="", content="", score=0.9),
            SearchResult(id="c", title="", content="", score=0.6),
        ]
        ranked = EnhancedSearchService._rank(results)
        scores = [r.score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_device_relevance_boost_match(self):
        device_info = {"name": "Arduino Uno", "manufacturer": "Arduino"}
        result = SearchResult(
            id="1",
            title="Arduino Uno Guide",
            content="This is about Arduino boards",
            score=0.5,
        )
        boost = EnhancedSearchService._device_relevance_boost(device_info, result)
        assert boost > 0.0

    def test_device_relevance_boost_no_match(self):
        device_info = {"name": "Raspberry Pi", "manufacturer": "RPi Foundation"}
        result = SearchResult(
            id="1",
            title="Arduino Guide",
            content="Arduino content",
            score=0.5,
        )
        boost = EnhancedSearchService._device_relevance_boost(device_info, result)
        assert boost == 0.0

    def test_device_relevance_boost_capped(self):
        device_info = {
            "name": "Arduino",
            "manufacturer": "Arduino",
            "model": "Arduino",
        }
        result = SearchResult(
            id="1",
            title="Arduino Arduino Arduino",
            content="Arduino Arduino Arduino",
            score=0.5,
        )
        boost = EnhancedSearchService._device_relevance_boost(device_info, result)
        assert boost <= 0.15


class TestEnhancedSearchServiceCollections:
    def test_resolve_collections_with_filter(self):
        client = _make_mock_client(collections=["col_a", "col_b", "col_c"])
        service = EnhancedSearchService(client)
        resolved = service._resolve_collections(["col_a", "col_b"])
        assert resolved == ["col_a", "col_b"]
        # Should NOT call get_collections when filter is provided
        client.get_collections.assert_not_called()

    def test_resolve_collections_without_filter(self):
        client = _make_mock_client(collections=["col_a", "col_b"])
        service = EnhancedSearchService(client)
        resolved = service._resolve_collections(None)
        assert set(resolved) == {"col_a", "col_b"}

    def test_resolve_collections_qdrant_unavailable(self):
        client = MagicMock()
        client.get_collections.side_effect = Exception("Qdrant down")
        service = EnhancedSearchService(client)
        resolved = service._resolve_collections(None)
        assert resolved == []


class TestEnhancedSearchServiceSearch:
    @pytest.mark.asyncio
    async def test_semantic_search_returns_results(self):
        hit = _make_hit("1", 0.8, {"title": "Doc", "content": "content"})
        client = _make_mock_client(collections=["col_a"], search_hits=[hit])
        service = EnhancedSearchService(client)

        with patch("app.search_service.embed_text_batch", return_value=[[0.1] * 384]):
            results = await service.semantic_search("test query", limit=5)

        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].score == 0.8

    @pytest.mark.asyncio
    async def test_semantic_search_folder_filter_restricts_collections(self):
        client = _make_mock_client(collections=["col_a", "col_b"], search_hits=[])
        service = EnhancedSearchService(client)

        with patch("app.search_service.embed_text_batch", return_value=[[0.1] * 384]):
            await service.semantic_search("query", folder_filter=["col_a"])

        # Only col_a should be searched
        calls = client.search.call_args_list
        searched_collections = [c.kwargs.get("collection_name") or c.args[0] for c in calls]
        assert "col_a" in searched_collections
        assert "col_b" not in searched_collections

    @pytest.mark.asyncio
    async def test_semantic_search_no_filter_searches_all(self):
        client = _make_mock_client(collections=["col_a", "col_b"], search_hits=[])
        service = EnhancedSearchService(client)

        with patch("app.search_service.embed_text_batch", return_value=[[0.1] * 384]):
            await service.semantic_search("query", folder_filter=None)

        calls = client.search.call_args_list
        searched_collections = {c.kwargs.get("collection_name") or c.args[0] for c in calls}
        assert {"col_a", "col_b"} == searched_collections

    @pytest.mark.asyncio
    async def test_semantic_search_qdrant_unavailable_returns_empty(self):
        client = MagicMock()
        client.get_collections.side_effect = Exception("down")
        service = EnhancedSearchService(client)

        with patch("app.search_service.embed_text_batch", return_value=[[0.1] * 384]):
            results = await service.semantic_search("query")

        assert results == []

    @pytest.mark.asyncio
    async def test_semantic_search_embedding_failure_returns_empty(self):
        client = _make_mock_client(collections=["col_a"])
        service = EnhancedSearchService(client)

        with patch("app.search_service.embed_text_batch", side_effect=Exception("embed fail")):
            results = await service.semantic_search("query")

        assert results == []

    @pytest.mark.asyncio
    async def test_keyword_search_returns_results(self):
        point = _make_point("1", {"title": "Doc", "content": "arduino content"})
        client = _make_mock_client(collections=["col_a"], scroll_points=[point])
        service = EnhancedSearchService(client)

        results = await service.keyword_search("arduino", limit=5)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_keyword_search_folder_filter(self):
        client = _make_mock_client(collections=["col_a", "col_b"], scroll_points=[])
        service = EnhancedSearchService(client)

        await service.keyword_search("query", folder_filter=["col_a"])

        calls = client.scroll.call_args_list
        searched_collections = [c.kwargs.get("collection_name") or c.args[0] for c in calls]
        assert "col_a" in searched_collections
        assert "col_b" not in searched_collections

    @pytest.mark.asyncio
    async def test_hybrid_search_combines_scores(self):
        hit = _make_hit("1", 0.8, {"title": "Doc", "content": "arduino content"})
        point = _make_point("1", {"title": "Doc", "content": "arduino content"})
        client = _make_mock_client(
            collections=["col_a"], search_hits=[hit], scroll_points=[point]
        )
        service = EnhancedSearchService(client)

        with patch("app.search_service.embed_text_batch", return_value=[[0.1] * 384]):
            results = await service.hybrid_search("arduino", limit=5, semantic_weight=0.7)

        assert len(results) >= 1
        # Score should be a weighted combination
        assert results[0].score > 0.0

    @pytest.mark.asyncio
    async def test_device_context_search_enriches_query(self):
        hit = _make_hit("1", 0.75, {"title": "Arduino Guide", "content": "arduino"})
        client = _make_mock_client(collections=["dispositivi"], search_hits=[hit])
        service = EnhancedSearchService(client)

        captured_texts = []

        def mock_embed(texts):
            captured_texts.extend(texts)
            return [[0.1] * 384]

        with patch("app.search_service.embed_text_batch", side_effect=mock_embed):
            results = await service.device_context_search(
                device_info={"name": "Arduino Uno", "manufacturer": "Arduino"},
                context_query="user manual",
            )

        # The enriched query should contain device info
        assert any("Arduino" in t for t in captured_texts)

    @pytest.mark.asyncio
    async def test_get_similar_devices_no_device_collections(self):
        client = _make_mock_client(collections=["appunti", "scuola"])
        service = EnhancedSearchService(client)

        results = await service.get_similar_devices("device_123")
        assert results == []

    @pytest.mark.asyncio
    async def test_get_similar_devices_fallback_to_text_search(self):
        """When device vector not found, falls back to semantic search."""
        client = _make_mock_client(collections=["dispositivi"], scroll_points=[])
        service = EnhancedSearchService(client)

        with patch("app.search_service.embed_text_batch", return_value=[[0.1] * 384]):
            results = await service.get_similar_devices("device_123")

        # Should not raise; returns empty or results from fallback
        assert isinstance(results, list)

    def test_get_search_suggestions(self):
        client = _make_mock_client()
        service = EnhancedSearchService(client)
        service._history.add("arduino uno")
        service._history.add("arduino mega")

        suggestions = service.get_search_suggestions("arduino", 5)
        assert len(suggestions) == 2

    def test_get_search_history(self):
        client = _make_mock_client()
        service = EnhancedSearchService(client)
        service._history.add("query one")
        service._history.add("query two")

        history = service.get_search_history(10)
        assert len(history) == 2


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_enhanced_search_request_defaults(self):
        req = EnhancedSearchRequest(query="test")
        assert req.limit == 10
        assert req.offset == 0
        assert req.folder_filter is None
        assert req.search_type == "semantic"
        assert req.semantic_weight == 0.7

    def test_enhanced_search_request_with_folder_filter(self):
        req = EnhancedSearchRequest(query="test", folder_filter=["dispositivi"])
        assert req.folder_filter == ["dispositivi"]

    def test_enhanced_search_response_structure(self):
        resp = EnhancedSearchResponse(
            results=[
                EnhancedSearchResult(
                    id="1",
                    title="Doc",
                    content="content",
                    score=0.9,
                )
            ],
            total=1,
            query="test",
            folder_filter=None,
            search_type="semantic",
        )
        assert resp.total == 1
        assert resp.results[0].score == 0.9

    def test_device_context_search_request(self):
        req = DeviceContextSearchRequest(
            device_info={"name": "Arduino Uno"},
            context_query="user manual",
        )
        assert req.limit == 10

    def test_search_suggestions_response(self):
        resp = SearchSuggestionsResponse(suggestions=["arduino uno", "arduino mega"])
        assert len(resp.suggestions) == 2

    def test_search_history_response(self):
        resp = SearchHistoryResponse(
            history=[{"query": "test", "folder_filter": []}]
        )
        assert len(resp.history) == 1


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------


# Property 9: Folder-Based Search Filtering (Req 4.3)
# When a folder_filter is provided, _resolve_collections returns exactly
# those collections (no extras, no missing).

@given(
    all_collections=st.lists(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("Ll", "Nd"), whitelist_characters="_"
            ),
        ),
        min_size=0,
        max_size=10,
        unique=True,
    ),
    filter_subset=st.lists(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("Ll", "Nd"), whitelist_characters="_"
            ),
        ),
        min_size=1,
        max_size=5,
        unique=True,
    ),
)
@settings(max_examples=25, suppress_health_check=[HealthCheck.too_slow])
def test_property_9_folder_filter_restricts_collections(all_collections, filter_subset):
    """
    **Property 9: Folder-Based Search Filtering**
    Validates: Requirements 4.3

    When a folder_filter is provided, _resolve_collections returns exactly
    the requested collections (no extras added, no items removed).
    """
    client = _make_mock_client(collections=all_collections)
    service = EnhancedSearchService(client)

    resolved = service._resolve_collections(filter_subset)

    # Must return exactly the filter_subset (order may differ)
    assert set(resolved) == set(filter_subset), (
        f"Expected {set(filter_subset)}, got {set(resolved)}"
    )
    # get_collections should NOT be called when a filter is provided
    client.get_collections.assert_not_called()


# Property 10: Global Search Coverage (Req 4.4)
# When no folder_filter is provided, _resolve_collections returns all
# available collections.

@given(
    collections=st.lists(
        st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(
                whitelist_categories=("Ll", "Nd"), whitelist_characters="_"
            ),
        ),
        min_size=0,
        max_size=10,
        unique=True,
    )
)
@settings(max_examples=25)
def test_property_10_global_search_coverage(collections):
    """
    **Property 10: Global Search Coverage**
    Validates: Requirements 4.4

    When no folder_filter is provided, _resolve_collections returns all
    collections registered in Qdrant.
    """
    client = _make_mock_client(collections=collections)
    service = EnhancedSearchService(client)

    resolved = service._resolve_collections(None)

    assert set(resolved) == set(collections), (
        f"Expected all collections {set(collections)}, got {set(resolved)}"
    )


# Property 38: Search History and Suggestions (Req 12.5)
# After adding N distinct queries, get_recent returns at most N entries,
# and get_suggestions returns only queries that start with the given prefix.

@given(
    queries=st.lists(
        st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters=" ")),
        min_size=1,
        max_size=20,
        unique=True,
    ),
    prefix=st.text(min_size=1, max_size=5, alphabet=st.characters(whitelist_categories=("Ll",))),
)
@settings(max_examples=25)
def test_property_38_search_history_and_suggestions(queries, prefix):
    """
    **Property 38: Search History and Suggestions**
    Validates: Requirements 12.5

    1. get_recent returns at most len(queries) entries (no duplicates invented).
    2. Every suggestion returned by get_suggestions starts with the prefix
       (case-insensitive).
    """
    history = SearchHistory()
    for q in queries:
        history.add(q)

    recent = history.get_recent(100)
    assert len(recent) <= len(queries), (
        f"get_recent returned more entries ({len(recent)}) than queries added ({len(queries)})"
    )

    suggestions = history.get_suggestions(prefix, limit=10)
    prefix_lower = prefix.lower()
    for s in suggestions:
        assert s.lower().startswith(prefix_lower), (
            f"Suggestion '{s}' does not start with prefix '{prefix}'"
        )

