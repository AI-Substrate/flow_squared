"""Ingestion pipeline for fs2 server.

Loads a graph pickle file, validates it with RestrictedUnpickler,
and bulk-inserts all data into PostgreSQL via COPY.

Design decisions:
- D4: COPY-based bulk ingestion (10x faster than batch INSERT)
- D6: JSONB embedding_metadata preserves model info
- D7: Full graph replace on re-upload (DELETE + COPY)
- Synchronous in-process (no background tasks for v1)

This class is designed for TDD: standalone, testable in isolation
without FastAPI or HTTP. Accepts Database via DI.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import networkx as nx

from fs2.core.models.code_node import CodeNode
from fs2.core.repos.pickle_security import RestrictedUnpickler
from fs2.server.database import Database

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Raised when ingestion fails."""


class IngestionResult:
    """Result of an ingestion operation."""

    def __init__(
        self,
        graph_id: str,
        node_count: int,
        edge_count: int,
        chunk_count: int,
        metadata: dict[str, Any],
    ):
        self.graph_id = graph_id
        self.node_count = node_count
        self.edge_count = edge_count
        self.chunk_count = chunk_count
        self.metadata = metadata


def load_pickle(pickle_path: Path) -> tuple[dict[str, Any], nx.DiGraph]:
    """Load and validate a graph pickle file.

    Uses RestrictedUnpickler to prevent arbitrary code execution.

    Args:
        pickle_path: Path to the pickle file.

    Returns:
        Tuple of (metadata dict, networkx DiGraph).

    Raises:
        IngestionError: If file is missing, invalid, or malicious.
    """
    if not pickle_path.exists():
        raise IngestionError(f"Pickle file not found: {pickle_path}")

    try:
        with open(pickle_path, "rb") as f:
            unpickler = RestrictedUnpickler(f)
            data = unpickler.load()
    except Exception as e:
        raise IngestionError(
            f"Failed to unpickle graph file: {pickle_path}. "
            f"File may be corrupted or malicious: {e}"
        ) from e

    if not isinstance(data, tuple) or len(data) != 2:
        raise IngestionError(
            f"Invalid graph file format: expected (metadata, graph) tuple, "
            f"got {type(data).__name__}"
        )

    metadata, graph = data

    if not isinstance(graph, nx.DiGraph):
        raise IngestionError(
            f"Invalid graph type: expected networkx.DiGraph, "
            f"got {type(graph).__name__}"
        )

    if not isinstance(metadata, dict):
        raise IngestionError(
            f"Invalid metadata type: expected dict, got {type(metadata).__name__}"
        )

    return metadata, graph


def extract_nodes(graph: nx.DiGraph) -> list[CodeNode]:
    """Extract all CodeNode objects from a networkx graph."""
    nodes = []
    for node_id in graph.nodes:
        data = graph.nodes[node_id].get("data")
        if isinstance(data, CodeNode):
            nodes.append(data)
    return nodes


def extract_edges(graph: nx.DiGraph) -> list[tuple[str, str]]:
    """Extract all parent→child edges from a networkx graph."""
    return list(graph.edges())


