# Domain: Server

**Slug**: server
**Type**: infrastructure
**Created**: 2026-03-05
**Created By**: plan-028-server-mode (new domain)
**Status**: active

## Purpose

The HTTP server application that receives graph uploads, stores data in PostgreSQL + pgvector, and serves query requests via REST API. Also hosts the management dashboard for tenant/graph administration. This is the central orchestration point for server mode — it composes services from graph-storage, search, and auth domains into a deployable web application.

## Concepts

| Concept | Entry Point | What It Does |
|---------|-------------|-------------|
| Serve query requests | FastAPI routes | HTTP endpoints for tree, search, get-node, list-graphs |
| Ingest graph uploads | Ingestion pipeline | Pickle → RestrictedUnpickler → COPY to PostgreSQL |
| Manage database connections | Database module | Async connection pool, session factory, RLS context |
| Dashboard administration | HTMX views | Upload graphs, manage sites, view status |

## Boundary

### Owns
- HTTP routing and request/response serialization
- Ingestion pipeline (pickle → staging → validation → COPY import)
- Background job processing for graph imports
- Dashboard UI (Jinja2 + HTMX templates)
- Health and metrics endpoints
- Database connection pool lifecycle
- SQL schema creation and migration
- Docker Compose deployment configuration

### Does NOT Own
- Graph query logic (delegates to graph-storage and search domains)
- Embedding generation (delegates to embedding adapters)
- Authentication/authorization logic (delegates to auth domain)
- CLI argument parsing (belongs to cli-presentation)
- Configuration registry (belongs to configuration domain)

## Contracts (Public Interface)

| Contract | Type | Consumers | Description |
|----------|------|-----------|-------------|
| FastAPI app factory | Function | Docker/uvicorn | `create_app()` → configured FastAPI instance |
| Database session | Context manager | All routes | Async connection with RLS context |

## Dependencies

### This Domain Depends On
- **graph-storage** — PostgreSQLGraphStore for data access
- **search** — SearchService + PgvectorSemanticMatcher for queries
- **configuration** — ServerDatabaseConfig, ServerStorageConfig
- **auth** — AuthService, middleware for request validation

### Domains That Depend On This
- **cli-presentation** — RemoteClient makes HTTP calls to server endpoints

### Ownership Boundary: Schema vs Graph-Storage
The **server** domain owns operational schema bootstrap (`schema.py` — DDL execution, extension creation, index management). The **graph-storage** domain owns query/storage contracts (GraphStore ABC, CodeNode model). Schema changes must stay aligned with graph-storage data contracts to prevent drift.

## Source Location

Primary: `src/fs2/server/`

| File | Role | Notes |
|------|------|-------|
| `src/fs2/server/__init__.py` | Public exports | Exports `create_app` |
| `src/fs2/server/app.py` | App factory | `create_app()` with lifespan |
| `src/fs2/server/database.py` | Connection pool (**contract**) | `Database` class — consumed by other domains via DI |
| `src/fs2/server/schema.py` | Schema DDL | `create_schema()` — 6 tables, 17 indexes |
| `src/fs2/server/ingestion.py` | Ingestion pipeline | `IngestionPipeline` — pickle → COPY to PostgreSQL |
| `src/fs2/server/routes/__init__.py` | Routes package | |
| `src/fs2/server/routes/health.py` | Health endpoint | `GET /health` |
| `src/fs2/server/routes/graphs.py` | Graph management | Upload, list (with status filter), status, delete |
| `src/fs2/server/routes/query.py` | Query endpoints | Tree, search, get-node, multi-graph search |

## History

| Plan | What Changed | Date |
|------|-------------|------|
| 028-server-mode | Domain created | 2026-03-05 |
| 028-server-mode (Phase 1) | Server skeleton implemented: app factory, database pool, schema DDL, health endpoint | 2026-03-05 |
| 028-server-mode (Phase 3) | Ingestion pipeline, graph upload/list/status/delete endpoints, ingestion_jobs table | 2026-03-06 |
| 028-server-mode (Phase 4) | Query API: tree, search (text/regex/semantic/auto), get-node, multi-graph search. PgvectorSemanticMatcher. Enhanced list-graphs with status filter. | 2026-03-06 |
