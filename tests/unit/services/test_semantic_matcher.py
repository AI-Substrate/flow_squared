"""Tests for SemanticMatcher - embedding-based semantic search.

TDD tests for Phase 3: Semantic Matcher.

Per tasks.md:
- T002: Cosine similarity tests
- T004: Chunk iteration tests (Discovery 05)
- T005: Basic matching tests
- T006: Dual embedding search tests (AC06)
- T007: Min similarity threshold tests (AC05)
- T009: Missing/partial embeddings tests

Per DYK-P3-01: All search methods are async.
Per DYK-P3-04: min_similarity default 0.25, clamp negatives to 0.
Per Discovery 05: Iterate ALL chunks in embedding arrays.
"""

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.search import QuerySpec, SearchMode, SearchResult


# ============================================================================
# Test Fixtures - Helper functions to create test nodes
# ============================================================================


def create_node_with_embedding(
    node_id: str,
    embedding: tuple[tuple[float, ...], ...] | None = None,
    smart_content_embedding: tuple[tuple[float, ...], ...] | None = None,
    content: str | None = None,
    smart_content: str | None = None,
    start_line: int = 1,
    end_line: int = 10,
) -> CodeNode:
    """Create a test CodeNode with embeddings.

    Embeddings are tuple[tuple[float, ...], ...] to match chunk format.
    """
    return CodeNode(
        node_id=node_id,
        category=node_id.split(":")[0],
        ts_kind="function_definition",
        name=node_id.split(":")[-1] if ":" in node_id else node_id,
        qualified_name=node_id.split(":")[-1] if ":" in node_id else node_id,
        start_line=start_line,
        end_line=end_line,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=len(content) if content else 0,
        content=content or "",
        content_hash="test_hash",
        signature=None,
        language="python",
        is_named=True,
        field_name=None,
        smart_content=smart_content,
        embedding=embedding,
        smart_content_embedding=smart_content_embedding,
    )


# ============================================================================
# T002: Cosine Similarity Tests
# ============================================================================


class TestCosineSimilarity:
    """Cosine similarity function tests (T002).

    Per DYK-P3-04: Clamp negative scores to 0.
    """

    def test_identical_vectors_return_1_0(self) -> None:
        """Proves identical vectors have similarity 1.0.

        Purpose: Perfect match case.
        Quality Contribution: Score ceiling validation.
        Acceptance Criteria: cos([1,0], [1,0]) == 1.0.
        """
        from fs2.core.services.search.semantic_matcher import cosine_similarity

        a = [1.0, 0.0]
        b = [1.0, 0.0]
        result = cosine_similarity(a, b)
        assert result == pytest.approx(1.0, abs=0.001)

    def test_orthogonal_vectors_return_0(self) -> None:
        """Proves orthogonal vectors have similarity 0.

        Purpose: No correlation case.
        Quality Contribution: Zero score case.
        Acceptance Criteria: cos([1,0], [0,1]) == 0.
        """
        from fs2.core.services.search.semantic_matcher import cosine_similarity

        a = [1.0, 0.0]
        b = [0.0, 1.0]
        result = cosine_similarity(a, b)
        assert result == pytest.approx(0.0, abs=0.001)

    def test_opposite_vectors_clamped_to_0(self) -> None:
        """Proves negative similarity is clamped to 0 (DYK-P3-04).

        Purpose: Negative scores make no sense for search ranking.
        Quality Contribution: Prevents confusing negative results.
        Acceptance Criteria: cos([1,0], [-1,0]) clamped to 0 (not -1).
        """
        from fs2.core.services.search.semantic_matcher import cosine_similarity

        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        result = cosine_similarity(a, b)
        # Raw would be -1.0, but per DYK-P3-04 we clamp to 0
        assert result == pytest.approx(0.0, abs=0.001)

    def test_similar_vectors_high_score(self) -> None:
        """Proves similar vectors have high similarity.

        Purpose: Semantic similarity produces high scores.
        Quality Contribution: Validates scoring behavior.
        Acceptance Criteria: Similar vectors > 0.9.
        """
        from fs2.core.services.search.semantic_matcher import cosine_similarity

        # Slightly different but similar vectors
        a = [1.0, 0.1]
        b = [1.0, 0.2]
        result = cosine_similarity(a, b)
        assert result > 0.9

    def test_handles_high_dimensional_vectors(self) -> None:
        """Proves function works with 1024-dimensional vectors.

        Purpose: Real embeddings are high-dimensional.
        Quality Contribution: Production-scale validation.
        Acceptance Criteria: Works with 1024 dimensions.
        """
        from fs2.core.services.search.semantic_matcher import cosine_similarity
        import numpy as np

        # Create normalized 1024-dim vectors
        np.random.seed(42)  # Reproducible
        a = np.random.randn(1024).tolist()
        b = np.random.randn(1024).tolist()
        result = cosine_similarity(a, b)

        # Should be a valid score (may be near 0 for random vectors)
        assert 0.0 <= result <= 1.0


