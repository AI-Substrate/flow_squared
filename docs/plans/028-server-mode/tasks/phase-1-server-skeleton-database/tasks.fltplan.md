# Flight Plan: Phase 1 — Server Skeleton + Database

**Plan**: [../../server-mode-plan.md](../../server-mode-plan.md)
**Phase**: Phase 1: Server Skeleton + Database
**Generated**: 2026-03-05
**Status**: Landed ✅

---

## Departure → Destination

**Where we are**: fs2 is a local-only CLI tool with no server component. All code intelligence data lives in pickle files on disk. The PostgreSQL + pgvector schema has been designed (Workshop 001) and validated against real data (Workshop 002, 5,231 nodes, sub-5ms queries). The server domain is defined in docs but no source code exists yet.

**Where we're going**: A developer can run `docker compose up` to start a FastAPI + PostgreSQL stack, hit `GET /health` and see `{"status":"ok","db":"connected","graphs":0}`, confirming the full server skeleton is operational. The database has all 5 tables, 20+ indexes, pgvector + trigram extensions, and RLS policies ready for Phase 2's auth layer.

---

## Domain Context

### Domains We're Changing

| Domain | What Changes | Key Files |
|--------|-------------|-----------|
| server | NEW — entire package created from scratch | `src/fs2/server/app.py`, `database.py`, `schema.py`, `routes/health.py` |
| configuration | Add 2 config models to existing registry | `src/fs2/config/objects.py` |

### Domains We Depend On (no changes)

| Domain | What We Consume | Contract |
|--------|----------------|----------|
| configuration | `ConfigurationService.require(T)` | `ConfigurationService` ABC |
| configuration | `FakeConfigurationService(configs...)` | Test double |

---

## Flight Status

<!-- Updated by /plan-6-v2: pending → active → done. Use blocked for problems/input needed. -->

```mermaid
stateDiagram-v2
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef active fill:#FFC107,stroke:#FFA000,color:#000
    classDef done fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    state "1: Package skeleton" as S1
    state "2: Config models" as S2
    state "3: App factory" as S3
    state "4: Connection pool" as S4
    state "5: Schema DDL" as S5
    state "6: Health endpoint" as S6
    state "7: Docker Compose" as S7
    state "8: Domain verify" as S8
    state "9: Tests" as S9

    [*] --> S1
    [*] --> S2
    S1 --> S3
    S2 --> S4
    S1 --> S4
    S1 --> S5
    S3 --> S6
    S4 --> S6
    S5 --> S6
    S4 --> S7
    S6 --> S9
    S8 --> [*]
    S9 --> [*]

    class S1,S2,S3,S4,S5,S6,S7,S8,S9 done
```

**Legend**: grey = pending | yellow = active | red = blocked/needs input | green = done

---

## Stages

<!-- Updated by /plan-6-v2 during implementation: [ ] → [~] → [x] -->

- [x] **Stage 1: Foundation** — Create server package skeleton + config models (`__init__.py`, `objects.py`)
- [x] **Stage 2: Core Infrastructure** — App factory + connection pool + schema DDL (`app.py`, `database.py`, `schema.py`)
- [x] **Stage 3: First Endpoint** — Health check route proving end-to-end stack (`routes/health.py`)
- [x] **Stage 4: Deployment** — Docker Compose for local dev (`docker-compose.yml`)
- [x] **Stage 5: Validation** — Tests + domain artifact verification (`tests/server/`)

---

## Architecture: Before & After

```mermaid
flowchart LR
    classDef existing fill:#E8F5E9,stroke:#4CAF50,color:#000
    classDef changed fill:#FFF3E0,stroke:#FF9800,color:#000
    classDef new fill:#E3F2FD,stroke:#2196F3,color:#000

    subgraph Before["Before Phase 1"]
        B_CLI[CLI]:::existing
        B_Config[Configuration]:::existing
        B_Graph[GraphStore\nNetworkX + Pickle]:::existing
        B_Search[SearchService]:::existing

        B_CLI --> B_Config
        B_CLI --> B_Graph
        B_CLI --> B_Search
    end

    subgraph After["After Phase 1"]
        A_CLI[CLI]:::existing
        A_Config[Configuration\n+ ServerDatabaseConfig\n+ ServerStorageConfig]:::changed
        A_Graph[GraphStore\nNetworkX + Pickle]:::existing
        A_Search[SearchService]:::existing
        A_Server["🌐 Server\nFastAPI app factory\nasync pool + schema\n/health endpoint"]:::new
        A_Docker["🐳 Docker Compose\nFastAPI + PostgreSQL"]:::new

        A_CLI --> A_Config
        A_CLI --> A_Graph
        A_CLI --> A_Search
        A_Server --> A_Config
        A_Docker -.-> A_Server
    end
```

**Legend**: existing (green, unchanged) | changed (orange, modified) | new (blue, created)

---

## Acceptance Criteria

- [x] AC22: Docker Compose stack (`docker compose up`) starts FastAPI + PostgreSQL cleanly
- [x] AC23: Health endpoint (`GET /health`) returns server status, database connectivity, and graph count

## Goals & Non-Goals

**Goals**:
- FastAPI app factory starts with `uvicorn fs2.server.app:create_app --factory`
- PostgreSQL schema with all 5 tables + 20 indexes created on fresh database
- Async connection pool manages lifecycle (startup/shutdown)
- Health endpoint proves end-to-end connectivity
- Docker Compose provides one-command dev environment
- Config models integrate cleanly with existing registry

**Non-Goals**:
- No authentication or tenant isolation (Phase 2)
- No graph upload or ingestion (Phase 3)
- No query endpoints (Phase 4)
- No dashboard UI (Phase 6)

---

## Checklist

- [x] T001: Create `src/fs2/server/` package skeleton
- [x] T002: Add ServerDatabaseConfig + ServerStorageConfig to config registry
- [x] T003: Create FastAPI app factory with lifespan
- [x] T004: Implement async connection pool (psycopg3)
- [x] T005: Implement schema DDL from Workshop 001
- [x] T006: Create health endpoint
- [x] T007: Create Docker Compose (FastAPI + PostgreSQL)
- [x] T008: Verify domain artifacts (already created)
- [x] T009: Create test suite
