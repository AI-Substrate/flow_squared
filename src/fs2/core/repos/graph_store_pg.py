"""PostgreSQL-backed GraphStore implementation for fs2 server.

Implements the GraphStore ABC query methods against PostgreSQL.
save()/load() are no-ops — the database is always-on.

Per Finding 01: Query methods work directly against DB.
Per DYK #3: Embedding round-trip reconstructs tuple-of-tuples from chunks table.
"""

import logging
from pathlib import Path
from typing import Any

from fs2.core.models.code_node import CodeNode
from fs2.core.models.content_type import ContentType
from fs2.core.repos.graph_store import GraphStore
from fs2.server.database import Database

logger = logging.getLogger(__name__)


class PostgreSQLGraphStore(GraphStore):
    """GraphStore implementation backed by PostgreSQL.

    Read-only query interface — data is ingested via IngestionPipeline.
    save()/load() are no-ops since the DB is always-on.

    Usage::

        store = PostgreSQLGraphStore(db, graph_id="...")
        node = await store.get_node_async("file:src/main.py")
    """

    def __init__(self, db: Database, graph_id: str) -> None:
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
