#!/usr/bin/env python3
"""
fs2 Server Mode Prototype: PostgreSQL + pgvector scratch test.

Tests the full pipeline:
  1. Create schema (tables, indexes, pgvector HNSW)
  2. Ingest a real fs2 graph.pickle into PostgreSQL
  3. Run tree queries (parent/children via recursive CTE)
  4. Run text search (trigram ILIKE)
  5. Run semantic search (pgvector cosine similarity)
  6. Run a LIVE semantic search using fs2's own embedding adapter

Usage:
  uv run python3 scripts/scratch/pgvector_prototype.py
"""
import sys
import os
import time
import pickle
import hashlib
from pathlib import Path
from dataclasses import fields as dc_fields

# Add src to path so we can import fs2
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import psycopg
from pgvector.psycopg import register_vector
import numpy as np

# ── Config ──────────────────────────────────────────────────────
DB_HOST = "localhost"
DB_PORT = 5433
DB_NAME = "fs2_scratch"
DB_USER = "postgres"
DB_PASS = "scratch"
GRAPH_PATH = Path(__file__).parent.parent.parent / ".fs2" / "graph.pickle"
TENANT_ID = "00000000-0000-0000-0000-000000000001"
GRAPH_NAME = "fs2-self"  # we're indexing ourselves!


def connect(with_vector=True):
    """Get a psycopg3 connection with pgvector registered."""
    conn = psycopg.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS, autocommit=True
    )
    if with_vector:
        # Ensure extension exists before registering type
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)
    return conn


# ════════════════════════════════════════════════════════════════
# PHASE 1: Schema Creation
# ════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Tenants
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Graphs (sites/repos)
CREATE TABLE IF NOT EXISTS graphs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'pending',
    format_version      TEXT,
    node_count          INT,
    edge_count          INT,
    embedding_model     TEXT,
    embedding_dimensions INT,
    embedding_metadata  JSONB,
    extra_metadata      JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingested_at         TIMESTAMPTZ,
    UNIQUE (tenant_id, name)
);

-- Code Nodes (all CodeNode fields)
CREATE TABLE IF NOT EXISTS code_nodes (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    graph_id        UUID NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL,
    node_id         TEXT NOT NULL,
    category        TEXT NOT NULL,
    ts_kind         TEXT NOT NULL,
    content_type    TEXT NOT NULL DEFAULT 'code',
    name            TEXT,
    qualified_name  TEXT NOT NULL,
    start_line      INT NOT NULL,
    end_line        INT NOT NULL,
    start_column    INT NOT NULL,
    end_column      INT NOT NULL,
    start_byte      INT NOT NULL,
    end_byte        INT NOT NULL,
    content         TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    signature       TEXT,
    language        TEXT NOT NULL,
    is_named        BOOLEAN NOT NULL,
    field_name      TEXT,
    is_error        BOOLEAN NOT NULL DEFAULT false,
    parent_node_id  TEXT,
    truncated       BOOLEAN NOT NULL DEFAULT false,
    truncated_at_line INT,
    smart_content   TEXT,
    smart_content_hash TEXT,
    embedding_hash  TEXT,
    UNIQUE (graph_id, node_id)
);

