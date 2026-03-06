# fs2 Server Mode — Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-03-05
**Spec**: [server-mode-spec.md](server-mode-spec.md)
**Status**: DRAFT
**Mode**: Full

## Summary

fs2's current local-only architecture (pickle files + in-memory NetworkX) cannot serve teams or scale to hundreds of repositories. This plan adds a server mode: a FastAPI application backed by PostgreSQL + pgvector that hosts pre-scanned graphs for remote queries. Clients use the same `fs2` CLI commands with a `--remote` flag, and AI agents use the same MCP tools transparently. A management dashboard handles graph uploads, tenant management, and API key provisioning. The approach is validated by a working prototype (5,231 nodes, sub-5ms queries) and 7 locked architectural decisions.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| graph-storage | extracted ✅ | **modify** | Add PostgreSQL-backed GraphStore; extend GraphService for DB catalog |
| search | extracted ✅ | **modify** | Add PgvectorSemanticMatcher; server-side text/regex via SQL |
| configuration | extracted ✅ | **modify** | Add ServerDatabaseConfig, RemotesConfig models |
| cli-presentation | informal | **modify** | Add `--remote` flag; transparent local/remote switching |
| indexing | informal | **consume** | Client-side `fs2 scan` unchanged — produces pickle for upload |
| embedding | informal | **consume** | Server uses existing EmbeddingAdapter ABC to embed search queries |
| server | **NEW** | **create** | FastAPI app, ingestion pipeline, REST API, dashboard |
| auth | **NEW** | **create** | API keys, tenants, RLS, request-scoped tenant context |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/server/__init__.py` | server | internal | Server package init |
| `src/fs2/server/app.py` | server | contract | FastAPI application factory |
| `src/fs2/server/routes/graphs.py` | server | internal | Graph CRUD + upload endpoints |
| `src/fs2/server/routes/query.py` | server | internal | Tree, search, get-node query endpoints |
| `src/fs2/server/routes/health.py` | server | internal | Health + metrics endpoints |
| `src/fs2/server/ingestion.py` | server | internal | Pickle → PostgreSQL pipeline |
| `src/fs2/server/database.py` | server | contract | Connection pool, session factory |
| `src/fs2/server/schema.py` | server | internal | SQL schema creation + migration |
| `src/fs2/server/routes/__init__.py` | server | internal | Routes package init |
| `src/fs2/server/dashboard/__init__.py` | server | internal | HTMX dashboard views |
| `src/fs2/server/dashboard/templates/` | server | internal | Jinja2 templates |
| `src/fs2/auth/__init__.py` | auth | internal | Auth package init |
| `src/fs2/auth/models.py` | auth | contract | Tenant, APIKey Pydantic models |
| `src/fs2/auth/service.py` | auth | contract | AuthService: key validation, tenant resolution |
| `src/fs2/auth/middleware.py` | auth | contract | FastAPI middleware for API key validation |
| `src/fs2/auth/fake.py` | auth | internal | FakeAuthService test double |
| `src/fs2/core/repos/graph_store_pg.py` | graph-storage | contract | PostgreSQLGraphStore implementation |
| `src/fs2/core/repos/graph_store_pg_fake.py` | graph-storage | internal | Fake for PostgreSQL store |
| `src/fs2/core/services/search/pgvector_matcher.py` | search | internal | PgvectorSemanticMatcher |
| `src/fs2/config/objects.py` | configuration | contract | Add ServerDatabaseConfig, RemotesConfig, RemoteServer |
| `src/fs2/cli/utils.py` | cli-presentation | cross-domain | Add resolve_remote_client() (does NOT modify resolve_graph_from_context) |
| `src/fs2/cli/main.py` | cli-presentation | cross-domain | Add --remote global flag + FS2_REMOTE env var |
| `src/fs2/cli/remote_client.py` | cli-presentation | internal | RemoteClient + MultiRemoteClient: async HTTP clients (NOT GraphStore ABC) |
| `src/fs2/cli/list_remotes.py` | cli-presentation | internal | list-remotes command: shows configured remotes |
| `docker-compose.yml` | server | internal | Deployment stack |
| `docs/domains/server/domain.md` | server | internal | Domain definition |
| `docs/domains/auth/domain.md` | auth | internal | Domain definition |
| `docs/domains/registry.md` | — | cross-domain | Update registry with new domains |
| `docs/domains/domain-map.md` | — | cross-domain | Update map with new domains |
| `Dockerfile` | server | internal | Server container runtime |
| `tests/server/test_health.py` | server | internal | Phase 1 server health test coverage |
| `tests/server/test_database.py` | server | internal | Phase 1 DB connection tests |
| `tests/server/test_schema.py` | server | internal | Phase 1 schema DDL tests |
| `tests/server/__init__.py` | server | internal | Test package init |
| `src/fs2/core/repos/pickle_security.py` | graph-storage | contract | RestrictedUnpickler public contract |
| `src/fs2/core/repos/graph_store_pg.py` | graph-storage | contract | PostgreSQLGraphStore + ConnectionProvider protocol |
| `src/fs2/server/ingestion.py` | server | internal | Pickle → PostgreSQL ingestion pipeline |
| `src/fs2/server/routes/graphs.py` | server | internal | Graph upload, list, status, delete endpoints |
| `tests/server/test_ingestion.py` | server | internal | Ingestion pipeline tests |
| `tests/server/test_graph_upload.py` | server | internal | Upload endpoint tests |
| `tests/server/test_graph_store_pg.py` | graph-storage | internal | PG store round-trip parity tests |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **GraphStore.save()/load() are file-oriented** — PostgreSQL backend can't implement `save(Path)`. | Server-side: create `PostgreSQLGraphStore` that implements query methods (6/10) directly; save/load become no-ops (persistence is always-on in DB). Ingestion pipeline writes to DB directly, not via save(). No ABC change needed. |
| 02 | High | **SearchService loads ALL nodes into memory** — `get_all_nodes()` at 500K nodes = ~2.5GB. Not viable for server. | Create `PgvectorSemanticMatcher` that queries DB directly. For text/regex, use SQL `ILIKE`/`~` on `code_nodes` table. SearchService gets a routing mode. |
| 03 | High | **Async driver: psycopg3 AsyncConnection** — pgvector-python supports psycopg3 (sync+async). asyncpg does NOT have pgvector adapter. | Use `psycopg3.AsyncConnection` + `psycopg_pool.AsyncConnectionPool`. Validate under concurrent load in Phase 1. |
| 04 | High | **RLS + connection pooling** — `SET app.current_tenant_id` leaks between requests if not scoped. | Use per-request transaction scope: acquire → SET → execute → COMMIT/ROLLBACK. FastAPI middleware wraps every request. Test with concurrent multi-tenant requests. |
| 05 | High | **500MB upload → OOM risk** — Naive FastAPI UploadFile buffers in RAM. | Stream upload to temp file on disk. Ingestion runs as background job from temp file. Return 202 Accepted + job ID. |
| 06 | High | **Configuration registry supports new types cleanly** — `YAML_CONFIG_TYPES` is a flat list with unique `__config_path__`. | Add `ServerDatabaseConfig` ("server.database") and `RemotesConfig` ("remotes") to registry. Zero collision risk. |
| 07 | High | **CLI resolve_graph_from_context() is single injection point** — Already abstracts all graph resolution. | CLI commands check `resolve_remote_client()` first and branch early. `resolve_graph_from_context()` is NOT modified — remote mode uses a separate `RemoteClient` (not a GraphStore). |

## Phases

### Phase 1: Server Skeleton + Database

**Objective**: Establish the server application with PostgreSQL schema, connection pooling, and basic health endpoint — the foundation everything else builds on.
**Domain**: server (NEW), configuration (modify)
**Delivers**:
- FastAPI application skeleton with async startup/shutdown
- PostgreSQL schema (validated in prototype: tenants, graphs, code_nodes, node_edges, embedding_chunks)
- Async connection pool (psycopg3 AsyncConnectionPool)
- Health check endpoint (`/health`)
- ServerDatabaseConfig + ServerStorageConfig Pydantic models
- Docker Compose for development (FastAPI + PostgreSQL + pgvector)
- `docs/domains/server/domain.md` created
- Domain registry + map updated

**Depends on**: None
**Key risks**: Async psycopg3 pooling under concurrent load is unvalidated (Finding 03). Mitigate by load-testing pool early.
**CS**: CS-3 (medium)

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 1.1 | Create `src/fs2/server/` package with FastAPI app factory | server | `uvicorn fs2.server.app:create_app --factory` starts cleanly | |
| 1.2 | Add ServerDatabaseConfig, ServerStorageConfig to config registry | configuration | `config.require(ServerDatabaseConfig)` returns valid config from YAML | Per finding 06 |
| 1.3 | Implement database.py: async pool, session factory, startup/shutdown | server | Pool creates connections, health check queries `SELECT 1` | Per finding 03 |
| 1.4 | Implement schema.py: CREATE TABLE/INDEX/EXTENSION (from workshop 001) | server | All 5 tables + 20 indexes created on fresh database | Workshop 001 locked |
| 1.5 | Health endpoint: `/health` returns DB status + graph count | server | `curl /health` returns `{"status": "ok", "db": "connected", "graphs": 0}` | AC23 |
| 1.6 | Docker Compose: FastAPI + PostgreSQL (pgvector) | server | `docker compose up` starts both services, health passes | AC22 |
| 1.7 | Create `docs/domains/server/domain.md` + update registry + map | server | Domain registered, map shows new node | |
| 1.8 | Tests: health endpoint, DB connection, schema creation | server | `pytest tests/server/` passes | Fakes for DB where needed |

### Acceptance Criteria
- [ ] AC22: Docker Compose stack starts cleanly
- [ ] AC23: Health endpoint returns status, DB connectivity, graph count

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| psycopg3 async pool instability | Low | High | Load test with 50+ concurrent connections in 1.8 |

---

### Phase 2: Auth + Multi-Tenancy

**Objective**: Establish tenant isolation with API key authentication and Row-Level Security — security before data.
**Domain**: auth (NEW), server (modify)
**Delivers**:
- Tenant and APIKey Pydantic models
- AuthService: API key validation, tenant resolution
- FastAPI middleware: extract key → validate → SET tenant_id → RLS enforcement
- FakeAuthService test double
- RLS policies on all data tables
- Key generation endpoint (admin-only)
- `docs/domains/auth/domain.md` created

**Depends on**: Phase 1
**Key risks**: RLS + connection pooling leak risk (Finding 04). Must test concurrent multi-tenant requests.
**CS**: CS-3 (medium)

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 2.1 | Create `src/fs2/auth/` package with models (Tenant, APIKey) | auth | Pydantic models validate, hash key correctly | |
| 2.2 | Implement AuthService: key validation, tenant lookup | auth | Valid key → tenant_id; invalid → raises AuthError | AC14, AC17 |
| 2.3 | Implement auth middleware: extract Bearer token, set RLS context | auth | Per-request `SET app.current_tenant_id` in transaction scope | Per finding 04 |
| 2.4 | Enable RLS on all data tables + create policies | server | `SELECT` from code_nodes without tenant context → 0 rows | AC15 |
| 2.5 | API key scoping: read-only vs read-write | auth | Read-only key can query but not upload/delete | AC16 |
| 2.6 | Create FakeAuthService + tests | auth | Concurrent multi-tenant test: tenant A can't see tenant B data | |
| 2.7 | Create `docs/domains/auth/domain.md` + update registry + map | auth | Domain registered | |

### Acceptance Criteria
- [ ] AC14: API requests require valid API key
- [ ] AC15: RLS prevents cross-tenant data access
- [ ] AC16: API keys scoped to read-only or read-write
- [ ] AC17: Invalid keys return HTTP 401 with actionable message

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| RLS context leaks between pooled connections | Medium | Critical | Transaction-scoped SET + explicit RESET in middleware |

---

### Phase 3: Ingestion Pipeline + Graph Upload

**Objective**: Enable graph upload through REST API (consumed by dashboard later) and background ingestion into PostgreSQL.
**Domain**: server (modify), graph-storage (modify)
**Delivers**:
- Upload endpoint: POST graph pickle file → staging → background job
- Ingestion pipeline: RestrictedUnpickler → COPY bulk insert (code_nodes, edges, embedding_chunks)
- Graph status lifecycle: pending → ingesting → ready → error
- Re-upload (full replace)
- Ingestion jobs table + status tracking
- PostgreSQLGraphStore (query methods only — no save/load for server side)

**Depends on**: Phase 2
**Key risks**: 500MB pickle upload OOM (Finding 05). Large HNSW rebuild blocks queries.
**CS**: CS-4 (large)

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 3.1 | Upload endpoint: stream pickle to temp file, return 202 + job ID | server | 128MB pickle uploads without OOM, returns job_id | Per finding 05, AC4 |
| 3.2 | Ingestion worker: load pickle → validate → COPY to PostgreSQL | server | 5K-node graph ingested in <30s including HNSW | AC1, AC3, Workshop D4 |
| 3.3 | RestrictedUnpickler validation on upload | server | Malicious pickle rejected with clear error | AC4 |
| 3.4 | Graph metadata extraction + embedding model preservation | server | embedding_model, dimensions, chunk_params in graphs table | AC3, Workshop D6 |
| 3.5 | Re-upload: DELETE existing + re-INSERT | server | Same graph name replaces old data completely | AC2, Workshop D7 |
| 3.6 | Ingestion job status tracking (pending/running/completed/failed) | server | Job status queryable via API | AC5 |
| 3.7 | PostgreSQLGraphStore: get_node, get_children, get_parent, get_all_nodes | graph-storage | Query methods return same results as NetworkXGraphStore | Per finding 01 |
| 3.8 | Tests: upload round-trip, ingestion, re-upload, validation rejection | server | End-to-end: upload pickle → query node → matches original | |

### Acceptance Criteria
- [ ] AC1: Upload → queryable within 30s for 5K-node graph
- [ ] AC2: Re-upload replaces completely
- [ ] AC3: Metadata preserved
- [ ] AC4: RestrictedUnpickler rejects malicious pickles
- [ ] AC5: Dashboard shows ingestion progress

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| 500MB upload causes OOM | Medium | High | Stream to temp file, ingest from disk |
| HNSW rebuild blocks concurrent queries | Low | Medium | pgvector updates index incrementally on INSERT |

---

### Phase 4: Server Query API

**Objective**: Expose tree, search, get-node, and list-graphs as REST endpoints, including pgvector semantic search.
**Domain**: server (modify), search (modify), graph-storage (modify)
**Delivers**:
- REST endpoints: `/api/v1/graphs/{name}/tree`, `/api/v1/graphs/{name}/search`, `/api/v1/graphs/{name}/nodes/{id}`, `/api/v1/graphs`
- Multi-graph search: search across 1, N, or all graphs
- PgvectorSemanticMatcher: SQL-based cosine search (not brute-force)
- Server-side text/regex search via SQL ILIKE/regex
- Embedding model compatibility validation before semantic search
- Response format parity with existing CLI/MCP output

**Depends on**: Phase 3
**Key risks**: SearchService memory load pattern at 500K nodes (Finding 02). Server must use SQL-native search, not get_all_nodes().
**CS**: CS-4 (large)

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 4.1 | GET `/api/v1/graphs` → list all tenant graphs | server | Returns GraphInfo-compatible JSON with name, status, node_count, embedding_model | AC9 |
| 4.2 | GET `/api/v1/graphs/{name}/tree?pattern=&max_depth=` | server | Same output as `fs2 tree` against local graph | AC6 |
| 4.3 | GET `/api/v1/graphs/{name}/nodes/{node_id}` | server | Same output as `fs2 get-node` | AC8 |
| 4.4 | Implement PgvectorSemanticMatcher: SQL cosine query | search | Semantic search via pgvector, sub-100ms at 200K nodes | Per finding 02, AC10 |
| 4.5 | GET `/api/v1/search?pattern=&mode=&graph=&limit=` → multi-graph search | server | Supports single graph, graph1,graph2, or all | AC7 |
| 4.6 | Server-side text/regex via SQL ILIKE and `~` operator | search | Text/regex search uses trigram indexes, not in-memory | Workshop D5 |
| 4.7 | Embedding model validation: reject search if model mismatch | server | Error if query model ≠ stored model | Finding R4 |
| 4.8 | Tests: query parity with local mode for all 4 search modes | search | Upload graph → remote search → results match local search | |

### Acceptance Criteria
- [ ] AC6: Remote tree matches local tree
- [ ] AC7: Remote search (text/regex/semantic/auto) matches local, multi-graph works
- [ ] AC8: Remote get-node matches local
- [ ] AC9: List-graphs shows all accessible graphs
- [ ] AC10: Semantic search <100ms at 500K nodes

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Query result parity drift between local and server | Medium | High | Comparison tests: same graph, same query, diff outputs |

---

### Phase 5: Remote CLI + MCP Bridge

**Objective**: Enable the `fs2` CLI and MCP server to transparently query remote server data.
**Domain**: cli-presentation (modify), configuration (modify)
**Delivers**:
- `--remote <name|url>` global CLI flag + `FS2_REMOTE` env var
- RemoteClient + MultiRemoteClient: async HTTP clients (NOT GraphStore ABC — returns raw JSON)
- RemotesConfig + RemoteServer Pydantic models
- `resolve_remote_client()` in cli/utils.py (does NOT modify `resolve_graph_from_context()`)
- MCP mixed mode: remote graphs discovered from RemotesConfig, routed by `graph_name` prefix
- `fs2 list-remotes` command
- Persistent remote config in `~/.config/fs2/config.yaml`

**Note**: graph-storage domain is NOT modified. RemoteClient lives in cli-presentation, not in core/repos.

**Depends on**: Phase 4
**Key risks**: Network errors need graceful handling. Large responses (500KB node content) need compression.
**CS**: CS-3 (medium)

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 5.1 | Add `--remote` flag to CLI main.py (global option) + `FS2_REMOTE` env var | cli-presentation | Flag propagates to all subcommands via CLIContext | AC11 |
| 5.2 | Add RemotesConfig + RemoteServer to configuration registry | configuration | Named remotes loaded from user/project YAML | Per finding 06 |
| 5.3 | Implement RemoteClient + MultiRemoteClient: async httpx clients | cli-presentation | tree/search/get_node/list_graphs work via HTTP; returns raw JSON | Does NOT implement GraphStore ABC |
| 5.4 | Add resolve_remote_client() to cli/utils.py | cli-presentation | CLI commands check this first; branches to remote mode early | Does NOT modify resolve_graph_from_context() |
| 5.5 | `fs2 tree --remote <name> --graph <name>` works end-to-end | cli-presentation | Output identical to local tree | AC6 |
| 5.6 | `fs2 search --remote <name> "pattern"` works end-to-end | cli-presentation | All 4 modes work, multi-graph works, multi-remote fan-out works | AC7 |
| 5.7 | MCP mixed mode: remote graphs coexist with local graphs | cli-presentation | MCP tree/search/get_node route by graph_name prefix | AC12, AC13 |
| 5.8 | `fs2 list-remotes` command | cli-presentation | Shows configured remotes from config (no HTTP calls) | |
| 5.9 | Error handling: network failures → actionable fs2 errors | cli-presentation | Connection refused → "Server unreachable at <url>. Check --remote." | |
| 5.10 | Tests: remote CLI e2e (test server or fake server) | cli-presentation | Query via CLI, verify output matches expected | |

### Acceptance Criteria
- [ ] AC11: --remote / FS2_REMOTE transparently routes all commands
- [ ] AC12: MCP remote mode works
- [ ] AC13: MCP response format identical
- Revalidated via remote: AC6 (tree), AC7 (search), AC8 (get-node), AC9 (list-graphs)

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Network latency makes remote CLI feel slow | Medium | Medium | gzip compression, client-side response caching |

---

### Phase 6: Management Dashboard

**Objective**: Web dashboard for graph upload, tenant management, API key provisioning, and status monitoring.
**Domain**: server (modify), auth (modify)
**Delivers**:
- Dashboard views: graph list, graph upload, ingestion status, API key management
- HTMX-based server-rendered UI (FastAPI + Jinja2 + Alpine.js)
- File upload with progress (chunked, to staging, triggers ingestion)
- Tenant self-service: view graphs, delete graphs
- Operator views: create tenants, generate API keys
- Structured request logging

**Depends on**: Phase 3 (upload), Phase 4 (queries), Phase 2 (auth)
**Key risks**: Dashboard scope creep. Keep v1 minimal — functional over beautiful.
**CS**: CS-3 (medium)

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 6.1 | Dashboard skeleton: FastAPI + Jinja2 + HTMX + Alpine.js | server | `/dashboard/` renders base layout | |
| 6.2 | Graph list view: table of tenant's graphs with status | server | Shows name, node_count, status, last updated | AC20 |
| 6.3 | Graph upload view: file picker + chunked upload with progress | server | 128MB pickle uploads with visible progress bar | AC19 |
| 6.4 | Ingestion status: SSE/polling for real-time progress | server | Upload → ingesting → ready visible in UI | AC5, AC20 |
| 6.5 | Graph delete: confirmation dialog + DELETE cascade | server | Graph and all associated data removed | AC21 |
| 6.6 | API key management: generate and revoke API keys | server | Operator can generate + revoke keys via dashboard | AC18 (tenant creation deferred) |
| 6.7 | Structured request logging: latency, status, tenant, graph | server | Logs parseable by standard log aggregators | AC24 |
| 6.8 | Tests: upload flow, delete flow, key generation | server | Dashboard functional tests | Lightweight — not visual |

### Acceptance Criteria
- [ ] AC5: Dashboard shows ingestion progress
- [ ] AC18: Operator can generate API keys (tenant creation deferred to auth phase)
- [ ] AC19: Tenant can upload graph pickles via dashboard
- [ ] AC20: Tenant can view graphs + ingestion progress
- [ ] AC21: Tenant can delete graphs
- [ ] AC24: Structured request logging

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Dashboard scope creep | High | Medium | Strict v1 scope: no fancy UI, function over form |

---

### Phase 7: Documentation + Polish

**Objective**: Complete documentation, deployment guide, and operational readiness.
**Domain**: all domains
**Delivers**:
- README.md server mode section
- docs/how/operator/server-deployment.md
- docs/how/user/remote-queries.md
- docs/how/user/server-dashboard.md
- API versioning (/api/v1/)
- Error message review (all errors actionable)
- Performance validation at target scale

**Depends on**: Phases 1-6
**CS**: CS-2 (small)

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 7.1 | README.md: server mode quick-start section | — | README explains both operator and user workflows | |
| 7.2 | docs/how/operator/server-deployment.md | — | Docker Compose setup, env vars, PostgreSQL config documented | |
| 7.3 | docs/how/user/remote-queries.md | — | --remote usage, config file, multi-graph search | |
| 7.4 | docs/how/user/server-dashboard.md | — | Upload, manage, delete graphs via dashboard | |
| 7.5 | Error message audit: all server errors are actionable | server, auth | Every error includes "what to do" guidance | |
| 7.6 | Scale validation: test with 10+ graphs, 50K+ total nodes | server | Query latency still under 100ms | |

### Acceptance Criteria
- [ ] Documentation covers operator and user workflows
- [ ] All error messages are actionable
- [ ] Performance validated at target scale

---

## Risks (Plan-Level)

| Risk | Likelihood | Impact | Mitigation | Phase |
|------|------------|--------|------------|-------|
| GraphStore ABC mismatch with PostgreSQL | — | — | Server-side store implements query methods; save/load are no-ops | 3 |
| SearchService 500K-node memory load | — | — | PgvectorSemanticMatcher + SQL text/regex bypass in-memory load | 4 |
| Async psycopg3 pool instability | Low | High | Load test in Phase 1; fallback to sync with thread pool | 1 |
| RLS tenant context leak | Medium | Critical | Transaction-scoped SET + RESET in middleware; multi-tenant tests | 2 |
| 500MB upload OOM | Medium | High | Stream to disk; async ingestion; 202 Accepted pattern | 3 |
| HNSW rebuild at 500K nodes | Low | Medium | pgvector incrementally updates; full rebuild only on first ingest | 3 |
| Dashboard scope creep | High | Medium | Strict v1: upload, list, delete, keys — nothing more | 6 |
| Network latency for remote CLI | Medium | Medium | gzip compression, ETag caching, httpx connection pooling | 5 |
