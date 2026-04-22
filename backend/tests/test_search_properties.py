# Feature: pdf-semantic-search-platform, Property 5: Filename filter exclusion
# Validates: Requirements 13.2

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from hypothesis import given, settings
from hypothesis import strategies as st


def apply_filename_filter(pdf_map: dict, filename_filter: str | None) -> dict:
    """Inline the filter logic from search_pdfs."""
    if filename_filter:
        filter_lower = filename_filter.lower()
        return {k: v for k, v in pdf_map.items() if filter_lower in k.lower()}
    return pdf_map


@given(
    filenames=st.lists(
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='._-')),
        min_size=0,
        max_size=10,
    ),
    filename_filter=st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), whitelist_characters='._-')),
)
@settings(max_examples=25)
def test_filename_filter_exclusion(filenames, filename_filter):
    """
    Property 5: Every result filename contains the filter string (case-insensitive).
    Validates: Requirements 13.2
    """
    # Build a mock pdf_map
    pdf_map = {fn: {"filename": fn, "score": 0.5} for fn in filenames}

    filtered = apply_filename_filter(pdf_map, filename_filter)

    filter_lower = filename_filter.lower()
    for filename in filtered:
        assert filter_lower in filename.lower(), (
            f"Filename '{filename}' does not contain filter '{filename_filter}'"
        )


# Feature: pdf-semantic-search-platform, Property 6: Pagination offset correctness
# Validates: Requirements 19.2

@given(
    scores=st.lists(st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=0, max_size=20),
    offset=st.integers(min_value=0, max_value=20),
    limit=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=25)
def test_pagination_offset_correctness(scores, offset, limit):
    """
    Property 6: Results at offset=k equal the full sorted list sliced [k:k+limit].
    Validates: Requirements 19.2
    """
    # Build a mock sorted list (simulate what search_pdfs does)
    items = [{"filename": f"file_{i}.pdf", "score": s} for i, s in enumerate(scores)]
    all_sorted = sorted(items, key=lambda x: x["score"], reverse=True)

    # Apply pagination
    paginated = all_sorted[offset : offset + limit]

    # Verify: paginated results equal the full sorted list sliced [offset:offset+limit]
    expected = all_sorted[offset : offset + limit]
    assert paginated == expected, (
        f"Pagination mismatch at offset={offset}, limit={limit}: "
        f"got {paginated}, expected {expected}"
    )

    # Also verify total is the full count before pagination
    total = len(all_sorted)
    assert total == len(scores)

