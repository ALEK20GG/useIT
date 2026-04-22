# Feature: pdf-semantic-search-platform, Property 1: Chunk round-trip completeness
# Validates: Requirements 16.4

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hypothesis import given, settings
from hypothesis import strategies as st
from app.pdf_utils import chunk_text


@given(st.text(min_size=1, max_size=5000))
@settings(max_examples=25)
def test_chunk_roundtrip_completeness(text):
    """
    Property 1: Every word in the original text appears in the concatenation of all chunks.
    Validates: Requirements 16.4
    """
    chunks = chunk_text(text)
    if not chunks:
        # Empty chunks means text was empty/whitespace — acceptable
        assert not text.strip()
        return

    combined = ' '.join(chunks)

    # Every word in the original text should appear in the combined chunks
    original_words = set(text.split())
    combined_words = set(combined.split())

    missing = original_words - combined_words
    assert not missing, (
        f"Words missing from chunks: {missing!r}\n"
        f"Original text: {text!r}\n"
        f"Chunks: {chunks!r}"
    )


# Feature: pdf-semantic-search-platform, Property 2: Chunk minimum length invariant
# Validates: Requirements 16.3

@given(st.text(min_size=101, max_size=5000))
@settings(max_examples=25)
def test_chunk_minimum_length_invariant(text):
    """
    Property 2: Every chunk except the last has length >= 100.
    Validates: Requirements 16.3
    """
    chunks = chunk_text(text)
    if len(chunks) <= 1:
        return  # Only one chunk — no constraint on minimum length

    for i, chunk in enumerate(chunks[:-1]):  # All except the last
        assert len(chunk) >= 100, (
            f"Chunk {i} has length {len(chunk)} < 100: {chunk!r}\n"
            f"All chunks: {[len(c) for c in chunks]}"
        )

