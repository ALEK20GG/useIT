"""
Enhanced search service with folder filtering, device context search,
hybrid search strategies, search history/suggestions, recency boost,
and interaction-based ranking.

Implements Requirements 4.1-4.5, 12.1-12.5, and 14.3-14.5.
"""

import logging
import time
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchText, MatchValue

from .embeddings import embed_text_batch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ranking constants (Requirement 14.5)
# ---------------------------------------------------------------------------

# Maximum fractional boost applied to a base score (10 % of base score)
MAX_RECENCY_BOOST = 0.10
MAX_INTERACTION_BOOST = 0.10

# Documents indexed within this many seconds are considered "recent"
RECENCY_WINDOW_SECONDS = 7 * 24 * 3600  # 7 days


# ---------------------------------------------------------------------------
# Enums and data classes
# ---------------------------------------------------------------------------


class SearchType(str, Enum):
    """Supported search strategies."""

    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass
class SearchResult:
    """A single search result returned by the enhanced search service."""

    id: str
    title: str
    content: str
    score: float
    folder_id: Optional[str] = None
    source: str = "qdrant"  # "qdrant", "device_database", etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Search history
# ---------------------------------------------------------------------------


class SearchHistory:
    """
    In-memory search history with a maximum of 100 entries.

    Supports recent-query retrieval and prefix-based suggestions.
    """

    MAX_ENTRIES = 100

    def __init__(self) -> None:
        # deque gives O(1) append and automatic eviction at max length
        self._entries: deque[dict] = deque(maxlen=self.MAX_ENTRIES)

    def add(self, query: str, folder_filter: Optional[List[str]] = None) -> None:
        """Record a new search query."""
        if not query or not query.strip():
            return
        self._entries.appendleft(
            {
                "query": query.strip(),
                "folder_filter": folder_filter or [],
            }
        )

    def get_recent(self, limit: int = 10) -> List[dict]:
        """Return the most recent *limit* search entries (newest first)."""
        return list(self._entries)[:limit]

    def get_suggestions(self, partial: str, limit: int = 5) -> List[str]:
        """
        Return up to *limit* unique past queries that start with *partial*
        (case-insensitive).
        """
        if not partial:
            return []

        partial_lower = partial.lower()
        seen: set[str] = set()
        suggestions: List[str] = []

        for entry in self._entries:
            q = entry["query"]
            if q.lower().startswith(partial_lower) and q not in seen:
                seen.add(q)
                suggestions.append(q)
                if len(suggestions) >= limit:
                    break

        return suggestions


# ---------------------------------------------------------------------------
# Interaction tracker (Requirement 14.5)
# ---------------------------------------------------------------------------


class InteractionTracker:
    """
    Tracks which search result IDs have been clicked or saved by the user.

    Stores a bounded set of interacted IDs so that the search service can
    apply a small relevance boost to previously interacted results.
    """

    MAX_ENTRIES = 1000

    def __init__(self) -> None:
        self._interactions: OrderedDict[str, bool] = OrderedDict()

    def record(self, result_id: str) -> None:
        """Record that the user interacted with *result_id*."""
        if result_id in self._interactions:
            self._interactions.move_to_end(result_id)
        else:
            self._interactions[result_id] = True
            if len(self._interactions) > self.MAX_ENTRIES:
                self._interactions.popitem(last=False)

    def has_interaction(self, result_id: str) -> bool:
        """Return True if the user has previously interacted with *result_id*."""
        return result_id in self._interactions

    @property
    def size(self) -> int:
        return len(self._interactions)


# ---------------------------------------------------------------------------
# Enhanced search service
# ---------------------------------------------------------------------------


