# fs2 Server Mode

**Mode**: Full
**Slug**: server-mode

📚 This specification incorporates findings from `research-dossier.md`, `external-research/synthesis.md`, and workshops `001-database-schema.md` / `002-prototype-validation.md`.

## Research Context

Extensive pre-spec research (71 findings from 8 parallel subagents) mapped the full fs2 architecture, followed by 3 deep research reports (database selection, dashboard architecture, remote CLI protocol) totaling 166KB. A hands-on prototype validated PostgreSQL + pgvector against a real fs2 graph (5,231 nodes, 10,845 embedding chunks), proving sub-5ms query latency for all operation types including semantic vector search. Seven architectural decisions are locked with measured evidence.

Key validated facts:
- fs2's Clean Architecture (ABC interfaces, DI) supports server mode without core refactoring
- PostgreSQL + pgvector handles graph + vector + content queries in a single database
- Ingestion of a real graph via COPY takes 5 seconds; HNSW index build takes 3 seconds
- All query types (tree traversal, text/regex search, semantic search) run under 5ms
- Live Azure text-embedding-3-small queries against pgvector return highly relevant results

## Summary

**WHAT**: Add a server mode to fs2 that hosts pre-scanned code graphs for many repositories, enabling teams to query code intelligence data remotely via the same CLI commands and MCP tools they use locally.

**WHY**: fs2 currently stores everything in local pickle files — one per repository. This works for individual developers but cannot serve teams or organizations that need centralized access to code intelligence across hundreds of repositories. A server mode unlocks:
- **Team access**: Multiple developers and AI agents querying the same code graphs
- **Scale**: Hundreds of repositories indexed and searchable from a single endpoint
- **Management**: Upload, update, and remove indexed sites through a dashboard
- **Consistency**: Everyone sees the same indexed state of each repository

## Goals

- **G1**: A user can point their existing `fs2` CLI at a remote server and run `tree`, `search`, `get-node`, and `list-graphs` commands against server-hosted repositories with the same output they'd get locally
- **G2**: A user can upload a locally-scanned graph (`fs2 scan` output) to the server, making it immediately available for remote queries
- **G3**: An MCP-connected AI agent can transparently query remote graphs without knowing whether the data is local or server-hosted
- **G4**: A server operator can manage tenants, sites, and API keys through a web dashboard
- **G5**: Multiple tenants can use the same server with complete data isolation — no tenant can see or query another tenant's graphs
- **G6**: The server scales to hundreds of indexed sites (10K–200K nodes each) with query latency under 100ms

## Non-Goals

- **NG1**: Remote scanning — source code never leaves the client machine. The server only receives pre-built graph artifacts
- **NG2**: Real-time synchronization — when a repository changes, the user must re-scan locally and re-upload. The server does not pull from Git
- **NG3**: Collaborative editing of graphs — graphs are read-only on the server; the only write operation is a full replace via upload
- **NG4**: Federation between servers — each server is standalone; cross-server queries are not supported
- **NG5**: Billing or payment processing — usage tracking is in scope, but integration with payment providers is not
- **NG6**: Code execution on the server — the server stores and queries indexed artifacts, not source code to be compiled or run

## Target Domains

> **Note**: No formal domain registry exists yet. The "existing" entries below are natural code boundaries identified during research. Key domains (graph-storage, search, configuration) should be formally extracted via `plan-v2-extract-domain` before architecting.

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| graph-storage | informal (extract before plan-3) | **modify** | Add PostgreSQL-backed GraphStore implementation; extend GraphService for remote catalog |
| search | informal (extract before plan-3) | **modify** | Wire SearchService to query pgvector for semantic search instead of brute-force |
| indexing | informal | **consume** | Client-side `fs2 scan` unchanged — produces pickle that gets uploaded |
| embedding | informal | **consume** | Server uses same embedding adapter to embed search queries against stored vectors |
| configuration | informal (extract before plan-3) | **modify** | Add ServerConfig, RemotesConfig Pydantic models |
| cli-presentation | informal | **modify** | Add `--remote` flag, `fs2 list-graphs` remote variant, `fs2 list-remotes` command |
| server | **NEW** | **create** | FastAPI application: HTTP API, ingestion pipeline, management dashboard |
| auth | **NEW** | **create** | API key management, tenant isolation, Row-Level Security |

