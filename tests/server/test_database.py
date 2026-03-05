"""Tests for the Database connection pool.

Unit tests use FakeDatabase. Integration tests (marked slow)
use real PostgreSQL via the scratch container.
"""

import pytest

from fs2.config.objects import ServerDatabaseConfig
from fs2.server.database import Database


def test_database_init():
    """Database initializes without connecting."""
    config = ServerDatabaseConfig(host="localhost", port=5432, database="test")
    db = Database(config)
    assert not db.is_connected


def test_conninfo_format():
    """ServerDatabaseConfig.conninfo builds correct connection string."""
    config = ServerDatabaseConfig(
        host="myhost", port=5433, database="mydb", user="myuser", password="secret"
    )
    assert "host=myhost" in config.conninfo
    assert "port=5433" in config.conninfo
    assert "dbname=mydb" in config.conninfo
    assert "user=myuser" in config.conninfo
    assert "password=secret" in config.conninfo


def test_conninfo_no_password():
    """Connection string omits password when empty."""
    config = ServerDatabaseConfig(host="localhost", password="")
    assert "password" not in config.conninfo


async def test_connection_raises_when_not_connected():
    """Calling connection() before connect() raises RuntimeError."""
    config = ServerDatabaseConfig()
    db = Database(config)
    with pytest.raises(RuntimeError, match="not connected"):
        async with db.connection():
            pass


@pytest.mark.slow
async def test_real_pool_lifecycle():
    """Integration: pool connects and disconnects to real PostgreSQL.

    Requires: docker container fs2-pgvector-scratch on port 5433.
    """
    config = ServerDatabaseConfig(
        host="localhost",
        port=5433,
        database="fs2_scratch",
        user="postgres",
        password="scratch",
    )
    db = Database(config)
    await db.connect()
    assert db.is_connected

    async with db.connection() as conn:
        result = await conn.execute("SELECT 1 AS check")
        row = await result.fetchone()
        assert row[0] == 1

    await db.disconnect()
    assert not db.is_connected