# ============================================================================
# T004: Chunk Iteration Tests
# ============================================================================


class TestChunkIteration:
    """Chunk iteration tests (T004, Discovery 05).

    Per Discovery 05: Iterate ALL chunks in embedding arrays.
    Best score across all chunks wins.
    """

    @pytest.mark.asyncio
    async def test_matches_first_chunk(self) -> None:
        """Proves first chunk can be matched.

        Purpose: Single-chunk case works.
        Quality Contribution: Basic chunk matching.
        Acceptance Criteria: First chunk matched returns result.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Query embedding (will match first chunk exactly)
        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # Node with single chunk in embedding
        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=((1.0, 0.0, 0.0, 0.0),),  # Single chunk
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [node],
        )

        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:func"
        assert results[0].score == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_best_chunk_wins_across_multiple_chunks(self) -> None:
        """Proves best chunk score is used when multiple chunks exist.

        Purpose: Multi-chunk matching per Discovery 05.
        Quality Contribution: Best semantic match wins.
        Acceptance Criteria: Highest chunk score becomes result score.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        # Query embedding
        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # Node with 3 chunks - second chunk is the best match
        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=(
                (0.0, 1.0, 0.0, 0.0),  # Chunk 0: orthogonal, score ~0
                (1.0, 0.0, 0.0, 0.0),  # Chunk 1: exact match, score 1.0
                (0.0, 0.0, 1.0, 0.0),  # Chunk 2: orthogonal, score ~0
            ),
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [node],
        )

        assert len(results) == 1
        # Best chunk (chunk 1) score should be used
        assert results[0].score == pytest.approx(1.0, abs=0.01)


# ============================================================================
# T005: Basic Matching Tests
# ============================================================================


