"""PostgreSQL schema creation for fs2 server.

DDL adapted from Workshop 001 (locked schema). Creates all tables,
indexes, and extensions needed for graph storage + vector search.

Design decisions (from prototype validation):
- D1: PostgreSQL + pgvector as sole database
- D2: vector(1024) for text-embedding-3-small
- D3: Separate embedding_chunks table
- D5: Trigram GIN indexes for text/regex search
- No RLS — auth model is "valid API key = full access"
"""

import psycopg

SCHEMA_SQL = """
-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Tenants (organizational grouping)
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    max_graphs  INT NOT NULL DEFAULT 50,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Graphs (one per uploaded repository)
CREATE TABLE IF NOT EXISTS graphs (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT,
    source_url  TEXT,
    status      TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'ingesting', 'ready', 'error')),
    format_version  TEXT,
    node_count      INT,
    edge_count      INT,
    embedding_model      TEXT,
    embedding_dimensions INT,
    embedding_metadata   JSONB,
    extra_metadata  JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ingested_at TIMESTAMPTZ,
    UNIQUE (tenant_id, name)
);

-- Code nodes (all indexed code elements)
CREATE TABLE IF NOT EXISTS code_nodes (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    graph_id        UUID NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
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
    truncated           BOOLEAN NOT NULL DEFAULT false,
    truncated_at_line   INT,
    smart_content       TEXT,
    smart_content_hash  TEXT,
    embedding_hash  TEXT,
    UNIQUE (graph_id, node_id)
);

-- Node edges (parent → child relationships)
CREATE TABLE IF NOT EXISTS node_edges (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    graph_id        UUID NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
    parent_node_id  TEXT NOT NULL,
    child_node_id   TEXT NOT NULL,
    UNIQUE (graph_id, parent_node_id, child_node_id)
);

-- Embedding chunks (vector storage for semantic search)
CREATE TABLE IF NOT EXISTS embedding_chunks (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    graph_id        UUID NOT NULL REFERENCES graphs(id) ON DELETE CASCADE,
    node_id         TEXT NOT NULL,
    embedding_type  TEXT NOT NULL,
    chunk_index     INT NOT NULL,
    embedding       vector(1024) NOT NULL,
    chunk_start_line INT,
    chunk_end_line   INT,
    UNIQUE (graph_id, node_id, embedding_type, chunk_index)
);

-- Indexes: graphs
CREATE INDEX IF NOT EXISTS idx_graphs_tenant ON graphs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_graphs_status ON graphs(status);

-- Indexes: code_nodes
CREATE INDEX IF NOT EXISTS idx_nodes_graph_node ON code_nodes(graph_id, node_id);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON code_nodes(graph_id, parent_node_id)
    WHERE parent_node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_nodes_category ON code_nodes(graph_id, category);
CREATE INDEX IF NOT EXISTS idx_nodes_content_trgm ON code_nodes
    USING gin (content gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_nodes_nodeid_trgm ON code_nodes
    USING gin (node_id gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_nodes_smart_trgm ON code_nodes
    USING gin (smart_content gin_trgm_ops)
    WHERE smart_content IS NOT NULL;

-- Indexes: node_edges
CREATE INDEX IF NOT EXISTS idx_edges_parent ON node_edges(graph_id, parent_node_id);
CREATE INDEX IF NOT EXISTS idx_edges_child ON node_edges(graph_id, child_node_id);

-- Indexes: embedding_chunks
CREATE INDEX IF NOT EXISTS idx_embeddings_graph ON embedding_chunks(graph_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_node ON embedding_chunks(graph_id, node_id);

-- HNSW vector index for cosine similarity search
CREATE INDEX IF NOT EXISTS idx_embeddings_hnsw ON embedding_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 128);
"""


async def create_schema(conn: psycopg.AsyncConnection) -> None:
    """Create all tables, indexes, and extensions.

    Idempotent — safe to call on every startup (uses IF NOT EXISTS).
    """
    await conn.execute(SCHEMA_SQL)  # type: ignore[arg-type]
    await conn.commit()
