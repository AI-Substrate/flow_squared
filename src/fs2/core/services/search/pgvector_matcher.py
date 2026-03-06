"""PgvectorSemanticMatcher — SQL-based cosine similarity search.

Queries the embedding_chunks table via pgvector's HNSW index for
sub-100ms semantic search at scale. Unlike the in-memory
SemanticMatcher (which iterates Python lists), this uses SQL
ORDER BY <=> for hardware-accelerated vector search.

Per Finding 02: Server must NOT use get_all_nodes() for search.
Per AC10: Semantic search <100ms at 200K+ nodes.
Per DYK #1: Accepts query_vector (BYO) or uses EmbeddingAdapter for text.
Per DYK #2: Accepts graph_ids list for multi-graph via WHERE IN(...).
"""

import logging
from typing import TYPE_CHECKING

from fs2.core.repos.protocols import ConnectionProvider

if TYPE_CHECKING:
    from fs2.core.adapters.embedding_adapter import EmbeddingAdapter

logger = logging.getLogger(__name__)


class PgvectorSemanticMatcher:
    """SQL-based semantic search using pgvector cosine similarity.

    Takes ConnectionProvider via DI (not server.Database) to respect
    domain boundaries. Optionally takes EmbeddingAdapter for text queries.

    Usage::

        matcher = PgvectorSemanticMatcher(db, embedding_adapter=adapter)
        results, total = await matcher.search(
            query="error handling",
            graph_ids=["uuid1", "uuid2"],
            limit=20,
        )
    """

    def __init__(
        self,
        db: ConnectionProvider,
        embedding_adapter: "EmbeddingAdapter | None" = None,
    ) -> None:
        self._db = db
        self._embedding_adapter = embedding_adapter

    async def search(
        self,
        graph_ids: list[str],
        limit: int = 20,
        offset: int = 0,
        min_similarity: float = 0.25,
        query: str | None = None,
        query_vector: list[float] | None = None,
        include: tuple[str, ...] | None = None,
        exclude: tuple[str, ...] | None = None,
    ) -> tuple[list[dict], int]:
        """Search for semantically similar code nodes.

        Either `query` (text, embedded by adapter) or `query_vector`
        (pre-embedded BYO) must be provided.

        Args:
            graph_ids: List of graph UUIDs to search across.
            limit: Max results to return.
            offset: Results to skip.
            min_similarity: Minimum cosine similarity threshold.
            query: Text query (requires embedding_adapter).
            query_vector: Pre-embedded vector (BYO mode).
            include: Keep only node_ids matching any pattern.
            exclude: Remove node_ids matching any pattern.

        Returns:
            Tuple of (results list, total count).
        """
        if query_vector is None and query is not None:
            if self._embedding_adapter is None:
                raise ValueError(
                    "Text query requires an embedding adapter. "
                    "Either configure one or pass query_vector directly."
                )
            query_vector = await self._embedding_adapter.embed_text(query)

        if query_vector is None:
            raise ValueError("Either query or query_vector must be provided.")

        vec_str = "[" + ",".join(str(float(v)) for v in query_vector) + "]"

        placeholders = ",".join(["%s"] * len(graph_ids))

        # Build include/exclude filters
        filters = ""
        filter_params: list = []
        if include:
            inc_clauses = " OR ".join(["cn.node_id ~ %s"] * len(include))
            filters += f" AND ({inc_clauses})"
            filter_params.extend(include)
        if exclude:
            exc_clauses = " AND ".join(["cn.node_id !~ %s"] * len(exclude))
            filters += f" AND ({exc_clauses})"
            filter_params.extend(exclude)

        async with self._db.connection() as conn:
            # Get total count of matches above threshold
            count_result = await conn.execute(
                f"""SELECT COUNT(DISTINCT (ec.graph_id, ec.node_id))
                FROM embedding_chunks ec
                JOIN code_nodes cn ON ec.graph_id = cn.graph_id AND ec.node_id = cn.node_id
                WHERE ec.graph_id IN ({placeholders})
                AND 1 - (ec.embedding <=> %s::vector) >= %s
                {filters}""",
                [*graph_ids, vec_str, min_similarity, *filter_params],
            )
            total_row = await count_result.fetchone()
            total = total_row[0] if total_row else 0

            # Fetch best chunk match per node using DISTINCT ON
            result = await conn.execute(
                f"""SELECT DISTINCT ON (ec.graph_id, ec.node_id)
                    ec.node_id,
                    cn.category,
                    cn.start_line,
                    cn.end_line,
                    cn.smart_content,
                    cn.content,
                    cn.name,
                    1 - (ec.embedding <=> %s::vector) AS similarity,
                    g.name AS graph_name,
                    ec.embedding_type,
                    ec.chunk_index,
                    ec.chunk_start_line,
                    ec.chunk_end_line
                FROM embedding_chunks ec
                JOIN code_nodes cn ON ec.graph_id = cn.graph_id AND ec.node_id = cn.node_id
                JOIN graphs g ON ec.graph_id = g.id
                WHERE ec.graph_id IN ({placeholders})
                AND 1 - (ec.embedding <=> %s::vector) >= %s
                {filters}
                ORDER BY ec.graph_id, ec.node_id, ec.embedding <=> %s::vector
                """,
                [
                    vec_str,
                    *graph_ids, vec_str, min_similarity, *filter_params,
                    vec_str,
                ],
            )
            all_rows = await result.fetchall()

        # Sort by similarity descending, apply offset/limit
        all_rows.sort(key=lambda r: r[7], reverse=True)
        paged = all_rows[offset:offset + limit]

        results = []
        for row in paged:
            (node_id, category, start, end, smart, content, name,
             sim, gname, emb_type, chunk_idx, csl, cel) = row

            snippet = (smart or content or "")[:50]
            chunk_offset = (csl, cel) if csl is not None else None

            results.append({
                "node_id": node_id,
                "start_line": start,
                "end_line": end,
                "match_start_line": csl or start,
                "match_end_line": cel or end,
                "smart_content": smart,
                "snippet": snippet,
                "score": float(sim),
                "match_field": "embedding",
                "content": content,
                "graph_name": gname,
                "chunk_offset": chunk_offset,
                "embedding_chunk_index": chunk_idx,
            })

        return results, total
