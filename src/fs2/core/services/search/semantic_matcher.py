"""SemanticMatcher - Embedding-based semantic search.

Provides semantic search using cosine similarity between query embeddings
and pre-computed node embeddings.

Per Phase 3 tasks.md:
- Discovery 05: Iterate ALL chunks in embedding arrays
- AC05: Filter by min_similarity threshold
- AC06: Search both embedding and smart_content_embedding
- DYK-P3-01: All methods are async
- DYK-P3-04: Clamp negative scores to 0, default min_similarity=0.25
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from numpy.linalg import norm

from fs2.core.models.code_node import CodeNode
from fs2.core.models.search import QuerySpec, SearchResult

if TYPE_CHECKING:
    from fs2.core.adapters.embedding_adapter import EmbeddingAdapter


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Per DYK-P3-04: Clamp negative values to 0 (negative scores
    don't make sense for search ranking).

    Args:
        a: First vector as list of floats.
        b: Second vector as list of floats.

    Returns:
        Cosine similarity clamped to [0.0, 1.0].
    """
    a_arr = np.array(a)
    b_arr = np.array(b)

    # Compute raw cosine similarity
    dot_product = float(np.dot(a_arr, b_arr))
    magnitude = float(norm(a_arr) * norm(b_arr))

    if magnitude == 0:
        return 0.0

    raw_score = dot_product / magnitude

    # Per DYK-P3-04: Clamp negative scores to 0
    return max(0.0, raw_score)


@dataclass
class ChunkMatch:
    """Internal result from matching a single chunk.

    Tracks which field and chunk produced the best score.
    """

    field_name: str  # "embedding" or "smart_content_embedding"
    chunk_index: int
    score: float


class SemanticMatcher:
    """Embedding-based semantic search with chunk iteration.

    Uses cosine similarity to find semantically similar nodes.

    Per Discovery 05: Iterates ALL chunks in both `embedding` and
    `smart_content_embedding` arrays. Best score across all chunks wins.

    Per AC05: Filters results by min_similarity threshold.
    Per AC06: Searches both embedding fields.
    Per DYK-P3-04: Default min_similarity is 0.25.

    Example:
        >>> matcher = SemanticMatcher(embedding_adapter=adapter)
        >>> results = await matcher.match(spec, nodes)
    """

    def __init__(self, embedding_adapter: "EmbeddingAdapter") -> None:
        """Initialize SemanticMatcher with embedding adapter.

        Args:
            embedding_adapter: Adapter for generating query embeddings.
        """
        self._adapter = embedding_adapter

    async def match(
        self,
        spec: QuerySpec,
        nodes: list[CodeNode],
    ) -> list[SearchResult]:
        """Match query against nodes using semantic similarity.

        Per Discovery 05: Iterates ALL chunks in embedding arrays.
        Per AC05: Filters by min_similarity threshold.
        Per AC06: Searches both embedding and smart_content_embedding.

        Args:
            spec: Query specification with pattern and min_similarity.
            nodes: List of CodeNodes to search.

        Returns:
            List of SearchResult for nodes above threshold.
            Results are NOT sorted (caller handles sorting).
        """
        if not nodes:
            return []

        # Get query embedding
        query_embedding = await self._adapter.embed_text(spec.pattern)

        results: list[SearchResult] = []

        for node in nodes:
            # Skip nodes without any embeddings
            if not node.embedding and not node.smart_content_embedding:
                continue

            # Find best match across all chunks in both fields
            best_match = self._find_best_chunk_match(query_embedding, node)

            if best_match is None:
                continue

            # Apply threshold filter (AC05)
            if best_match.score < spec.min_similarity:
                continue

            # Build result
            result = self._build_result(node, best_match)
            results.append(result)

        return results

    def _find_best_chunk_match(
        self,
        query_embedding: list[float],
        node: CodeNode,
    ) -> ChunkMatch | None:
        """Find the best matching chunk across all embedding fields.

        Per Discovery 05: Iterate ALL chunks in both embedding fields.

        Args:
            query_embedding: The query's embedding vector.
            node: The CodeNode to search.

        Returns:
            ChunkMatch with best score, or None if no embeddings.
        """
        best: ChunkMatch | None = None

        # Search embedding field (content embedding)
        if node.embedding:
            for chunk_idx, chunk in enumerate(node.embedding):
                score = cosine_similarity(query_embedding, list(chunk))
                if best is None or score > best.score:
                    best = ChunkMatch("embedding", chunk_idx, score)

        # Search smart_content_embedding field
        if node.smart_content_embedding:
            for chunk_idx, chunk in enumerate(node.smart_content_embedding):
                score = cosine_similarity(query_embedding, list(chunk))
                if best is None or score > best.score:
                    best = ChunkMatch("smart_content_embedding", chunk_idx, score)

        return best

    def _build_result(
        self,
        node: CodeNode,
        chunk_match: ChunkMatch,
    ) -> SearchResult:
        """Build SearchResult from node and chunk match.

        Args:
            node: The matched CodeNode.
            chunk_match: The winning chunk match.

        Returns:
            SearchResult with all fields populated.
        """
        # For semantic matches, use node's full range (like smart_content in regex)
        match_start_line = node.start_line
        match_end_line = node.end_line

        # Use smart_content as snippet if available, otherwise first line of content
        if node.smart_content:
            snippet = node.smart_content[:100]  # Truncate for display
        elif node.content:
            lines = node.content.split("\n")
            snippet = lines[0] if lines else ""
        else:
            snippet = node.node_id

        return SearchResult(
            node_id=node.node_id,
            start_line=node.start_line,
            end_line=node.end_line,
            match_start_line=match_start_line,
            match_end_line=match_end_line,
            smart_content=node.smart_content,
            snippet=snippet,
            score=chunk_match.score,
            match_field=chunk_match.field_name,
            content=node.content,
            matched_lines=list(range(match_start_line, match_end_line + 1)),
        )