### New Domain Sketches

#### server [NEW]
- **Purpose**: The HTTP server application that receives graph uploads, stores data in PostgreSQL + pgvector, and serves query requests via REST API. Also hosts the management dashboard.
- **Boundary Owns**: HTTP routing, request/response serialization, ingestion pipeline (pickle → DB), background job processing, dashboard UI, health/metrics endpoints
- **Boundary Excludes**: Graph query logic (delegates to existing SearchService/TreeService), embedding generation (delegates to existing EmbeddingAdapter), CLI argument parsing (belongs to cli-presentation)

#### auth [NEW]
- **Purpose**: Tenant and API key management, request authentication, and data isolation enforcement.
- **Boundary Owns**: Tenant CRUD, API key generation/validation/rotation, RLS policy enforcement, request-scoped tenant context, dashboard user authentication (OAuth2)
- **Boundary Excludes**: Authorization policies beyond tenant isolation (e.g., per-graph permissions within a tenant — future scope), user profile management, SSO provider configuration

## Complexity

- **Score**: CS-5 (epic)
- **Breakdown**: S=2, I=2, D=2, N=1, F=2, T=2 → P=11
  - **Surface Area (S=2)**: Cross-cutting — new server package, new CLI commands, modified config, new DB layer, dashboard UI
  - **Integration (I=2)**: PostgreSQL + pgvector (new), FastAPI (new), Azure AD auth, HTMX dashboard, background job queue
  - **Data/State (D=2)**: Entirely new database schema (5+ tables), migration from pickle, HNSW vector indexes, multi-tenant RLS
  - **Novelty (N=1)**: Well-researched via 3 deep research reports + prototype validation; remaining unknowns are manageable (scale testing, async pooling)
  - **Non-Functional (F=2)**: Multi-tenant security isolation, query latency SLAs, large file upload handling, concurrent access
  - **Testing/Rollout (T=2)**: Integration tests with real PostgreSQL, end-to-end upload→query tests, multi-tenant isolation tests, load testing
- **Confidence**: 0.80 — high due to validated prototype, but scale testing and production deployment are untested
- **Assumptions**:
  - PostgreSQL + pgvector performance extrapolates to 100× current prototype scale
  - fs2's existing ABC interfaces are sufficient for remote adapter implementations without interface changes
  - Pickle upload is acceptable UX (vs. streaming incremental updates)
- **Dependencies**:
  - PostgreSQL 15+ with pgvector extension available in deployment environment
  - Docker for self-hosted deployments
  - Embedding API access on the server (for embedding search queries)
- **Risks**:
  - HNSW index build time at large scale (100K+ vectors) could impact re-upload latency
  - Connection pooling under concurrent load — not yet validated
  - Graph upload size (50–500MB) may hit reverse proxy limits in some deployments
- **Phases**: Server skeleton → Database backend → Remote CLI → Management dashboard → MCP bridge → Polish

## Acceptance Criteria

### Graph Upload & Ingestion
- **AC1**: A tenant user can upload a graph pickle file through the dashboard, and it becomes queryable within 30 seconds for a 5K-node graph
- **AC2**: Re-uploading a graph for the same repository replaces the previous version completely — old data is not retained
- **AC3**: The server preserves all graph metadata (format_version, embedding_model, embedding_dimensions, chunk_params) from the pickle file
- **AC4**: Upload rejects pickle files that fail RestrictedUnpickler validation (security: no arbitrary code execution)
- **AC5**: The dashboard shows upload and ingestion progress for in-flight graph imports