def extract_graph_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Extract server-relevant metadata from graph pickle metadata.

    Returns a dict with keys matching the graphs table columns.
    """
    embedding_metadata = {}
    for key in ["embedding_model", "embedding_dimensions", "chunk_params",
                "embedding_mode", "embedding_batch_size"]:
        if key in metadata:
            embedding_metadata[key] = metadata[key]

    return {
        "format_version": metadata.get("format_version"),
        "embedding_model": metadata.get("embedding_model"),
        "embedding_dimensions": metadata.get("embedding_dimensions"),
        "embedding_metadata": embedding_metadata or None,
        "node_count": metadata.get("node_count"),
        "edge_count": metadata.get("edge_count"),
    }


class IngestionPipeline:
    """Pipeline for ingesting graph pickle files into PostgreSQL.

    Standalone class — testable in isolation without FastAPI or HTTP.

    Usage::

        pipeline = IngestionPipeline(database)
        result = await pipeline.ingest(
            pickle_path=Path("/tmp/graph.pickle"),
            graph_name="my-repo",
            tenant_id="...",
        )
    """

    def __init__(self, db: Database) -> None:
        self._db = db

    async def ingest(
        self,
        pickle_path: Path,
        graph_name: str,
        tenant_id: str,
        description: str | None = None,
        source_url: str | None = None,
    ) -> IngestionResult:
        """Ingest a graph pickle file into PostgreSQL.

        Full pipeline: load → validate → create/replace graph → COPY data → ready.
        Synchronous — blocks until complete.

        Args:
            pickle_path: Path to the validated pickle file on disk.
            graph_name: Name for this graph (unique per tenant).
            tenant_id: Tenant UUID for organizational grouping.
            description: Optional graph description.
            source_url: Optional source repository URL.

        Returns:
            IngestionResult with graph_id, counts, and metadata.

        Raises:
            IngestionError: If any step fails.
        """
        # Step 1: Load and validate pickle
        metadata, graph = load_pickle(pickle_path)
        graph_meta = extract_graph_metadata(metadata)
        nodes = extract_nodes(graph)
        edges = extract_edges(graph)

        logger.info(
            "Loaded pickle: %d nodes, %d edges",
            len(nodes), len(edges),
        )

        async with self._db.connection() as conn:
            # Step 2: Create or replace graph record
            graph_id = await self._upsert_graph(
                conn, graph_name, tenant_id, description, source_url, graph_meta
            )

            # Step 3: Delete existing data (re-upload = full replace)
            await self._delete_graph_data(conn, graph_id)

            # Step 4: Update status to ingesting
            await conn.execute(
                "UPDATE graphs SET status = 'ingesting' WHERE id = %s",
                (graph_id,),
            )

            try:
                # Step 5: COPY bulk insert
                await self._copy_nodes(conn, graph_id, nodes)
                await self._copy_edges(conn, graph_id, edges)
                chunk_count = await self._copy_embeddings(conn, graph_id, nodes)

                # Step 6: Update graph to ready
                await conn.execute(
                    """UPDATE graphs SET
                        status = 'ready',
                        node_count = %s,
                        edge_count = %s,
                        ingested_at = now(),
                        updated_at = now()
                    WHERE id = %s""",
                    (len(nodes), len(edges), graph_id),
                )

                await conn.commit()

            except Exception as e:
                await conn.execute(
                    "UPDATE graphs SET status = 'error', updated_at = now() WHERE id = %s",
                    (graph_id,),
                )
                await conn.commit()
                raise IngestionError(f"Ingestion failed: {e}") from e

        logger.info(
            "Ingestion complete: graph_id=%s, %d nodes, %d edges, %d chunks",
            graph_id, len(nodes), len(edges), chunk_count,
        )

        return IngestionResult(
            graph_id=graph_id,
            node_count=len(nodes),
            edge_count=len(edges),
            chunk_count=chunk_count,
            metadata=graph_meta,
        )

    async def _upsert_graph(
        self,
        conn,
        name: str,
        tenant_id: str,
        description: str | None,
        source_url: str | None,
        meta: dict[str, Any],
    ) -> str:
        """Create or update graph record. Returns graph_id."""
        # Check if graph already exists for this tenant+name
        result = await conn.execute(
            "SELECT id FROM graphs WHERE tenant_id = %s AND name = %s",
            (tenant_id, name),
        )
        row = await result.fetchone()

        if row:
            graph_id = str(row[0])
            await conn.execute(
                """UPDATE graphs SET
                    description = %s,
                    source_url = %s,
                    status = 'pending',
                    format_version = %s,
                    embedding_model = %s,
                    embedding_dimensions = %s,
                    embedding_metadata = %s,
                    updated_at = now()
                WHERE id = %s""",
                (
                    description,
                    source_url,
                    meta.get("format_version"),
                    meta.get("embedding_model"),
                    meta.get("embedding_dimensions"),
                    json.dumps(meta.get("embedding_metadata")) if meta.get("embedding_metadata") else None,
                    graph_id,
                ),
            )
        else:
            graph_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO graphs (id, tenant_id, name, description, source_url,
                    status, format_version, embedding_model, embedding_dimensions,
                    embedding_metadata)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, %s, %s)""",
                (
                    graph_id,
                    tenant_id,
                    name,
                    description,
                    source_url,
                    meta.get("format_version"),
                    meta.get("embedding_model"),
                    meta.get("embedding_dimensions"),
                    json.dumps(meta.get("embedding_metadata")) if meta.get("embedding_metadata") else None,
                ),
            )

        return graph_id

    async def _delete_graph_data(self, conn, graph_id: str) -> None:
        """Delete all data for a graph (re-upload = full replace)."""
        await conn.execute(
            "DELETE FROM embedding_chunks WHERE graph_id = %s", (graph_id,)
        )
        await conn.execute(
            "DELETE FROM node_edges WHERE graph_id = %s", (graph_id,)
        )
        await conn.execute(
            "DELETE FROM code_nodes WHERE graph_id = %s", (graph_id,)
        )

    async def _copy_nodes(self, conn, graph_id: str, nodes: list[CodeNode]) -> None:
        """Bulk insert code_nodes via COPY."""
        async with conn.cursor() as cur, cur.copy(
            """COPY code_nodes (graph_id, node_id, category, ts_kind,
                    content_type, name, qualified_name,
                    start_line, end_line, start_column, end_column,
                    start_byte, end_byte, content, content_hash,
                    signature, language, is_named, field_name,
                    is_error, parent_node_id, truncated, truncated_at_line,
                    smart_content, smart_content_hash, embedding_hash)
                FROM STDIN"""
        ) as copy:
            for node in nodes:
                ct = getattr(node, "content_type", None)
                ct_val = ct.value if ct else "code"
                await copy.write_row((
                    graph_id,
                    node.node_id,
                    node.category,
                    node.ts_kind,
                    ct_val,
                    node.name,
                    node.qualified_name,
                    node.start_line,
                    node.end_line,
                    node.start_column,
                    node.end_column,
                    node.start_byte,
                    node.end_byte,
                    node.content,
                    node.content_hash,
                    node.signature,
                    node.language,
                    node.is_named,
                    node.field_name,
                    getattr(node, "is_error", False),
                    node.parent_node_id,
                    getattr(node, "truncated", False),
                    getattr(node, "truncated_at_line", None),
                    node.smart_content,
                    getattr(node, "smart_content_hash", None),
                    node.embedding_hash,
                ))

    async def _copy_edges(
        self, conn, graph_id: str, edges: list[tuple[str, str]]
    ) -> None:
        """Bulk insert node_edges via COPY."""
        async with conn.cursor() as cur, cur.copy(
            """COPY node_edges (graph_id, parent_node_id, child_node_id)
                FROM STDIN"""
        ) as copy:
            for parent_id, child_id in edges:
                await copy.write_row((graph_id, parent_id, child_id))

    async def _copy_embeddings(
        self, conn, graph_id: str, nodes: list[CodeNode]
    ) -> int:
        """Bulk insert embedding_chunks via COPY. Returns chunk count."""
        chunk_count = 0
        async with conn.cursor() as cur, cur.copy(
            """COPY embedding_chunks (graph_id, node_id,
                    embedding_type, chunk_index, embedding,
                    chunk_start_line, chunk_end_line)
                FROM STDIN"""
        ) as copy:
            for node in nodes:
                if node.embedding:
                    offsets = getattr(node, "embedding_chunk_offsets", None)
                    for i, chunk_vec in enumerate(node.embedding):
                        sl = offsets[i][0] if offsets and i < len(offsets) else None
                        el = offsets[i][1] if offsets and i < len(offsets) else None
                        vec_str = "[" + ",".join(str(float(v)) for v in chunk_vec) + "]"
                        await copy.write_row((
                            graph_id, node.node_id,
                            "content", i, vec_str, sl, el,
                        ))
                        chunk_count += 1

                sc_emb = getattr(node, "smart_content_embedding", None)
                if sc_emb:
                    for i, chunk_vec in enumerate(sc_emb):
                        vec_str = "[" + ",".join(str(float(v)) for v in chunk_vec) + "]"
                        await copy.write_row((
                            graph_id, node.node_id,
                            "smart_content", i, vec_str, None, None,
                        ))
                        chunk_count += 1

        return chunk_count
