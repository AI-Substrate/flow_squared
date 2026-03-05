# Fix Tasks: Phase 1: Server Skeleton + Database

Apply in order. Re-run review after fixes.

## Critical / High Fixes

### FT-001: Satisfy AC22 Compose Stack Requirement
- **Severity**: HIGH
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/028-server-mode/docker-compose.yml
  - /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-1-server-skeleton-database/execution.log.md
- **Issue**: Operational AC22 requires a single Docker Compose stack with FastAPI + PostgreSQL + Redis, but compose currently defines only `db` and `server`.
- **Fix**:
  1. Add a `redis` service to compose (image, ports if needed, healthcheck).
  2. Wire server service dependency if runtime behavior needs Redis availability.
  3. Update execution evidence with concrete command output proving all required services are healthy.
- **Patch hint**:
  ```diff
   services:
     db:
       ...
  +  redis:
  +    image: redis:7-alpine
  +    healthcheck:
  +      test: ["CMD", "redis-cli", "ping"]
  +      interval: 5s
  +      timeout: 3s
  +      retries: 5
     server:
       ...
       depends_on:
         db:
           condition: service_healthy
  +      redis:
  +        condition: service_healthy
  ```

## Medium / Low Fixes

### FT-002: Assert AC23 Happy-Path Health Payload
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_health.py
- **Issue**: Tests currently verify health status code/shape and degraded path, but do not explicitly assert connected success payload semantics.
- **Fix**: Add a test asserting `status="ok"`, `db="connected"`, and expected numeric `graphs` when database is connected.
- **Patch hint**:
  ```diff
   async def test_health_json_shape(client: AsyncClient):
       ...
  +async def test_health_connected_payload(client: AsyncClient):
  +    response = await client.get("/health")
  +    data = response.json()
  +    assert data["status"] == "ok"
  +    assert data["db"] == "connected"
  +    assert isinstance(data["graphs"], int)
  ```

### FT-003: Update Configuration Domain Contracts/History/Concepts
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md
- **Issue**: New public config contracts (`ServerDatabaseConfig`, `ServerStorageConfig`) are implemented but undocumented in domain contract and history sections.
- **Fix**:
  1. Add both config models to Contracts and Source Location sections.
  2. Add phase history row for Phase 1 server-mode changes.
  3. Add Concepts entries describing server DB/storage config usage.
- **Patch hint**:
  ```diff
   | Contract | Type | Consumers | Description |
   |----------|------|-----------|-------------|
  +| `ServerDatabaseConfig` | Pydantic Model | server domain | DB host/port/pool configuration |
  +| `ServerStorageConfig` | Pydantic Model | server domain | Upload staging configuration |
  ...
   ## History
  +| 028-server-mode (Phase 1) | Added server database/storage config contracts | 2026-03-05 |
  ```

### FT-004: Align Auth Domain Doc with No-RLS Direction
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md
- **Issue**: Auth domain documentation still presents mandatory RLS middleware despite phase artifacts documenting no-RLS direction for current architecture.
- **Fix**: Update Purpose, Concepts, Boundary, and Contracts sections to match implemented decision and record the change in History.
- **Patch hint**:
  ```diff
  -...Row-Level Security prevents any cross-tenant data access...
  +...API-key validation governs access; tenant isolation model is documented per current phase decisions...
  ...
  -| Enforce tenant isolation | RLS middleware | SET app.current_tenant_id ... |
  +| Enforce request auth | Auth middleware | Validate Bearer key and attach auth context |
  ```

### FT-005: Refresh Domain Map Node/Edge Currency
- **Severity**: MEDIUM
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md
- **Issue**: Map still marks server as planned and labels `server -> auth` with RLS middleware language, both stale relative to phase implementation records.
- **Fix**:
  1. Mark server node and health summary as active.
  2. Relabel auth edge to current API-key contract language.
- **Patch hint**:
  ```diff
  -server["🌐 server ..."]:::planned
  +server["🌐 server ..."]:::infra
  ...
  -server -->|AuthService + RLS middleware| auth
  +server -->|AuthService + API key middleware| auth
  ...
  -| server | ... | 🟡 Planned |
  +| server | ... | ✅ Active |
  ```

### FT-006: Remove Orphan-Mapping Drift in Domain Manifest
- **Severity**: MEDIUM
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
  - /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/_manifest.txt
- **Issue**: Plan Domain Manifest does not map every file touched by this phase diff, violating no-orphan mapping expectations.
- **Fix**: Either (a) extend Domain Manifest with all changed files (or explicit path patterns), or (b) split unrelated files out of this phase commit.
- **Patch hint**:
  ```diff
   ## Domain Manifest
   | File | Domain | Classification | Rationale |
   |------|--------|---------------|-----------|
  +| `tests/server/test_health.py` | server | internal | Phase 1 server health coverage |
  +| `src/fs2/server/routes/__init__.py` | server | internal | Server routes package |
  +| `Dockerfile` | server | internal | Server container runtime |
  +| `src/fs2/cli/watch.py` | cli-presentation | cross-domain | Out-of-phase change; move or justify |
  ```

### FT-007: Document Schema Ownership vs Graph-Storage Capability
- **Severity**: MEDIUM
- **File(s)**:
  - /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/schema.py
  - /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md
  - /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md
- **Issue**: Potential conceptual overlap between server schema bootstrap and graph-storage persistence ownership.
- **Fix**: Add explicit cross-domain ownership notes to prevent duplicate persistence abstractions as phases continue.
- **Patch hint**:
  ```diff
   ## Dependencies
  +The server domain owns operational schema bootstrap; graph-storage owns query/storage contracts.
  +Schema changes must stay aligned through documented contract boundaries.
  ```

### FT-008: Improve Execution Evidence Granularity
- **Severity**: LOW
- **File(s)**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-1-server-skeleton-database/execution.log.md
- **Issue**: Evidence is mostly summary counts without command transcripts for key acceptance checks.
- **Fix**: Append reproducible output snippets (compose status, health endpoint output, key test command output) mapped to AC IDs.
- **Patch hint**:
  ```diff
   ## Test Results
  +### AC22 Evidence
  +$ docker compose up -d
  +$ docker compose ps
  +...
  +
  +### AC23 Evidence
  +$ curl http://localhost:8000/health
  +{"status":"ok","db":"connected","graphs":0}
  ```

## Re-Review Checklist

- [ ] All critical/high fixes applied
- [ ] Re-run `/plan-7-v2-code-review` and achieve zero HIGH/CRITICAL
