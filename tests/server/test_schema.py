"""Tests for schema creation.

Integration tests (marked slow) use real PostgreSQL to verify DDL.
Unit tests verify the SQL string content.
"""

import pytest

from fs2.server.schema import SCHEMA_SQL, create_schema


def test_schema_sql_has_extensions():
    """Schema SQL includes required extensions."""
    assert "CREATE EXTENSION IF NOT EXISTS vector" in SCHEMA_SQL
    assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in SCHEMA_SQL
    assert 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"' in SCHEMA_SQL


def test_schema_sql_has_all_tables():
    """Schema SQL creates all 5 required tables."""
    for table in ["tenants", "graphs", "code_nodes", "node_edges", "embedding_chunks"]:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in SCHEMA_SQL


def test_schema_sql_has_hnsw_index():
    """Schema SQL includes HNSW vector index."""
    assert "USING hnsw" in SCHEMA_SQL
    assert "vector_cosine_ops" in SCHEMA_SQL


def test_schema_sql_has_trigram_indexes():
    """Schema SQL includes trigram GIN indexes for text search."""
    assert "gin_trgm_ops" in SCHEMA_SQL


def test_schema_sql_no_rls():
    """Schema SQL does NOT include Row-Level Security (removed by DYK decision)."""
    assert "ENABLE ROW LEVEL SECURITY" not in SCHEMA_SQL
    assert "CREATE POLICY" not in SCHEMA_SQL


def test_schema_sql_no_tenant_id_on_data_tables():
    """Data tables (code_nodes, node_edges, embedding_chunks) don't have tenant_id FK."""
    # tenant_id only appears on graphs table (organizational grouping)
    # Split SQL into per-table blocks and check data tables
    lines = SCHEMA_SQL.split("\n")
    in_code_nodes = False
    in_node_edges = False
    in_embedding_chunks = False

    for line in lines:
        if "CREATE TABLE IF NOT EXISTS code_nodes" in line:
            in_code_nodes = True
        elif "CREATE TABLE IF NOT EXISTS node_edges" in line:
            in_node_edges = True
            in_code_nodes = False
        elif "CREATE TABLE IF NOT EXISTS embedding_chunks" in line:
            in_embedding_chunks = True
            in_node_edges = False
        elif line.strip().startswith("CREATE") and "TABLE" not in line:
            in_embedding_chunks = False

        if (in_code_nodes or in_node_edges or in_embedding_chunks) and "tenant_id" in line:
            pytest.fail(f"Found tenant_id in data table: {line.strip()}")


@pytest.mark.slow
async def test_schema_creation_on_real_db():
    """Integration: schema creates all tables on real PostgreSQL.

    Requires: docker container fs2-pgvector-scratch on port 5433.
    """
    from fs2.config.objects import ServerDatabaseConfig
    from fs2.server.database import Database

    config = ServerDatabaseConfig(
        host="localhost",
        port=5433,
        database="fs2_scratch",
        user="postgres",
        password="scratch",
    )
    db = Database(config)
    await db.connect()
    try:
        async with db.connection() as conn:
            await create_schema(conn)

            # Verify all tables exist
            result = await conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            tables = {row[0] for row in await result.fetchall()}
            for expected in ["tenants", "graphs", "code_nodes", "node_edges", "embedding_chunks"]:
                assert expected in tables, f"Table {expected} not found"

        # Idempotency: running again should not fail
        async with db.connection() as conn:
            await create_schema(conn)
    finally:
        await db.disconnect()
