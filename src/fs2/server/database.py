"""Async PostgreSQL connection pool for fs2 server.

This module provides the Database class — a server-domain **contract**
that wraps psycopg3's AsyncConnectionPool. Other domains (graph-storage,
search) receive Database via dependency injection for DB access.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psycopg
from pgvector.psycopg import register_vector_async
from psycopg_pool import AsyncConnectionPool

from fs2.config.objects import ServerDatabaseConfig


async def _configure_connection(conn: psycopg.AsyncConnection) -> None:
    """Configure each new connection in the pool.

    Registers pgvector types so vector columns work transparently.
    Called by the pool for every new connection it creates.
    """
    await register_vector_async(conn)


class Database:
    """Async PostgreSQL connection pool manager.

    This is a server-domain **contract** — designed for consumption
    by other domains (graph-storage, search) via dependency injection.

    Usage::

        db = Database(config)
        await db.connect()

        async with db.connection() as conn:
            result = await conn.execute("SELECT 1")

        await db.disconnect()
    """

    def __init__(self, config: ServerDatabaseConfig) -> None:
        self._config = config
        self._pool: AsyncConnectionPool | None = None

    async def connect(self) -> None:
        """Create and open the connection pool."""
        self._pool = AsyncConnectionPool(
            conninfo=self._config.conninfo,
            min_size=self._config.pool_min,
            max_size=self._config.pool_max,
            timeout=self._config.pool_timeout,
            configure=_configure_connection,
            open=False,
        )
        await self._pool.open()

    async def disconnect(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        """Get a connection from the pool.

        Raises:
            RuntimeError: If the pool is not connected.
        """
        if self._pool is None:
            raise RuntimeError(
                "Database pool not connected. Call connect() first."
            )
        async with self._pool.connection() as conn:
            yield conn

    @property
    def is_connected(self) -> bool:
        """Whether the pool is open and available."""
        return self._pool is not None
