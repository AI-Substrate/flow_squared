"""FastAPI application factory for fs2 server.

Usage::

    uvicorn fs2.server.app:create_app --factory
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fs2.config.objects import ServerDatabaseConfig
from fs2.server.dashboard import router as dashboard_router
from fs2.server.database import Database
from fs2.server.middleware import AccessLogMiddleware
from fs2.server.routes.graphs import router as graphs_router
from fs2.server.routes.health import router as health_router
from fs2.server.routes.query import router as query_router
from fs2.server.schema import create_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage server startup and shutdown.

    Startup: connect pool → create schema → ready.
    Shutdown: close pool.
    """
    db: Database = app.state.db
    await db.connect()

    async with db.connection() as conn:
        await create_schema(conn)

    yield

    await db.disconnect()


def create_app(
    db_config: ServerDatabaseConfig | None = None,
    database: Database | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        db_config: Database config. If None, uses defaults.
        database: Pre-built Database instance (for testing).
                  If None, creates one from db_config.
    """
    if db_config is None:
        db_config = ServerDatabaseConfig()

    app = FastAPI(
        title="fs2 Server",
        description="Code intelligence graph server powered by PostgreSQL + pgvector",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)

    if database is not None:
        app.state.db = database
    else:
        app.state.db = Database(db_config)

    app.include_router(health_router)
    app.include_router(graphs_router)
    app.include_router(query_router)
    app.include_router(dashboard_router)

    return app