### Remote Queries
- **AC6**: `fs2 tree --remote <name|url> --graph <name>` returns the same hierarchical structure as querying the local graph
- **AC7**: `fs2 search --remote <name|url> "pattern"` supports `--graph <name>` (single), `--graph name1,name2` (multi), or no `--graph` flag (search all accessible graphs). All four modes (text, regex, semantic, auto) work identically to local search.
- **AC8**: `fs2 get-node --remote <name|url> --graph <name> <node_id>` returns full node content identical to local get-node
- **AC9**: `fs2 list-graphs --remote <name|url>` shows all graphs the authenticated user has access to, with name, description, node count, embedding model, and status
- **AC10**: Semantic search on the server uses pgvector HNSW cosine similarity and returns results in under 100ms for graphs up to 500K nodes
- **AC11**: If `--remote` is set (via flag or `FS2_REMOTE` env var), all query commands transparently route to the server without other changes

### MCP Integration
- **AC12**: An MCP server started with remote configuration (named remotes in config) exposes the same `tree`, `search`, `get_node`, and `list_graphs` tools, backed by server data via RemoteClient
- **AC13**: AI agents using MCP tools cannot distinguish between local and remote mode — response formats are identical

### Multi-Tenancy & Auth
- **AC14**: Each API request requires a valid API key in the `Authorization: Bearer fs2_<key>` header
- **AC15**: A tenant can only see and query their own graphs — Row-Level Security prevents cross-tenant data access even if application code has bugs
- **AC16**: API keys can be scoped to read-only or read-write (write = upload/delete graphs)
- **AC17**: Invalid or expired API keys return HTTP 401 with an actionable error message

### Management Dashboard
- **AC18**: A server operator can create tenants and generate API keys through the dashboard
- **AC19**: A tenant user can upload graph pickle files (50–500MB) via the dashboard with progress feedback
- **AC20**: A tenant user can view their graphs (name, status, node count, last updated) and see real-time ingestion progress
- **AC21**: A tenant user can delete a graph from the dashboard, which removes all associated data

### Operational
- **AC22**: The server can be deployed as a single Docker Compose stack (FastAPI + PostgreSQL + Redis)
- **AC23**: Health check endpoint (`/health`) returns server status, database connectivity, and graph count
- **AC24**: The server logs structured request metrics (latency, status code, tenant, graph) for monitoring

## Risks & Assumptions

### Risks
- **R1**: HNSW index build time scales super-linearly — rebuilding after a large graph upload (200K+ nodes) could take minutes, blocking queries during rebuild. *Mitigation*: Build index in background, swap atomically.
- **R2**: Pickle deserialization is a potential attack vector — malicious pickle files could attempt code execution. *Mitigation*: RestrictedUnpickler whitelist is already battle-tested in fs2.
- **R3**: Large file uploads (500MB) may fail in enterprise environments with aggressive proxy timeouts. *Mitigation*: Chunked upload with resumability.
- **R4**: Embedding model mismatch — if the server embeds queries with a different model than the stored vectors, results are garbage. *Mitigation*: Store embedding model metadata per graph, validate before search.