class EnhancedSearchService:
    """
    Advanced search service supporting folder filtering, hybrid search,
    device context search, search history, recency boost, and interaction
    tracking.

    Gracefully handles cases where Qdrant is unavailable by returning
    empty result lists instead of raising exceptions.
    """

    def __init__(self, qdrant_client: QdrantClient) -> None:
        self._client = qdrant_client
        self._history = SearchHistory()
        self._interactions = InteractionTracker()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_all_collection_names(self) -> List[str]:
        """Return all collection names currently registered in Qdrant."""
        try:
            response = self._client.get_collections()
            return [c.name for c in response.collections]
        except Exception as exc:
            logger.warning("Could not list Qdrant collections: %s", exc)
            return []

    def _resolve_collections(
        self, folder_filter: Optional[List[str]]
    ) -> List[str]:
        """
        Resolve the list of Qdrant collections to search.

        - If *folder_filter* is provided, use those collection names directly
          (Requirement 4.3).
        - Otherwise search all available collections (Requirement 4.4).
        """
        if folder_filter:
            return [f for f in folder_filter if f]
        return self._get_all_collection_names()

    @staticmethod
    def _point_to_result(hit: Any, source: str = "qdrant") -> SearchResult:
        """Convert a Qdrant scored point to a SearchResult."""
        payload = hit.payload or {}
        return SearchResult(
            id=str(hit.id),
            title=payload.get("title", payload.get("filename", str(hit.id))),
            content=payload.get("content", payload.get("chunk_text", "")),
            score=float(hit.score),
            folder_id=payload.get("folder_id"),
            source=source,
            metadata={k: v for k, v in payload.items()
                      if k not in ("title", "content", "chunk_text", "folder_id")},
        )

    @staticmethod
    def _deduplicate(results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate results keeping the highest-scoring entry per id."""
        seen: Dict[str, SearchResult] = {}
        for r in results:
            if r.id not in seen or r.score > seen[r.id].score:
                seen[r.id] = r
        return list(seen.values())

    @staticmethod
    def _rank(results: List[SearchResult]) -> List[SearchResult]:
        """Sort results by score descending."""
        return sorted(results, key=lambda r: r.score, reverse=True)

    # ------------------------------------------------------------------
    # Ranking boost helpers (Requirement 14.5)
    # ------------------------------------------------------------------

    @staticmethod
    def _recency_boost(
        result: SearchResult, max_boost: float = MAX_RECENCY_BOOST
    ) -> float:
        """
        Return a small score boost for recently indexed documents.

        Documents indexed within RECENCY_WINDOW_SECONDS receive a boost that
        decays linearly from *max_boost* (just indexed) to 0 (at the window
        boundary).  Documents older than the window receive no boost.

        Requirement 14.5: ranking based on recency.
        """
        indexed_at_str: Optional[str] = (
            result.metadata.get("indexed_at")
            or result.metadata.get("upload_date")
        )
        if not indexed_at_str:
            return 0.0
        try:
            indexed_at = datetime.fromisoformat(
                indexed_at_str.replace("Z", "+00:00")
            )
            now = datetime.now(timezone.utc)
            age_seconds = (now - indexed_at).total_seconds()
            if age_seconds < 0:
                age_seconds = 0.0
            if age_seconds >= RECENCY_WINDOW_SECONDS:
                return 0.0
            # Linear decay: max_boost at age=0, 0 at age=RECENCY_WINDOW_SECONDS
            decay = 1.0 - (age_seconds / RECENCY_WINDOW_SECONDS)
            return max_boost * decay
        except (ValueError, TypeError):
            return 0.0

    def _interaction_boost(
        self, result: SearchResult, max_boost: float = MAX_INTERACTION_BOOST
    ) -> float:
        """
        Return a small score boost for results the user has previously
        clicked or saved.

        Requirement 14.5: ranking based on user interaction patterns.
        """
        if self._interactions.has_interaction(result.id):
            return max_boost
        return 0.0

    def _apply_ranking_boosts(
        self,
        results: List[SearchResult],
        recency_boost: bool = True,
        interaction_boost: bool = True,
    ) -> List[SearchResult]:
        """
        Apply recency and interaction boosts to a list of results and re-sort.

        Each boost is individually capped at its maximum (10 %).

        Requirement 14.5.
        """
        boosted: List[SearchResult] = []
        for r in results:
            extra = 0.0
            if recency_boost:
                extra += self._recency_boost(r)
            if interaction_boost:
                extra += self._interaction_boost(r)
            if extra > 0.0:
                boosted.append(
                    SearchResult(
                        id=r.id,
                        title=r.title,
                        content=r.content,
                        score=min(r.score + extra, 1.0),
                        folder_id=r.folder_id,
                        source=r.source,
                        metadata=r.metadata,
                    )
                )
            else:
                boosted.append(r)
        return self._rank(boosted)

    # ------------------------------------------------------------------
    # Public search methods
    # ------------------------------------------------------------------

    async def semantic_search(
        self,
        query: str,
        folder_filter: Optional[List[str]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[SearchResult]:
        """
        Perform semantic (vector) search with optional folder filtering.

        Requirement 4.1: natural language query input.
        Requirement 4.3: restrict to folder collection when filter provided.
        Requirement 4.4: search all collections when no filter.
        Requirement 14.5: apply recency and interaction boosts.
        """
        self._history.add(query, folder_filter)

        try:
            query_vector = embed_text_batch([query])[0]
        except Exception as exc:
            logger.error("Failed to generate query embedding: %s", exc)
            return []

        collections = self._resolve_collections(folder_filter)
        all_results: List[SearchResult] = []

        for collection in collections:
            try:
                hits = self._client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=limit + offset,
                    with_payload=True,
                )
                for hit in hits:
                    all_results.append(self._point_to_result(hit))
            except Exception as exc:
                logger.warning(
                    "Semantic search failed for collection '%s': %s", collection, exc
                )

        results = self._apply_ranking_boosts(self._deduplicate(all_results))
        return results[offset: offset + limit]

    async def keyword_search(
        self,
        query: str,
        folder_filter: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """
        Perform keyword (payload text match) search with optional folder filtering.

        Uses Qdrant's MatchText filter to find documents whose payload fields
        contain the query terms.
        """
        self._history.add(query, folder_filter)

        collections = self._resolve_collections(folder_filter)
        all_results: List[SearchResult] = []

        # Build a filter that matches the query text in common text fields
        text_filter = Filter(
            should=[
                FieldCondition(key="content", match=MatchText(text=query)),
                FieldCondition(key="chunk_text", match=MatchText(text=query)),
                FieldCondition(key="title", match=MatchText(text=query)),
            ]
        )

        for collection in collections:
            try:
                points, _ = self._client.scroll(
                    collection_name=collection,
                    scroll_filter=text_filter,
                    limit=limit,
                    with_payload=True,
                    with_vectors=False,
                )
                for point in points:
                    # Assign a keyword relevance score based on match count
                    payload = point.payload or {}
                    score = self._keyword_score(
                        query,
                        " ".join(
                            str(v)
                            for v in [
                                payload.get("content", ""),
                                payload.get("chunk_text", ""),
                                payload.get("title", ""),
                            ]
                        ),
                    )
                    result = SearchResult(
                        id=str(point.id),
                        title=payload.get(
                            "title", payload.get("filename", str(point.id))
                        ),
                        content=payload.get(
                            "content", payload.get("chunk_text", "")
                        ),
                        score=score,
                        folder_id=payload.get("folder_id"),
                        source="qdrant",
                        metadata={
                            k: v
                            for k, v in payload.items()
                            if k
                            not in ("title", "content", "chunk_text", "folder_id")
                        },
                    )
                    all_results.append(result)
            except Exception as exc:
                logger.warning(
                    "Keyword search failed for collection '%s': %s", collection, exc
                )

        results = self._apply_ranking_boosts(self._deduplicate(all_results))
        return results[:limit]

    @staticmethod
    def _keyword_score(query: str, text: str) -> float:
        """
        Simple keyword relevance score: fraction of query words found in text,
        scaled to [0, 1].
        """
        if not query or not text:
            return 0.0
        query_words = [w.lower() for w in query.split() if len(w) > 1]
        if not query_words:
            return 0.0
        text_lower = text.lower()
        matches = sum(1 for w in query_words if w in text_lower)
        return matches / len(query_words)

    async def hybrid_search(
        self,
        query: str,
        folder_filter: Optional[List[str]] = None,
        limit: int = 10,
        semantic_weight: float = 0.7,
    ) -> List[SearchResult]:
        """
        Combine semantic and keyword search results.

        The final score is a weighted combination:
            final_score = semantic_weight * semantic_score
                        + (1 - semantic_weight) * keyword_score

        Requirement 4.5: return results from both internal database and
        external sources based on search context.
        Requirement 14.5: apply recency and interaction boosts.
        """
        self._history.add(query, folder_filter)

        keyword_weight = 1.0 - semantic_weight

        try:
            query_vector = embed_text_batch([query])[0]
        except Exception as exc:
            logger.error("Failed to generate query embedding: %s", exc)
            return []

        collections = self._resolve_collections(folder_filter)

        # Collect semantic scores
        semantic_scores: Dict[str, float] = {}
        semantic_results: Dict[str, SearchResult] = {}

        for collection in collections:
            try:
                hits = self._client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=limit * 3,
                    with_payload=True,
                )
                for hit in hits:
                    r = self._point_to_result(hit)
                    if r.id not in semantic_scores or r.score > semantic_scores[r.id]:
                        semantic_scores[r.id] = r.score
                        semantic_results[r.id] = r
            except Exception as exc:
                logger.warning(
                    "Hybrid semantic search failed for collection '%s': %s",
                    collection,
                    exc,
                )

        # Collect keyword scores
        keyword_scores: Dict[str, float] = {}
        text_filter = Filter(
            should=[
                FieldCondition(key="content", match=MatchText(text=query)),
                FieldCondition(key="chunk_text", match=MatchText(text=query)),
                FieldCondition(key="title", match=MatchText(text=query)),
            ]
        )

        for collection in collections:
            try:
                points, _ = self._client.scroll(
                    collection_name=collection,
                    scroll_filter=text_filter,
                    limit=limit * 3,
                    with_payload=True,
                    with_vectors=False,
                )
                for point in points:
                    payload = point.payload or {}
                    kw_score = self._keyword_score(
                        query,
                        " ".join(
                            str(v)
                            for v in [
                                payload.get("content", ""),
                                payload.get("chunk_text", ""),
                                payload.get("title", ""),
                            ]
                        ),
                    )
                    pid = str(point.id)
                    if pid not in keyword_scores or kw_score > keyword_scores[pid]:
                        keyword_scores[pid] = kw_score
                        if pid not in semantic_results:
                            semantic_results[pid] = SearchResult(
                                id=pid,
                                title=payload.get(
                                    "title", payload.get("filename", pid)
                                ),
                                content=payload.get(
                                    "content", payload.get("chunk_text", "")
                                ),
                                score=0.0,
                                folder_id=payload.get("folder_id"),
                                source="qdrant",
                                metadata={
                                    k: v
                                    for k, v in payload.items()
                                    if k
                                    not in (
                                        "title",
                                        "content",
                                        "chunk_text",
                                        "folder_id",
                                    )
                                },
                            )
            except Exception as exc:
                logger.warning(
                    "Hybrid keyword search failed for collection '%s': %s",
                    collection,
                    exc,
                )

        # Combine scores
        all_ids = set(semantic_scores) | set(keyword_scores)
        combined: List[SearchResult] = []
        for pid in all_ids:
            sem = semantic_scores.get(pid, 0.0)
            kw = keyword_scores.get(pid, 0.0)
            final_score = semantic_weight * sem + keyword_weight * kw
            result = semantic_results[pid]
            combined.append(
                SearchResult(
                    id=result.id,
                    title=result.title,
                    content=result.content,
                    score=final_score,
                    folder_id=result.folder_id,
                    source=result.source,
                    metadata=result.metadata,
                )
            )

        results = self._apply_ranking_boosts(combined)
        return results[:limit]

    async def device_context_search(
        self,
        device_info: dict,
        context_query: str,
        limit: int = 10,
    ) -> List[SearchResult]:
        """
        Search with device context prepended to the query for better relevance.

        Requirement 12.1: consider device categories and relationships.
        Requirement 12.2: enhance results with related device information.
        Requirement 12.4: support contextual queries like
            "devices similar to [identified device]".
        """
        # Build an enriched query that includes device context
        device_parts = []
        for key in ("name", "manufacturer", "model", "category"):
            val = device_info.get(key)
            if val:
                device_parts.append(str(val))

        if device_parts:
            enriched_query = f"{' '.join(device_parts)} {context_query}".strip()
        else:
            enriched_query = context_query

        self._history.add(enriched_query)

        try:
            query_vector = embed_text_batch([enriched_query])[0]
        except Exception as exc:
            logger.error("Failed to generate device context embedding: %s", exc)
            return []

        collections = self._get_all_collection_names()
        all_results: List[SearchResult] = []

        for collection in collections:
            try:
                hits = self._client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    limit=limit,
                    with_payload=True,
                )
                for hit in hits:
                    result = self._point_to_result(hit)
                    # Boost results that mention the device name/manufacturer
                    boost = self._device_relevance_boost(device_info, result)
                    all_results.append(
                        SearchResult(
                            id=result.id,
                            title=result.title,
                            content=result.content,
                            score=min(result.score + boost, 1.0),
                            folder_id=result.folder_id,
                            source=result.source,
                            metadata=result.metadata,
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "Device context search failed for collection '%s': %s",
                    collection,
                    exc,
                )

        return self._rank(self._deduplicate(all_results))[:limit]

    @staticmethod
    def _device_relevance_boost(device_info: dict, result: SearchResult) -> float:
        """
        Calculate a small relevance boost when the result content mentions
        the device name, manufacturer, or model.
        """
        boost = 0.0
        text = (result.title + " " + result.content).lower()
        for key in ("name", "manufacturer", "model"):
            val = device_info.get(key, "")
            if val and str(val).lower() in text:
                boost += 0.05
        return min(boost, 0.15)

    async def get_similar_devices(
        self,
        device_id: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Find devices with similar embeddings in the device database.

        Requirement 12.3: suggest similar devices when documentation is incomplete.
        Requirement 12.4: support "devices similar to [identified device]".

        Searches the 'dispositivi' collection (and any collection whose name
        contains 'device') for points similar to the given device_id.
        """
        collections = self._get_all_collection_names()
        device_collections = [
            c for c in collections if "dispositivi" in c or "device" in c
        ]

        if not device_collections:
            logger.info("No device collections found for similar device search")
            return []

        # Find the source point's vector
        source_vector: Optional[List[float]] = None
        for collection in device_collections:
            try:
                points, _ = self._client.scroll(
                    collection_name=collection,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key="device_id", match=MatchValue(value=device_id)
                            )
                        ]
                    ),
                    limit=1,
                    with_payload=True,
                    with_vectors=True,
                )
                if points:
                    source_vector = points[0].vector  # type: ignore[assignment]
                    break
            except Exception as exc:
                logger.warning(
                    "Could not retrieve device vector from '%s': %s", collection, exc
                )

        if source_vector is None:
            # Fall back to a text-based search using the device_id as query
            return await self.semantic_search(
                query=device_id,
                folder_filter=device_collections,
                limit=limit,
            )

        all_results: List[SearchResult] = []
        for collection in device_collections:
            try:
                hits = self._client.search(
                    collection_name=collection,
                    query_vector=source_vector,
                    limit=limit + 1,  # +1 to exclude the source itself
                    with_payload=True,
                )
                for hit in hits:
                    if str(hit.id) != device_id:
                        all_results.append(self._point_to_result(hit))
            except Exception as exc:
                logger.warning(
                    "Similar device search failed for collection '%s': %s",
                    collection,
                    exc,
                )

        return self._rank(self._deduplicate(all_results))[:limit]

    # ------------------------------------------------------------------
    # Interaction recording (Requirement 14.5)
    # ------------------------------------------------------------------

    def record_interaction(self, result_id: str) -> None:
        """
        Record that the user interacted with (clicked or saved) a result.

        Subsequent searches will apply a small boost to this result.

        Requirement 14.5: ranking based on user interaction patterns.
        """
        self._interactions.record(result_id)

    # ------------------------------------------------------------------
    # History and suggestions
    # ------------------------------------------------------------------

    def get_search_suggestions(self, partial: str, limit: int = 5) -> List[str]:
        """
        Return query suggestions based on previous searches.

        Requirement 12.5: provide query suggestions based on previous searches.
        """
        return self._history.get_suggestions(partial, limit)

    def get_search_history(self, limit: int = 10) -> List[dict]:
        """
        Return recent search history entries.

        Requirement 12.5: maintain search history.
        """
        return self._history.get_recent(limit)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_search_service: Optional[EnhancedSearchService] = None


def get_enhanced_search_service(qdrant_client: QdrantClient) -> EnhancedSearchService:
    """Return (or create) the module-level EnhancedSearchService singleton."""
    global _search_service
    if _search_service is None:
        _search_service = EnhancedSearchService(qdrant_client)
    return _search_service