class TestSemanticMatcherBasicMatching:
    """Basic semantic matching tests (T005).

    Tests fundamental matching behavior.
    """

    @pytest.mark.asyncio
    async def test_node_with_embedding_matches(self) -> None:
        """Proves nodes with embeddings can be matched.

        Purpose: Core semantic matching works.
        Quality Contribution: Validates fundamental behavior.
        Acceptance Criteria: Node with embedding returns result.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        node = create_node_with_embedding(
            "callable:test.py:SearchService",
            embedding=((0.9, 0.1, 0.0, 0.0),),  # Similar to query
            content="class SearchService: ...",
        )

        results = await matcher.match(
            QuerySpec(pattern="find service", mode=SearchMode.SEMANTIC),
            [node],
        )

        assert len(results) == 1
        assert results[0].node_id == "callable:test.py:SearchService"

    @pytest.mark.asyncio
    async def test_returns_search_result_with_required_fields(self) -> None:
        """Proves SearchResult has all required fields.

        Purpose: Contract verification.
        Quality Contribution: Validates return type structure.
        Acceptance Criteria: All SearchResult fields populated.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=((1.0, 0.0, 0.0, 0.0),),
            content="def func(): pass",
            smart_content="Does something important",
            start_line=10,
            end_line=15,
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [node],
        )

        assert len(results) == 1
        result = results[0]

        # Verify all required fields
        assert result.node_id == "callable:test.py:func"
        assert result.start_line == 10
        assert result.end_line == 15
        assert result.match_start_line >= 10
        assert result.match_end_line <= 15
        assert result.smart_content == "Does something important"
        assert result.snippet is not None
        assert 0.0 <= result.score <= 1.0
        assert result.match_field in ["embedding", "smart_content_embedding"]
        assert result.content == "def func(): pass"

    @pytest.mark.asyncio
    async def test_empty_nodes_returns_empty(self) -> None:
        """Proves empty node list returns empty results.

        Purpose: Edge case handling.
        Quality Contribution: Graceful empty state.
        Acceptance Criteria: Empty input returns [].
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        adapter = FakeEmbeddingAdapter()
        adapter.set_response([1.0, 0.0])

        matcher = SemanticMatcher(embedding_adapter=adapter)

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [],
        )

        assert results == []


# ============================================================================
# T006: Dual Embedding Search Tests
# ============================================================================


class TestDualEmbeddingSearch:
    """Dual embedding search tests (T006, AC06).

    Per AC06: Search both embedding and smart_content_embedding.
    Best score across all chunks from both fields wins.
    """

    @pytest.mark.asyncio
    async def test_matches_content_embedding(self) -> None:
        """Proves content embedding field is searched.

        Purpose: Primary embedding field works.
        Quality Contribution: Content embedding search.
        Acceptance Criteria: Match found in embedding field.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=((1.0, 0.0, 0.0, 0.0),),  # Matches query
            smart_content_embedding=None,  # No smart_content embedding
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [node],
        )

        assert len(results) == 1
        assert results[0].match_field == "embedding"

    @pytest.mark.asyncio
    async def test_matches_smart_content_embedding(self) -> None:
        """Proves smart_content_embedding field is searched.

        Purpose: AI summary embedding works.
        Quality Contribution: smart_content embedding search.
        Acceptance Criteria: Match found in smart_content_embedding field.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=None,  # No content embedding
            smart_content_embedding=((1.0, 0.0, 0.0, 0.0),),  # Matches query
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [node],
        )

        assert len(results) == 1
        assert results[0].match_field == "smart_content_embedding"

    @pytest.mark.asyncio
    async def test_best_embedding_wins_when_both_present(self) -> None:
        """Proves best score across both embedding fields is used.

        Purpose: Dual search finds best match.
        Quality Contribution: AC06 compliance.
        Acceptance Criteria: Higher score wins regardless of field.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # smart_content_embedding has better match
        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=((0.5, 0.5, 0.0, 0.0),),  # Partial match
            smart_content_embedding=((1.0, 0.0, 0.0, 0.0),),  # Exact match
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [node],
        )

        assert len(results) == 1
        # smart_content_embedding has better score
        assert results[0].match_field == "smart_content_embedding"
        assert results[0].score == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_content_embedding_wins_when_better(self) -> None:
        """Proves content embedding wins when it has better score.

        Purpose: Best score wins regardless of field order.
        Quality Contribution: Fair comparison.
        Acceptance Criteria: embedding field wins when better.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # embedding has better match
        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=((1.0, 0.0, 0.0, 0.0),),  # Exact match
            smart_content_embedding=((0.5, 0.5, 0.0, 0.0),),  # Partial match
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [node],
        )

        assert len(results) == 1
        assert results[0].match_field == "embedding"


# ============================================================================
# T007: Min Similarity Threshold Tests
# ============================================================================


class TestMinSimilarityThreshold:
    """Minimum similarity threshold tests (T007, AC05).

    Per AC05: Only return results above min_similarity.
    Per DYK-P3-04: Default threshold is 0.25.
    """

    @pytest.mark.asyncio
    async def test_above_threshold_included(self) -> None:
        """Proves results above threshold are included.

        Purpose: High-quality matches returned.
        Quality Contribution: Threshold filtering works.
        Acceptance Criteria: Score >= threshold is included.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # High similarity node
        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=((0.9, 0.1, 0.0, 0.0),),  # ~0.99 similarity
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC, min_similarity=0.25),
            [node],
        )

        assert len(results) == 1
        assert results[0].score > 0.25

    @pytest.mark.asyncio
    async def test_below_threshold_excluded(self) -> None:
        """Proves results below threshold are excluded.

        Purpose: Low-quality matches filtered out.
        Quality Contribution: Threshold filtering works.
        Acceptance Criteria: Score < threshold is excluded.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # Low similarity node (orthogonal)
        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=((0.0, 1.0, 0.0, 0.0),),  # ~0.0 similarity (orthogonal)
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC, min_similarity=0.25),
            [node],
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_default_threshold_is_0_25(self) -> None:
        """Proves default threshold is 0.25 (DYK-P3-04).

        Purpose: Default threshold validation.
        Quality Contribution: Confirms spec compliance.
        Acceptance Criteria: Default min_similarity=0.25.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # Node with 0.3 similarity (above 0.25)
        above_node = create_node_with_embedding(
            "callable:test.py:above",
            embedding=((0.7, 0.6, 0.0, 0.0),),  # Will have >0.25 similarity
        )

        # Node with ~0 similarity (below 0.25)
        below_node = create_node_with_embedding(
            "callable:test.py:below",
            embedding=((0.0, 1.0, 0.0, 0.0),),  # ~0 similarity (orthogonal)
        )

        # Use default min_similarity (0.25)
        spec = QuerySpec(pattern="query", mode=SearchMode.SEMANTIC)
        assert spec.min_similarity == 0.25

        results = await matcher.match(spec, [above_node, below_node])

        # Only above_node should be included
        node_ids = [r.node_id for r in results]
        assert "callable:test.py:above" in node_ids
        assert "callable:test.py:below" not in node_ids

    @pytest.mark.asyncio
    async def test_custom_threshold_respected(self) -> None:
        """Proves custom threshold is respected.

        Purpose: Threshold configurability.
        Quality Contribution: User control works.
        Acceptance Criteria: Custom threshold filters correctly.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # Node with ~0.7 similarity (using orthogonal component for lower score)
        # cos([1,0,0,0], [0.7,0.7,0,0]) = 0.7 / sqrt(0.98) = ~0.707
        node = create_node_with_embedding(
            "callable:test.py:func",
            embedding=((0.7, 0.7, 0.0, 0.0),),
        )

        # With high threshold (0.95) - should be excluded (score ~0.7)
        results_high = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC, min_similarity=0.95),
            [node],
        )
        assert len(results_high) == 0

        # With low threshold (0.5) - should be included (score ~0.7)
        results_low = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC, min_similarity=0.5),
            [node],
        )
        assert len(results_low) == 1


# ============================================================================
# T009: Missing/Partial Embeddings Tests
# ============================================================================


class TestMissingEmbeddings:
    """Missing and partial embeddings tests (T009).

    Per DYK-P3-05: Warn but proceed if some nodes lack embeddings.
    """

    @pytest.mark.asyncio
    async def test_nodes_without_embeddings_skipped(self) -> None:
        """Proves nodes without embeddings are skipped.

        Purpose: Graceful handling of unindexed nodes.
        Quality Contribution: Robustness.
        Acceptance Criteria: Nodes without embeddings don't crash.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # Node WITHOUT embeddings
        node_without = create_node_with_embedding(
            "callable:test.py:no_embed",
            embedding=None,
            smart_content_embedding=None,
        )

        # Node WITH embeddings
        node_with = create_node_with_embedding(
            "callable:test.py:has_embed",
            embedding=((1.0, 0.0, 0.0, 0.0),),
        )

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            [node_without, node_with],
        )

        # Only node_with should be in results
        node_ids = [r.node_id for r in results]
        assert "callable:test.py:has_embed" in node_ids
        assert "callable:test.py:no_embed" not in node_ids

    @pytest.mark.asyncio
    async def test_partial_coverage_does_not_crash(self) -> None:
        """Proves partial embedding coverage doesn't crash.

        Purpose: Mixed coverage works.
        Quality Contribution: Production resilience.
        Acceptance Criteria: Partial coverage returns results from indexed nodes.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # Mix of nodes with and without embeddings
        nodes = [
            create_node_with_embedding("callable:test.py:a", embedding=None),
            create_node_with_embedding("callable:test.py:b", embedding=((1.0, 0.0, 0.0, 0.0),)),
            create_node_with_embedding("callable:test.py:c", embedding=None),
            create_node_with_embedding("callable:test.py:d", embedding=((0.9, 0.1, 0.0, 0.0),)),
            create_node_with_embedding("callable:test.py:e", embedding=None),
        ]

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            nodes,
        )

        # Should get results from nodes b and d
        node_ids = [r.node_id for r in results]
        assert "callable:test.py:b" in node_ids
        assert "callable:test.py:d" in node_ids
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_all_nodes_without_embeddings_returns_empty(self) -> None:
        """Proves all nodes without embeddings returns empty (not error).

        Purpose: Edge case handling.
        Quality Contribution: Graceful degradation.
        Acceptance Criteria: No crash, empty results.
        """
        from fs2.core.services.search.semantic_matcher import SemanticMatcher
        from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

        query_embedding = [1.0, 0.0, 0.0, 0.0]

        adapter = FakeEmbeddingAdapter()
        adapter.set_response(query_embedding)

        matcher = SemanticMatcher(embedding_adapter=adapter)

        # All nodes without embeddings
        nodes = [
            create_node_with_embedding("callable:test.py:a", embedding=None),
            create_node_with_embedding("callable:test.py:b", embedding=None),
        ]

        results = await matcher.match(
            QuerySpec(pattern="query", mode=SearchMode.SEMANTIC),
            nodes,
        )

        # Should return empty, not crash
        assert results == []
