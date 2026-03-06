"""PostgreSQL-backed GraphStore implementation for fs2 server.

Implements the GraphStore ABC query methods against PostgreSQL.
save()/load() are no-ops — the database is always-on.

Per Finding 01: Query methods work directly against DB.
Per DYK #3: Embedding round-trip reconstructs tuple-of-tuples from chunks table.
Per Phase 4 DYK #3: Tree folder hierarchy uses Python path splitting, not SQL CTE.

Depends on ConnectionProvider protocol (not server.Database directly)
to avoid graph-storage → server reverse dependency.
"""

import fnmatch
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType
from fs2.core.repos.graph_store import GraphStore

logger = logging.getLogger(__name__)


@runtime_checkable
class ConnectionProvider(Protocol):
    """Protocol for async database connection access.

    Decouples PostgreSQLGraphStore from the server.Database class,
    preventing a graph-storage → server reverse dependency.
    """

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator: ...


class PostgreSQLGraphStore(GraphStore):
    """GraphStore implementation backed by PostgreSQL.

    Read-only query interface — data is ingested via IngestionPipeline.
    save()/load() are no-ops since the DB is always-on.

    Usage::

        store = PostgreSQLGraphStore(db, graph_id="...")
        node = await store.get_node_async("file:src/main.py")
    """

    def __init__(self, db: ConnectionProvider, graph_id: str) -> None:
        self._db = db
        self._graph_id = graph_id

    def _row_to_code_node(self, row: tuple, embeddings: dict | None = None) -> CodeNode:
        """Reconstruct a CodeNode from a database row.

        Column order must match the SELECT in query methods.
        """
        node_id = row[0]

        # Reconstruct embedding tuple-of-tuples from chunks if available
        embedding = None
        smart_content_embedding = None
        embedding_chunk_offsets = None

        if embeddings and node_id in embeddings:
            node_emb = embeddings[node_id]
            if "content" in node_emb:
                chunks = sorted(node_emb["content"], key=lambda x: x[0])
                embedding = tuple(tuple(c[1]) for c in chunks)
                offsets = [(c[2], c[3]) for c in chunks if c[2] is not None]
                if offsets:
                    embedding_chunk_offsets = tuple(
                        (int(s), int(e)) for s, e in offsets
                    )
            if "smart_content" in node_emb:
                chunks = sorted(node_emb["smart_content"], key=lambda x: x[0])
                smart_content_embedding = tuple(tuple(c[1]) for c in chunks)

        ct_str = row[3]
        try:
            content_type = ContentType(ct_str)
        except (ValueError, KeyError):
            content_type = ContentType.CODE

        return CodeNode(
            node_id=row[0],
            category=row[1],
            ts_kind=row[2],
            content_type=content_type,
            name=row[4],
            qualified_name=row[5],
            start_line=row[6],
            end_line=row[7],
            start_column=row[8],
            end_column=row[9],
            start_byte=row[10],
            end_byte=row[11],
            content=row[12],
            content_hash=row[13],
            signature=row[14],
            language=row[15],
            is_named=row[16],
            field_name=row[17],
            is_error=row[18],
            parent_node_id=row[19],
            truncated=row[20],
            truncated_at_line=row[21],
            smart_content=row[22],
            smart_content_hash=row[23],
            embedding_hash=row[24],
            embedding=embedding,
            smart_content_embedding=smart_content_embedding,
            embedding_chunk_offsets=embedding_chunk_offsets,
        )

    _NODE_COLUMNS = """node_id, category, ts_kind, content_type, name,
        qualified_name, start_line, end_line, start_column, end_column,
        start_byte, end_byte, content, content_hash, signature,
        language, is_named, field_name, is_error, parent_node_id,
        truncated, truncated_at_line, smart_content, smart_content_hash,
        embedding_hash"""

    async def get_node_async(self, node_id: str) -> CodeNode | None:
        """Async version of get_node with embedding reconstruction."""
        async with self._db.connection() as conn:
            result = await conn.execute(
                f"SELECT {self._NODE_COLUMNS} FROM code_nodes "
                "WHERE graph_id = %s AND node_id = %s",
                (self._graph_id, node_id),
            )
            row = await result.fetchone()
            if not row:
                return None

            # Fetch embeddings for this node
            emb_result = await conn.execute(
                """SELECT node_id, embedding_type, chunk_index, embedding,
                    chunk_start_line, chunk_end_line
                FROM embedding_chunks
                WHERE graph_id = %s AND node_id = %s
                ORDER BY embedding_type, chunk_index""",
                (self._graph_id, node_id),
            )
            emb_rows = await emb_result.fetchall()
            embeddings = self._group_embeddings(emb_rows)

            return self._row_to_code_node(row, embeddings)

    async def get_children_async(self, node_id: str) -> list[CodeNode]:
        """Async version of get_children."""
        async with self._db.connection() as conn:
            result = await conn.execute(
                f"""SELECT {self._NODE_COLUMNS} FROM code_nodes cn
                JOIN node_edges ne ON cn.graph_id = ne.graph_id AND cn.node_id = ne.child_node_id
                WHERE ne.graph_id = %s AND ne.parent_node_id = %s""",
                (self._graph_id, node_id),
            )
            rows = await result.fetchall()
            return [self._row_to_code_node(row) for row in rows]

    async def get_parent_async(self, node_id: str) -> CodeNode | None:
        """Async version of get_parent."""
        async with self._db.connection() as conn:
            result = await conn.execute(
                f"""SELECT {self._NODE_COLUMNS} FROM code_nodes cn
                JOIN node_edges ne ON cn.graph_id = ne.graph_id AND cn.node_id = ne.parent_node_id
                WHERE ne.graph_id = %s AND ne.child_node_id = %s
                LIMIT 1""",
                (self._graph_id, node_id),
            )
            row = await result.fetchone()
            if not row:
                return None
            return self._row_to_code_node(row)

    async def get_all_nodes_async(self) -> list[CodeNode]:
        """Async version of get_all_nodes."""
        async with self._db.connection() as conn:
            result = await conn.execute(
                f"SELECT {self._NODE_COLUMNS} FROM code_nodes "
                "WHERE graph_id = %s ORDER BY node_id",
                (self._graph_id,),
            )
            rows = await result.fetchall()
            return [self._row_to_code_node(row) for row in rows]

    def _group_embeddings(self, emb_rows: list) -> dict:
        """Group embedding rows by node_id and embedding_type."""
        embeddings: dict = {}
        for row in emb_rows:
            node_id, emb_type, chunk_idx, vec, sl, el = row
            if node_id not in embeddings:
                embeddings[node_id] = {}
            if emb_type not in embeddings[node_id]:
                embeddings[node_id][emb_type] = []
            vec_list = list(vec) if vec is not None else []
            embeddings[node_id][emb_type].append((chunk_idx, vec_list, sl, el))
        return embeddings

    # ── Phase 4: Tree + Search query methods ──

    async def get_filtered_nodes_async(
        self, pattern: str
    ) -> list[CodeNode]:
        """Fetch nodes filtered by pattern using SQL.

        Pattern modes (same as TreeService._detect_input_mode):
        - "." → all nodes (file-level for folder tree)
        - Contains ":" → exact node_id match
        - Contains "/" → folder prefix filter (node_id LIKE 'file:{prefix}%')
        - Contains glob chars → glob match (fetches all, filters in Python)
        - Otherwise → substring match via ILIKE
        """
        async with self._db.connection() as conn:
            if pattern == ".":
                result = await conn.execute(
                    f"SELECT {self._NODE_COLUMNS} FROM code_nodes "
                    "WHERE graph_id = %s ORDER BY node_id",
                    (self._graph_id,),
                )
            elif ":" in pattern:
                # Exact node_id match
                result = await conn.execute(
                    f"SELECT {self._NODE_COLUMNS} FROM code_nodes "
                    "WHERE graph_id = %s AND node_id = %s",
                    (self._graph_id, pattern),
                )
            elif "/" in pattern:
                # Folder prefix filter
                prefix = pattern if pattern.endswith("/") else pattern + "/"
                like_pattern = f"%{prefix}%"
                result = await conn.execute(
                    f"SELECT {self._NODE_COLUMNS} FROM code_nodes "
                    "WHERE graph_id = %s AND node_id LIKE %s ORDER BY node_id",
                    (self._graph_id, like_pattern),
                )
            elif any(c in pattern for c in "*?[]"):
                # Glob pattern — fetch all, filter in Python
                result = await conn.execute(
                    f"SELECT {self._NODE_COLUMNS} FROM code_nodes "
                    "WHERE graph_id = %s ORDER BY node_id",
                    (self._graph_id,),
                )
                rows = await result.fetchall()
                return [
                    self._row_to_code_node(r) for r in rows
                    if fnmatch.fnmatch(r[0], f"*{pattern}*")
                ]
            else:
                # Substring match via ILIKE
                like_pattern = f"%{pattern}%"
                result = await conn.execute(
                    f"SELECT {self._NODE_COLUMNS} FROM code_nodes "
                    "WHERE graph_id = %s AND node_id ILIKE %s ORDER BY node_id",
                    (self._graph_id, like_pattern),
                )

            rows = await result.fetchall()
            return [self._row_to_code_node(r) for r in rows]

    async def get_children_count_async(self, node_id: str) -> int:
        """Get count of children for a node."""
        async with self._db.connection() as conn:
            result = await conn.execute(
                "SELECT COUNT(*) FROM node_edges "
                "WHERE graph_id = %s AND parent_node_id = %s",
                (self._graph_id, node_id),
            )
            row = await result.fetchone()
            return row[0] if row else 0

    async def has_embeddings_async(self) -> bool:
        """Check if this graph has any embedding chunks."""
        async with self._db.connection() as conn:
            result = await conn.execute(
                "SELECT EXISTS(SELECT 1 FROM embedding_chunks "
                "WHERE graph_id = %s LIMIT 1)",
                (self._graph_id,),
            )
            row = await result.fetchone()
            return row[0] if row else False

    async def search_text_async(
        self,
        pattern: str,
        limit: int = 20,
        offset: int = 0,
        include: tuple[str, ...] | None = None,
        exclude: tuple[str, ...] | None = None,
        graph_ids: list[str] | None = None,
    ) -> tuple[list[dict], int]:
        """Text search via SQL ILIKE with trigram indexes.

        Returns (results, total_count) where results are
        SearchResult-compatible dicts.
        """
        return await self._search_sql(
            pattern, "ilike", limit, offset, include, exclude, graph_ids
        )

    async def search_regex_async(
        self,
        pattern: str,
        limit: int = 20,
        offset: int = 0,
        include: tuple[str, ...] | None = None,
        exclude: tuple[str, ...] | None = None,
        graph_ids: list[str] | None = None,
    ) -> tuple[list[dict], int]:
        """Regex search via SQL ~ operator with trigram indexes.

        Returns (results, total_count) where results are
        SearchResult-compatible dicts.
        """
        return await self._search_sql(
            pattern, "regex", limit, offset, include, exclude, graph_ids
        )

    async def _search_sql(
        self,
        pattern: str,
        mode: str,
        limit: int,
        offset: int,
        include: tuple[str, ...] | None,
        exclude: tuple[str, ...] | None,
        graph_ids: list[str] | None,
    ) -> tuple[list[dict], int]:
        """Internal: run text or regex search via SQL.

        Uses ILIKE for text, ~ for regex. Scores heuristically:
        node_id match → 0.9, smart_content → 0.7, content → 0.5.
        """
        ids = graph_ids or [self._graph_id]
        placeholders = ",".join(["%s"] * len(ids))

        if mode == "ilike":
            op = "ILIKE"
            sql_pattern = f"%{pattern}%"
        else:
            op = "~"
            sql_pattern = pattern

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

        # Score calculation: prioritize node_id > smart_content > content
        score_expr = f"""
            CASE
                WHEN cn.node_id {op} %s THEN 0.9
                WHEN cn.smart_content IS NOT NULL AND cn.smart_content {op} %s THEN 0.7
                ELSE 0.5
            END
        """

        base_where = f"""
            cn.graph_id IN ({placeholders})
            AND (cn.node_id {op} %s OR cn.content {op} %s
                 OR (cn.smart_content IS NOT NULL AND cn.smart_content {op} %s))
            {filters}
        """

        params_where = [*ids, sql_pattern, sql_pattern, sql_pattern, *filter_params]
        params_score = [sql_pattern, sql_pattern]

        # Count total
        async with self._db.connection() as conn:
            count_result = await conn.execute(
                f"SELECT COUNT(*) FROM code_nodes cn WHERE {base_where}",
                params_where,
            )
            total_row = await count_result.fetchone()
            total = total_row[0] if total_row else 0

            # Fetch page
            result = await conn.execute(
                f"""SELECT cn.node_id, cn.category, cn.start_line, cn.end_line,
                    cn.smart_content, cn.content, cn.name,
                    {score_expr} AS score,
                    g.name AS graph_name
                FROM code_nodes cn
                JOIN graphs g ON cn.graph_id = g.id
                WHERE {base_where}
                ORDER BY score DESC, cn.node_id
                LIMIT %s OFFSET %s""",
                [*params_score, *params_where, limit, offset],
            )
            rows = await result.fetchall()

        results = []
        for row in rows:
            node_id, category, start, end, smart, content, name, score, gname = row
            snippet = (smart or content or "")[:50]
            # Determine which field matched
            pat_lower = pattern.lower() if mode == "ilike" else pattern
            if mode == "ilike":
                if pat_lower in (node_id or "").lower():
                    match_field = "node_id"
                elif smart and pat_lower in smart.lower():
                    match_field = "smart_content"
                else:
                    match_field = "content"
            else:
                import re as _re
                try:
                    if _re.search(pattern, node_id or ""):
                        match_field = "node_id"
                    elif smart and _re.search(pattern, smart):
                        match_field = "smart_content"
                    else:
                        match_field = "content"
                except _re.error:
                    match_field = "content"

            results.append({
                "node_id": node_id,
                "start_line": start,
                "end_line": end,
                "match_start_line": start,
                "match_end_line": end,
                "smart_content": smart,
                "snippet": snippet,
                "score": float(score),
                "match_field": match_field,
                "content": content,
                "graph_name": gname,
            })

        return results, total

    # ── Sync ABC methods (no-ops or sync wrappers) ──

    def add_node(self, node: CodeNode) -> None:
        """No-op — data is ingested via IngestionPipeline."""
        raise NotImplementedError("Use IngestionPipeline for data writes")

    def add_edge(self, parent_id: str, child_id: str) -> None:
        """No-op — data is ingested via IngestionPipeline."""
        raise NotImplementedError("Use IngestionPipeline for data writes")

    def get_node(self, node_id: str) -> CodeNode | None:
        """Sync stub — use get_node_async() in async contexts."""
        raise NotImplementedError("Use get_node_async() in async server context")

    def get_children(self, node_id: str) -> list[CodeNode]:
        """Sync stub — use get_children_async() in async contexts."""
        raise NotImplementedError("Use get_children_async() in async server context")

    def get_parent(self, node_id: str) -> CodeNode | None:
        """Sync stub — use get_parent_async() in async contexts."""
        raise NotImplementedError("Use get_parent_async() in async server context")

    def get_all_nodes(self) -> list[CodeNode]:
        """Sync stub — use get_all_nodes_async() in async contexts."""
        raise NotImplementedError("Use get_all_nodes_async() in async server context")

    def save(self, path: Path) -> None:
        """No-op — PostgreSQL is always-on."""

    def load(self, path: Path) -> None:
        """No-op — PostgreSQL is always-on."""

    def clear(self) -> None:
        """No-op — use IngestionPipeline for data management."""
        raise NotImplementedError("Use IngestionPipeline or DELETE for data management")

    def set_metadata(self, metadata: dict[str, Any]) -> None:
        """No-op — metadata stored in graphs table."""

    def get_metadata(self) -> dict[str, Any]:
        """Sync stub — metadata available via graph queries."""
        raise NotImplementedError("Use async graph queries for metadata")