### Assumptions
- **A1**: Users have an existing `fs2 scan` workflow — server mode does not need to teach scanning
- **A2**: One embedding model per graph is sufficient (no mixed-model graphs)
- **A3**: Full graph replacement on re-upload is acceptable (no incremental/differential updates needed)
- **A4**: The server operator controls the embedding API credentials (users don't need their own for search)
- **A5**: Graphs are read-mostly — concurrent write pressure is low (only during upload)

## Open Questions

*All resolved — see Clarifications below.*

## Testing Strategy

- **Approach**: Hybrid
- **Rationale**: TDD for server core (ingestion pipeline, database repository, auth/RLS, vector search), lightweight/test-after for CLI glue (--remote flag threading) and dashboard templates (HTMX views)
- **Mock Policy**: Fakes over mocks — matches fs2 convention. Create FakeDatabase, FakeIngestionPipeline, etc. as real interface implementations. Mocks only if fakes are truly impractical.
- **Focus Areas**: Ingestion pipeline (pickle → DB round-trip), RLS tenant isolation (multi-tenant queries), semantic search accuracy (pgvector vs brute-force parity), API auth (key validation, scope enforcement)
- **Excluded**: Dashboard visual/layout testing, Docker Compose integration (tested manually)

## Documentation Strategy

- **Location**: Hybrid — README quick-start + docs/how/ detailed guides
- **Rationale**: Operators need deployment guides (docs/how/operator/), users need CLI remote usage guides (docs/how/user/), and the README needs a quick-start section for both
- **Planned Docs**:
  - README.md: Server mode overview section
  - docs/how/operator/server-deployment.md: Docker Compose setup, PostgreSQL config, environment variables
  - docs/how/user/remote-queries.md: Using --remote, configuring persistent remote, searching across graphs
  - docs/how/user/server-dashboard.md: Uploading graphs, managing API keys, monitoring

## Clarifications

### Session 2026-03-05

**Q1: Workflow Mode** → **Full** (CS-5 epic, multi-phase, all gates required)

**Q2: Testing Strategy** → **Hybrid** (TDD for core, lightweight for glue) — user skipped, defaulted to recommended

**Q3: Mock Usage** → **Fakes over mocks** (matches fs2 convention — FakeDatabase, FakeIngestionPipeline, etc.)

**Q4: Documentation Strategy** → **Hybrid** (README quick-start + docs/how/ detailed guides)

**Q5: Domain Review** → Existing "domains" in the spec are informal code boundaries, not formally extracted. **Action**: Extract key domains (graph-storage, search, config) via plan-v2-extract-domain BEFORE running plan-3-architect. Keep server and auth as 2 new domains.

**Q6: Upload UX** → **No CLI push command for v1.** Graph upload happens through the web dashboard (browser upload). This avoids CLI auth complexity and security concerns. `fs2 push` may be added later.
- **Spec impact**: Removed AC1 (push command), AC5 (CLI upload progress). Updated AC to reflect dashboard-only upload. The `--remote` flag is for queries only.

**Q7: Cross-graph search** → **Full flexibility**: single graph, multiple named graphs, or all graphs. Query API should support `--graph graph1,graph2` and `--graph all` (or no `--graph` = search all accessible).
- **Spec impact**: Updated AC7/AC9 to reflect multi-graph search capability.

**Q8: Scale ceiling** → **500K nodes per graph** (large monorepo). Partitioning not needed for v1 but should be workshopped to understand difficulty of adding later.
- **Spec impact**: Updated AC10 scale target. Added workshop topic for HNSW partitioning strategy.

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| ~~Database Schema~~ | ~~Storage Design~~ | ~~COMPLETED~~ | See `workshops/001-database-schema.md` |
| ~~Prototype Validation~~ | ~~Integration Pattern~~ | ~~COMPLETED~~ | See `workshops/002-prototype-validation.md` |
| Remote CLI Flow | CLI Flow | How `--remote` flag threads through the CLI layer, interacts with existing graph resolution, and falls back gracefully | How does the CLI branch for remote mode? What happens when remote is down? Config file format for persistent remote? |
| Ingestion Pipeline | State Machine | Upload → staging → validation → COPY import → HNSW → ready has multiple failure modes and status transitions | What happens on partial failure? How to report progress? Retry semantics? Concurrent uploads for same graph? |
| Auth & Tenant Model | API Contract | Tenant hierarchy, API key scoping, RLS integration pattern, and dashboard auth need careful design before implementation | How many roles? Key rotation flow? Admin vs tenant user? How does RLS interact with connection pooling? |
| HNSW Partitioning Strategy | Scale Design | 500K-node ceiling means 1M+ embedding chunks; need to understand when partitioning becomes necessary and how hard to retrofit | Single index vs per-graph partition? Build time at 1M vectors? Can we partition later without downtime? |
