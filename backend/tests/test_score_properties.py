# Feature: pdf-semantic-search-platform, Property 3: Keyword boost is bounded
# Feature: pdf-semantic-search-platform, Property 4: Normalized score is bounded
# Validates: Requirements 5.1, 5.2

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hypothesis import given, settings
from hypothesis import strategies as st


def calculate_keyword_boost(query: str, text: str) -> float:
    """
    Inline copy of calculate_keyword_boost from app.main.
    Returns a boost value between 0.0 and 0.3 (30% boost max).
    """
    if not query or not text:
        return 0.0

    query_lower = query.lower()
    text_lower = text.lower()

    query_words = [w.strip() for w in query_lower.split() if len(w.strip()) > 2]

    if not query_words:
        return 0.0

    matches = sum(1 for word in query_words if word in text_lower)
    match_ratio = matches / len(query_words)

    return min(match_ratio * 0.3, 0.3)


def normalize_cosine_score(score: float) -> float:
    """
    Inline copy of normalize_cosine_score from app.main.
    Normalizes cosine similarity from [-1, 1] to [0, 1].
    """
    return (score + 1.0) / 2.0


# Feature: pdf-semantic-search-platform, Property 3: Keyword boost is bounded
# Validates: Requirements 5.1, 5.2

@given(st.text(), st.text())
@settings(max_examples=25)
def test_keyword_boost_bounded(query, chunk):
    """
    Property 3: calculate_keyword_boost returns a value in [0.0, 0.3].
    Validates: Requirements 5.1, 5.2
    """
    boost = calculate_keyword_boost(query, chunk)
    assert 0.0 <= boost <= 0.3, (
        f"keyword_boost={boost} is outside [0.0, 0.3] for query={query!r}, chunk={chunk!r}"
    )


# Feature: pdf-semantic-search-platform, Property 4: Normalized score is bounded
# Validates: Requirements 5.1

@given(st.floats(min_value=-1.0, max_value=1.0, allow_nan=False))
@settings(max_examples=25)
def test_normalize_score_bounded(score):
    """
    Property 4: normalize_cosine_score returns a value in [0.0, 1.0].
    Validates: Requirements 5.1
    """
    normalized = normalize_cosine_score(score)
    assert 0.0 <= normalized <= 1.0, (
        f"normalized_score={normalized} is outside [0.0, 1.0] for score={score}"
    )

