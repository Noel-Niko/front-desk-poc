"""Tests for the handbook RAG pipeline."""

import pytest

from backend.app.services.handbook import (
    HandbookChunk,
    HandbookIndex,
    build_index,
    hybrid_search,
)


@pytest.fixture(scope="module")
def handbook_index() -> HandbookIndex:
    """Load the pre-built handbook index (requires build_index to have run)."""
    return build_index("backend/data/handbook.pdf", "backend/data/handbook_index")


class TestHandbookIndexBuild:
    def test_index_has_chunks(self, handbook_index: HandbookIndex) -> None:
        assert len(handbook_index.chunks) > 50  # 56-page PDF should produce many chunks

    def test_chunks_have_page_numbers(self, handbook_index: HandbookIndex) -> None:
        for chunk in handbook_index.chunks:
            assert chunk.page_number >= 1
            assert chunk.page_number <= 60  # Reasonable upper bound

    def test_chunks_have_text(self, handbook_index: HandbookIndex) -> None:
        for chunk in handbook_index.chunks:
            assert len(chunk.text) > 20

    def test_chunks_have_section_titles(self, handbook_index: HandbookIndex) -> None:
        for chunk in handbook_index.chunks:
            assert chunk.section_title  # Not empty


class TestHybridSearch:
    def test_illness_policy_returns_relevant_pages(self, handbook_index: HandbookIndex) -> None:
        results = hybrid_search(handbook_index, "illness policy fever child return")
        assert len(results) > 0
        # Should find pages around 44-46 (illness section)
        pages = {r.page_number for r in results}
        assert any(40 <= p <= 50 for p in pages), f"Expected illness pages, got: {pages}"

    def test_hours_of_operation(self, handbook_index: HandbookIndex) -> None:
        results = hybrid_search(handbook_index, "hours of operation when does center open close")
        assert len(results) > 0

    def test_enrollment_policy(self, handbook_index: HandbookIndex) -> None:
        results = hybrid_search(handbook_index, "enrollment how to enroll register child")
        assert len(results) > 0

    def test_empty_query_returns_results(self, handbook_index: HandbookIndex) -> None:
        # Even an empty-ish query should not crash
        results = hybrid_search(handbook_index, "hello")
        assert isinstance(results, list)

    def test_top_k_limits_results(self, handbook_index: HandbookIndex) -> None:
        results = hybrid_search(handbook_index, "policy", top_k=3)
        assert len(results) <= 3

    def test_results_are_handbook_chunks(self, handbook_index: HandbookIndex) -> None:
        results = hybrid_search(handbook_index, "meals lunch food")
        for r in results:
            assert isinstance(r, HandbookChunk)
            assert r.chunk_id
            assert r.page_number
            assert r.text


class TestSemanticSearch:
    def test_returns_results(self, handbook_index: HandbookIndex) -> None:
        results = handbook_index.semantic_search("when can a sick child return")
        assert len(results) > 0

    def test_results_limited_by_top_k(self, handbook_index: HandbookIndex) -> None:
        results = handbook_index.semantic_search("policy", top_k=2)
        assert len(results) <= 2


class TestKeywordSearch:
    def test_returns_results(self, handbook_index: HandbookIndex) -> None:
        results = handbook_index.keyword_search("immunization vaccine")
        assert len(results) > 0

    def test_no_results_for_gibberish(self, handbook_index: HandbookIndex) -> None:
        results = handbook_index.keyword_search("xyzzy123 foobar999")
        assert len(results) == 0