-- Indexes for code_nodes
CREATE INDEX IF NOT EXISTS idx_nodes_graph_node ON code_nodes(graph_id, node_id);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON code_nodes(graph_id, parent_node_id) WHERE parent_node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_nodes_category ON code_nodes(graph_id, category);
CREATE INDEX IF NOT EXISTS idx_nodes_content_trgm ON code_nodes USING gin (content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_nodes_nodeid_trgm ON code_nodes USING gin (node_id gin_trgm_ops);

-- Node Edges (parent→child)
CREATE TABLE IF NOT EXISTS node_edges (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    graph_id        UUID NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL,
    parent_node_id  TEXT NOT NULL,
    child_node_id   TEXT NOT NULL,
    UNIQUE (graph_id, parent_node_id, child_node_id)
);
CREATE INDEX IF NOT EXISTS idx_edges_parent ON node_edges(graph_id, parent_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_child ON node_edges(graph_id, child_node_id);

-- Embedding Chunks (pgvector)
CREATE TABLE IF NOT EXISTS embedding_chunks (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    graph_id        UUID NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
    tenant_id       UUID NOT NULL,
    node_id         TEXT NOT NULL,
    embedding_type  TEXT NOT NULL,
    chunk_index     INT NOT NULL,
    embedding       vector(1024) NOT NULL,
    chunk_start_line INT,
    chunk_end_line   INT,
    UNIQUE (graph_id, node_id, embedding_type, chunk_index)
);
CREATE INDEX IF NOT EXISTS idx_embeddings_graph ON embedding_chunks(graph_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_node ON embedding_chunks(graph_id, node_id);
"""

# HNSW index created separately (expensive, do after data load)
HNSW_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw ON embedding_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
"""


def create_schema(conn):
    """Create all tables and indexes."""
    print("━" * 60)
    print("PHASE 1: Creating schema...")
    conn.execute(SCHEMA_SQL)
    print("  ✅ Tables and indexes created")

    # Insert test tenant
    conn.execute("""
        INSERT INTO tenants (id, name, slug)
        VALUES (%s, 'Test Tenant', 'test')
        ON CONFLICT (id) DO NOTHING
    """, (TENANT_ID,))
    print(f"  ✅ Tenant created: {TENANT_ID}")


# ════════════════════════════════════════════════════════════════
# PHASE 2: Ingest Graph Pickle
# ════════════════════════════════════════════════════════════════

def load_pickle(path: Path):
    """Load graph.pickle using fs2's RestrictedUnpickler for safety."""
    from fs2.core.repos.graph_store_impl import RestrictedUnpickler

    with open(path, "rb") as f:
        metadata, nx_graph = RestrictedUnpickler(f).load()
    return metadata, nx_graph


def ingest_graph(conn, metadata, nx_graph):
    """Ingest a NetworkX graph into PostgreSQL."""
    print("━" * 60)
    print("PHASE 2: Ingesting graph pickle...")
    t0 = time.time()

    # Extract all CodeNode objects
    nodes = []
    for n in nx_graph.nodes:
        node_data = nx_graph.nodes[n].get("data")
        if node_data is not None:
            nodes.append(node_data)

    edges = list(nx_graph.edges)

    print(f"  📊 Metadata: format_version={metadata.get('format_version')}")
    print(f"     nodes={len(nodes)}, edges={len(edges)}")
    print(f"     embedding_model={metadata.get('embedding_model', 'N/A')}")
    print(f"     embedding_dimensions={metadata.get('embedding_dimensions', 'N/A')}")

    # Create graph record
    import json
    known_keys = {"format_version", "created_at", "node_count", "edge_count",
                  "embedding_model", "embedding_dimensions", "chunk_params"}
    extra = {k: str(v) for k, v in metadata.items() if k not in known_keys}

    conn.execute("""
        INSERT INTO graphs (tenant_id, name, description, status,
                           format_version, node_count, edge_count,
                           embedding_model, embedding_dimensions,
                           embedding_metadata, extra_metadata)
        VALUES (%s, %s, %s, 'ingesting', %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, name) DO UPDATE SET
            status = 'ingesting',
            format_version = EXCLUDED.format_version,
            node_count = EXCLUDED.node_count,
            edge_count = EXCLUDED.edge_count,
            embedding_model = EXCLUDED.embedding_model,
            embedding_dimensions = EXCLUDED.embedding_dimensions,
            embedding_metadata = EXCLUDED.embedding_metadata,
            extra_metadata = EXCLUDED.extra_metadata
    """, (
        TENANT_ID, GRAPH_NAME, "fs2 indexing itself",
        metadata.get("format_version"),
        len(nodes), len(edges),
        metadata.get("embedding_model"),
        metadata.get("embedding_dimensions"),
        json.dumps({
            "model": metadata.get("embedding_model"),
            "dimensions": metadata.get("embedding_dimensions"),
            "chunk_params": metadata.get("chunk_params"),
        }),
        json.dumps(extra) if extra else None,
    ))

    # Get graph_id
    row = conn.execute(
        "SELECT id FROM graphs WHERE tenant_id = %s AND name = %s",
        (TENANT_ID, GRAPH_NAME)
    ).fetchone()
    graph_id = str(row[0])
    print(f"  📝 Graph ID: {graph_id}")

    # Clear existing data for this graph (re-upload = full replace)
    conn.execute("DELETE FROM embedding_chunks WHERE graph_id = %s", (graph_id,))
    conn.execute("DELETE FROM node_edges WHERE graph_id = %s", (graph_id,))
    conn.execute("DELETE FROM code_nodes WHERE graph_id = %s", (graph_id,))

    # ── Bulk insert code_nodes ──
    t1 = time.time()
    with conn.cursor() as cur:
        with cur.copy("""
            COPY code_nodes (graph_id, tenant_id, node_id, category, ts_kind,
                content_type, name, qualified_name,
                start_line, end_line, start_column, end_column,
                start_byte, end_byte, content, content_hash,
                signature, language, is_named, field_name,
                is_error, parent_node_id, truncated, truncated_at_line,
                smart_content, smart_content_hash, embedding_hash)
            FROM STDIN
        """) as copy:
            for node in nodes:
                ct = getattr(node, 'content_type', None)
                ct_val = ct.value if ct else 'code'
                copy.write_row((
                    graph_id, TENANT_ID, node.node_id, node.category, node.ts_kind,
                    ct_val, node.name, node.qualified_name,
                    node.start_line, node.end_line, node.start_column, node.end_column,
                    node.start_byte, node.end_byte, node.content, node.content_hash,
                    node.signature, node.language, node.is_named, node.field_name,
                    getattr(node, 'is_error', False),
                    node.parent_node_id,
                    getattr(node, 'truncated', False),
                    getattr(node, 'truncated_at_line', None),
                    node.smart_content,
                    getattr(node, 'smart_content_hash', None),
                    node.embedding_hash,
                ))
    t2 = time.time()
    print(f"  ✅ Inserted {len(nodes)} code_nodes via COPY in {t2-t1:.2f}s")

    # ── Bulk insert node_edges ──
    with conn.cursor() as cur:
        with cur.copy("""
            COPY node_edges (graph_id, tenant_id, parent_node_id, child_node_id)
            FROM STDIN
        """) as copy:
            for parent_id, child_id in edges:
                copy.write_row((graph_id, TENANT_ID, parent_id, child_id))
    t3 = time.time()
    print(f"  ✅ Inserted {len(edges)} edges via COPY in {t3-t2:.2f}s")

    # ── Bulk insert embedding_chunks ──
    chunk_count = 0
    with conn.cursor() as cur:
        with cur.copy("""
            COPY embedding_chunks (graph_id, tenant_id, node_id,
                embedding_type, chunk_index, embedding,
                chunk_start_line, chunk_end_line)
            FROM STDIN
        """) as copy:
            for node in nodes:
                if node.embedding:
                    offsets = getattr(node, 'embedding_chunk_offsets', None)
                    for i, chunk_vec in enumerate(node.embedding):
                        sl = offsets[i][0] if offsets and i < len(offsets) else None
                        el = offsets[i][1] if offsets and i < len(offsets) else None
                        vec_str = "[" + ",".join(str(float(v)) for v in chunk_vec) + "]"
                        copy.write_row((
                            graph_id, TENANT_ID, node.node_id,
                            "content", i, vec_str, sl, el
                        ))
                        chunk_count += 1

                sc_emb = getattr(node, 'smart_content_embedding', None)
                if sc_emb:
                    for i, chunk_vec in enumerate(sc_emb):
                        vec_str = "[" + ",".join(str(float(v)) for v in chunk_vec) + "]"
                        copy.write_row((
                            graph_id, TENANT_ID, node.node_id,
                            "smart_content", i, vec_str, None, None
                        ))
                        chunk_count += 1
    t4 = time.time()
    print(f"  ✅ Inserted {chunk_count} embedding chunks via COPY in {t4-t3:.2f}s")

    # Update graph status
    conn.execute("""
        UPDATE graphs SET status = 'ready', ingested_at = now()
        WHERE id = %s
    """, (graph_id,))

    total = time.time() - t0
    print(f"  🎉 Total ingestion: {total:.2f}s")
    print(f"     ({len(nodes)} nodes, {len(edges)} edges, {chunk_count} embedding chunks)")

    return graph_id


def build_hnsw_index(conn):
    """Build the HNSW vector index (can be slow for large datasets)."""
    print("\n  🔨 Building HNSW index...")
    t0 = time.time()
    conn.execute(HNSW_INDEX_SQL)
    t1 = time.time()
    print(f"  ✅ HNSW index built in {t1-t0:.2f}s")


# ════════════════════════════════════════════════════════════════
# PHASE 3: Query Tests
# ════════════════════════════════════════════════════════════════

def test_tree_queries(conn, graph_id):
    """Test hierarchical tree traversal queries."""
    print("━" * 60)
    print("PHASE 3a: Tree Traversal Queries")

    # Find a file node with children
    t0 = time.time()
    row = conn.execute("""
        SELECT node_id, name, category
        FROM code_nodes
        WHERE graph_id = %s AND category = 'file'
        ORDER BY node_id
        LIMIT 1
    """, (graph_id,)).fetchone()
    t1 = time.time()

    if not row:
        print("  ⚠️ No file nodes found")
        return

    file_node_id = row[0]
    print(f"\n  📁 Root file: {file_node_id}")
    print(f"     Query time: {(t1-t0)*1000:.1f}ms")

    # Get direct children
    t0 = time.time()
    children = conn.execute("""
        SELECT cn.node_id, cn.name, cn.category, cn.start_line, cn.end_line
        FROM code_nodes cn
        JOIN node_edges ne ON ne.child_node_id = cn.node_id AND ne.graph_id = cn.graph_id
        WHERE ne.graph_id = %s AND ne.parent_node_id = %s
        ORDER BY cn.start_line
    """, (graph_id, file_node_id)).fetchall()
    t1 = time.time()

    print(f"\n  👶 Direct children ({len(children)}): [{(t1-t0)*1000:.1f}ms]")
    for c in children[:8]:
        print(f"     {c[2]:12s} {c[1] or '(anon)':30s} L{c[3]}-{c[4]}")
    if len(children) > 8:
        print(f"     ... and {len(children)-8} more")

    # Recursive tree expansion (3 levels deep)
    t0 = time.time()
    tree = conn.execute("""
        WITH RECURSIVE tree AS (
            SELECT cn.node_id, cn.name, cn.category, cn.start_line, cn.end_line, 0 AS depth
            FROM code_nodes cn
            WHERE cn.graph_id = %s AND cn.node_id = %s

            UNION ALL

            SELECT cn.node_id, cn.name, cn.category, cn.start_line, cn.end_line, tree.depth + 1
            FROM code_nodes cn
            JOIN node_edges ne ON ne.child_node_id = cn.node_id AND ne.graph_id = cn.graph_id
            JOIN tree ON tree.node_id = ne.parent_node_id
            WHERE cn.graph_id = %s AND tree.depth < 3
        )
        SELECT * FROM tree ORDER BY depth, start_line
    """, (graph_id, file_node_id, graph_id)).fetchall()
    t1 = time.time()

    print(f"\n  🌳 Recursive tree (3 levels, {len(tree)} nodes): [{(t1-t0)*1000:.1f}ms]")
    for t_node in tree[:15]:
        indent = "  " * t_node[5]
        print(f"     {indent}{t_node[2]:12s} {t_node[1] or '(anon)'}")
    if len(tree) > 15:
        print(f"     ... and {len(tree)-15} more nodes")


def test_text_search(conn, graph_id):
    """Test text/regex search with trigram indexes."""
    print("\n" + "━" * 60)
    print("PHASE 3b: Text Search (trigram ILIKE)")

    # Text search for "GraphStore"
    t0 = time.time()
    results = conn.execute("""
        SELECT node_id, category, name, start_line, end_line,
               LEFT(smart_content, 100) as snippet
        FROM code_nodes
        WHERE graph_id = %s
          AND (node_id ILIKE %s OR content ILIKE %s OR smart_content ILIKE %s)
        LIMIT 10
    """, (graph_id, "%GraphStore%", "%GraphStore%", "%GraphStore%")).fetchall()
    t1 = time.time()

    print(f"\n  🔍 Search: 'GraphStore' → {len(results)} results [{(t1-t0)*1000:.1f}ms]")
    for r in results[:5]:
        snippet = (r[5] or "")[:80].replace("\n", " ")
        print(f"     {r[1]:12s} {r[0][:60]}")
        if snippet:
            print(f"               {snippet}...")

    # Regex search
    t0 = time.time()
    results = conn.execute("""
        SELECT node_id, category, name
        FROM code_nodes
        WHERE graph_id = %s AND content ~ %s
        LIMIT 5
    """, (graph_id, r"class\s+\w+Service")).fetchall()
    t1 = time.time()

    print(f"\n  🔍 Regex: 'class\\s+\\w+Service' → {len(results)} results [{(t1-t0)*1000:.1f}ms]")
    for r in results:
        print(f"     {r[1]:12s} {r[0][:60]}")


def test_semantic_search(conn, graph_id):
    """Test pgvector semantic search using a node's own embedding as query."""
    print("\n" + "━" * 60)
    print("PHASE 3c: Semantic Search (pgvector cosine similarity)")

    # Grab a random embedding to use as a query vector
    row = conn.execute("""
        SELECT node_id, embedding, embedding_type
        FROM embedding_chunks
        WHERE graph_id = %s AND embedding_type = 'smart_content'
        LIMIT 1
    """, (graph_id,)).fetchone()

    if not row:
        print("  ⚠️ No embeddings found in database")
        return

    query_node_id = row[0]
    query_vec = row[1]  # pgvector returns numpy array
    print(f"  📌 Using embedding from: {query_node_id}")
    print(f"     Vector dims: {len(query_vec)}, type: {type(query_vec)}")

    # Find nearest neighbors
    t0 = time.time()
    results = conn.execute("""
        SELECT
            ec.node_id,
            ec.embedding_type,
            ec.chunk_index,
            1 - (ec.embedding <=> %s::vector) AS similarity
        FROM embedding_chunks ec
        WHERE ec.graph_id = %s
          AND 1 - (ec.embedding <=> %s::vector) >= 0.25
        ORDER BY ec.embedding <=> %s::vector
        LIMIT 10
    """, (query_vec, graph_id, query_vec, query_vec)).fetchall()
    t1 = time.time()

    print(f"\n  🧠 Top {len(results)} semantic matches [{(t1-t0)*1000:.1f}ms]:")
    for r in results[:10]:
        print(f"     {r[3]:.4f}  {r[1]:14s} chunk[{r[2]}]  {r[0][:55]}")

    # Now get the smart_content for the top results (join enrichment)
    top_node_ids = [r[0] for r in results[:5]]
    if top_node_ids:
        enriched = conn.execute("""
            SELECT node_id, category, name, LEFT(smart_content, 120) as snippet
            FROM code_nodes
            WHERE graph_id = %s AND node_id = ANY(%s)
        """, (graph_id, top_node_ids)).fetchall()

        print(f"\n  📝 Enriched results:")
        for e in enriched:
            snippet = (e[3] or "").replace("\n", " ")[:100]
            print(f"     {e[1]:12s} {e[2] or '(anon)':25s} {snippet}")


# ════════════════════════════════════════════════════════════════
# PHASE 4: Live Embedding Search (using fs2's adapter)
# ════════════════════════════════════════════════════════════════

def test_live_semantic_search(conn, graph_id):
    """Use fs2's real embedding adapter to embed a query and search."""
    print("\n" + "━" * 60)
    print("PHASE 4: LIVE Semantic Search (real embedding via fs2 adapter)")

    try:
        import asyncio
        from fs2.config.service import FS2ConfigurationService
        from fs2.core.adapters.embedding_adapter import create_embedding_adapter_from_config

        config_svc = FS2ConfigurationService()
        adapter = create_embedding_adapter_from_config(config_svc)
        if not adapter:
            print("  ⚠️ Embedding adapter not configured — skipping live search")
            return

        print(f"  🔌 Adapter: {adapter.provider_name}")

        # Embed a natural language query
        query_text = "error handling and exception translation"
        print(f"\n  💬 Query: \"{query_text}\"")

        t0 = time.time()
        query_vec = asyncio.run(adapter.embed_text(query_text))
        t1 = time.time()
        print(f"  ⚡ Embedding generated in {(t1-t0)*1000:.0f}ms ({len(query_vec)} dims)")

        # Search pgvector
        t0 = time.time()
        results = conn.execute("""
            SELECT
                ec.node_id,
                ec.embedding_type,
                1 - (ec.embedding <=> %s::vector) AS similarity,
                cn.category,
                cn.name,
                LEFT(cn.smart_content, 150) as snippet
            FROM embedding_chunks ec
            JOIN code_nodes cn ON cn.graph_id = ec.graph_id AND cn.node_id = ec.node_id
            WHERE ec.graph_id = %s
              AND 1 - (ec.embedding <=> %s::vector) >= 0.25
            ORDER BY ec.embedding <=> %s::vector
            LIMIT 10
        """, (query_vec, graph_id, query_vec, query_vec)).fetchall()
        t1 = time.time()

        print(f"\n  🎯 Results for \"{query_text}\" [{(t1-t0)*1000:.1f}ms]:")
        for r in results:
            snippet = (r[5] or "").replace("\n", " ")[:90]
            print(f"     {r[2]:.4f}  {r[3]:12s} {r[4] or '(anon)':25s}")
            if snippet:
                print(f"              {snippet}")
        print()

        # Second query
        query_text2 = "how to configure embedding models"
        print(f"  💬 Query: \"{query_text2}\"")
        t0 = time.time()
        query_vec2 = asyncio.run(adapter.embed_text(query_text2))
        t1 = time.time()
        print(f"  ⚡ Embedding: {(t1-t0)*1000:.0f}ms")

        t0 = time.time()
        results2 = conn.execute("""
            SELECT
                ec.node_id,
                ec.embedding_type,
                1 - (ec.embedding <=> %s::vector) AS similarity,
                cn.category,
                cn.name,
                LEFT(cn.smart_content, 150) as snippet
            FROM embedding_chunks ec
            JOIN code_nodes cn ON cn.graph_id = ec.graph_id AND cn.node_id = ec.node_id
            WHERE ec.graph_id = %s
              AND 1 - (ec.embedding <=> %s::vector) >= 0.25
            ORDER BY ec.embedding <=> %s::vector
            LIMIT 10
        """, (query_vec2, graph_id, query_vec2, query_vec2)).fetchall()
        t1 = time.time()

        print(f"\n  🎯 Results [{(t1-t0)*1000:.1f}ms]:")
        for r in results2:
            snippet = (r[5] or "").replace("\n", " ")[:90]
            print(f"     {r[2]:.4f}  {r[3]:12s} {r[4] or '(anon)':25s}")
            if snippet:
                print(f"              {snippet}")

    except Exception as e:
        print(f"  ⚠️ Live search failed (expected if no API key configured): {e}")
        print("     Skipping live search — static vector search above still validated pgvector works.")


# ════════════════════════════════════════════════════════════════
# PHASE 5: Stats Summary
# ════════════════════════════════════════════════════════════════

def print_stats(conn, graph_id):
    """Print database statistics."""
    print("\n" + "━" * 60)
    print("PHASE 5: Database Statistics")

    stats = {}
    for table in ["code_nodes", "node_edges", "embedding_chunks"]:
        row = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE graph_id = %s", (graph_id,)
        ).fetchone()
        stats[table] = row[0]

    # Table sizes
    sizes = conn.execute("""
        SELECT
            relname AS table,
            pg_size_pretty(pg_total_relation_size(relid)) AS total_size
        FROM pg_catalog.pg_statio_user_tables
        WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size(relid) DESC
    """).fetchall()

    # Embedding dimension check
    dim_row = conn.execute("""
        SELECT vector_dims(embedding) FROM embedding_chunks LIMIT 1
    """).fetchone()

    print(f"\n  📊 Row counts:")
    for table, count in stats.items():
        print(f"     {table:25s} {count:>8,}")

    print(f"\n  💾 Table sizes:")
    for s in sizes:
        print(f"     {s[0]:25s} {s[1]:>10s}")

    if dim_row:
        print(f"\n  📐 Embedding dimensions: {dim_row[0]}")

    # Graph metadata
    graph = conn.execute(
        "SELECT embedding_model, embedding_dimensions, embedding_metadata FROM graphs WHERE id = %s",
        (graph_id,)
    ).fetchone()
    if graph:
        print(f"\n  🏷️ Embedding model: {graph[0]}")
        print(f"     Dimensions: {graph[1]}")
        import json
        meta = graph[2] if graph[2] else {}
        if isinstance(meta, str):
            meta = json.loads(meta)
        if meta.get("chunk_params"):
            print(f"     Chunk params: {json.dumps(meta['chunk_params'], indent=6)}")


# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  fs2 Server Mode — PostgreSQL + pgvector Prototype")
    print("=" * 60)
    print(f"  DB: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"  Graph: {GRAPH_PATH}")
    print(f"  Graph exists: {GRAPH_PATH.exists()}")
    print(f"  Graph size: {GRAPH_PATH.stat().st_size / 1024 / 1024:.1f} MB")
    print()

    conn = connect()

    # Phase 1: Schema
    create_schema(conn)

    # Phase 2: Ingest
    print("\n  Loading pickle (this may take a moment for 128MB)...")
    t0 = time.time()
    metadata, nx_graph = load_pickle(GRAPH_PATH)
    t1 = time.time()
    print(f"  📦 Pickle loaded in {t1-t0:.2f}s")

    graph_id = ingest_graph(conn, metadata, nx_graph)

    # Build HNSW index
    build_hnsw_index(conn)

    # Phase 3: Queries
    test_tree_queries(conn, graph_id)
    test_text_search(conn, graph_id)
    test_semantic_search(conn, graph_id)

    # Phase 4: Live embedding search
    test_live_semantic_search(conn, graph_id)

    # Phase 5: Stats
    print_stats(conn, graph_id)

    print("\n" + "=" * 60)
    print("  ✅ PROTOTYPE COMPLETE")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
