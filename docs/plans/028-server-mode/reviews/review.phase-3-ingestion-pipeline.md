# Code Review: Phase 3: Ingestion Pipeline + Graph Upload

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md  
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md  
**Phase**: Phase 3: Ingestion Pipeline + Graph Upload  
**Date**: 2026-03-06  
**Reviewer**: Automated (plan-7-v2)  
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

High-severity correctness, architecture-boundary, and testing gaps block approval.

**Key failure areas**:
- **Implementation**: Upload metadata binding is incorrect for multipart forms, ingestion error-path transaction handling is unsafe, and `PostgreSQLGraphStore` does not implement required sync query methods.
- **Domain compliance**: `graph-storage` now imports `server` (`fs2.server.database.Database`), creating an unintended reverse dependency/cycle and map drift.
- **Reinvention**: Pickle load/validate logic is partially reimplemented in `server.ingestion` instead of being consolidated with existing graph-load behavior.
- **Testing**: Core acceptance paths (upload flow, re-upload replace, status behavior, PG store parity) are not verified by the committed tests.

## B) Summary

This phase lands important foundations (ingestion pipeline, graph routes, schema updates, and pickle-security extraction), but review found blocking defects before merge. The most serious runtime risks are multipart contract mismatch in `POST /api/v1/graphs` and fragile failure handling in ingestion transactions after COPY/SQL errors. Domain boundaries also regressed: `graph-storage` now imports `server` internals, while domain artifacts (manifest/map/domain docs) are not fully synchronized to the new dependency shape. Testing evidence is insufficient for phase-critical acceptance criteria, with no committed `test_graph_store_pg.py` and no behavior tests for upload/re-upload/status paths.

## C) Checklist

**Testing Approach: Hybrid**

- [ ] Core-path TDD coverage present for ingestion pipeline and upload endpoint behaviors
- [ ] Lightweight glue coverage present for route wiring/OpenAPI surfacing
- [ ] Evidence links each relevant acceptance criterion to concrete verification output

Universal (all approaches):
- [ ] Only in-scope files changed
- [x] Linters/type checks clean (as claimed in execution log)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py:27-33 | correctness | Upload metadata fields are declared as plain params, so FastAPI treats them as query params instead of multipart form fields. | Use `Form(...)`/`File(...)` annotations for multipart contract fields. |
| F002 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/ingestion.py:228-234 | error-handling | Ingestion failure handling updates status in the same possibly failed transaction, risking secondary DB errors and uncontrolled 500s. | Roll back first, then set error status in a fresh transaction/connection, then raise `IngestionError`. |
| F003 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_pg.py:17,195-209 | pattern | `PostgreSQLGraphStore` claims `GraphStore` compatibility but required sync query methods raise `NotImplementedError`. | Implement contract methods or split into a distinct async interface without inheriting `GraphStore`. |
| F004 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_pg.py:17 | dependency-direction | `graph-storage` imports `fs2.server.database.Database`, reversing intended dependency flow and creating a domain cycle. | Depend on a domain-neutral protocol/port (or move implementation to server infra layer) and update composition wiring. |
| F005 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_upload.py:1-83; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_ingestion.py:1-173; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_store_pg.py (missing) | testing | Phase-critical behaviors are not tested: upload success/failure, re-upload replacement, status transitions, and PG store parity. | Add targeted behavior/integration tests and create `test_graph_store_pg.py` as specified by phase tasks. |
| F006 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py:39-49 | security | Upload streaming does not enforce configured max upload size (`ServerStorageConfig.max_upload_bytes`). | Track bytes while streaming and reject over-limit uploads with 413 + temp file cleanup. |
| F007 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md:74-122; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:41-48; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md:26-63 | domain-compliance | Domain docs/manifest/map are not fully updated for new files/dependencies (contracts/composition/source list and edge set drift). | Update domain.md tables, domain-map edges/labels, and plan Domain Manifest for all changed files. |
| F008 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/ingestion.py:53-100 | reinvention | `load_pickle()` duplicates part of existing graph-load behavior from `NetworkXGraphStore.load()`. | Extract/shared helper for common pickle validation/loading semantics where practical. |
| F009 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-3-ingestion-pipeline/execution.log.md:32-38 | testing-evidence | Evidence is summary-only; command transcripts and AC-to-proof traceability are missing. | Add explicit command outputs and AC↔test mapping entries to execution evidence. |

## E) Detailed Findings

### E.1) Implementation Quality

- **F001 (HIGH)**: Multipart contract mismatch in `upload_graph()` because metadata fields are not declared as `Form(...)`.
- **F002 (HIGH)**: Error-path status update is attempted after potential transaction failure state, which can mask original ingestion errors.
- **F003 (HIGH)**: `PostgreSQLGraphStore` does not satisfy functional expectations of `GraphStore` read methods.
- **F006 (MEDIUM)**: Upload size limit from config is not enforced during stream-to-disk.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New source files are under expected `server` / `graph-storage` trees. |
| Contract-only imports | ❌ | `server.ingestion` imports `fs2.core.repos.pickle_security`; contract documentation for this symbol is incomplete in graph-storage tables. |
| Dependency direction | ❌ | `graph-storage` imports `server` (`graph_store_pg.py` → `fs2.server.database.Database`). |
| Domain.md updated | ❌ | `graph-storage/domain.md` history updated, but Contracts/Composition/Source tables omit new components. |
| Registry current | ✅ | `docs/domains/registry.md` lists current domains; no missing domain registration found. |
| No orphan files | ❌ | Plan `## Domain Manifest` omits changed files (e.g., `pickle_security.py`, Phase 3 test files). |
| Map nodes current | ✅ | Domain nodes exist for active/planned domains. |
| Map edges current | ❌ | Map shows `server -> graph-storage` but not current reverse code dependency. |
| No circular business deps | ❌ | A server↔graph-storage cycle now exists in code-level dependencies. |
| Concepts documented | ⚠️ | Concepts sections exist, but new contract/component entries are incomplete. |

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `load_pickle()` + validation in `server.ingestion` | `NetworkXGraphStore.load` semantics in `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_impl.py` | graph-storage | ⚠️ Partial duplication (F008) |

### E.4) Testing & Evidence

**Coverage confidence**: 33%

| AC | Confidence | Evidence |
|----|------------|----------|
| AC1 | 15 | No committed behavior test for `POST /api/v1/graphs` upload-to-ready path. |
| AC2 | 10 | Re-upload replacement behavior claimed in log but not validated by tests. |
| AC3 | 35 | Metadata extraction helper tested, but persistence/round-trip behavior not proven. |
| AC4 | 75 | Malicious pickle rejection tested (`test_load_malicious_pickle`, `TestRestrictedUnpickler`). |
| AC5 | 20 | Status endpoint presence tested via OpenAPI, not lifecycle behavior assertions. |
| AC9 | 40 | `GET /api/v1/graphs` empty-state test exists; populated/field parity cases missing. |

### E.5) Doctrine Compliance

N/A at required path — `docs/project-rules/{rules,idioms,architecture,constitution}.md` not found. Closest equivalents exist under `/Users/jordanknight/substrate/fs2/028-server-mode/docs/rules-idioms-architecture/`; no additional doctrine-only findings beyond F004/F005.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC1 | Upload graph becomes queryable within target window | No direct upload behavior test in committed diff | 15 |
| AC2 | Re-upload fully replaces prior graph data | No committed replacement/no-orphan verification test | 10 |
| AC3 | Graph metadata preserved | Helper extraction tests only; no DB round-trip assertion | 35 |
| AC4 | RestrictedUnpickler blocks malicious pickle | Explicit malicious pickle unit tests present | 75 |
| AC5 | Ingestion progress/status lifecycle visible | Route existence asserted, lifecycle transitions untested | 20 |
| AC9 | List graphs endpoint returns graph catalog data | Empty-state list test only; populated response parity untested | 40 |

**Overall coverage confidence**: 33%

## G) Commands Executed

```bash
git --no-pager status --short
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager log --oneline -15
git --no-pager diff 67176ba..HEAD > /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/_computed.diff
git --no-pager diff --name-status 67176ba..HEAD > /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/_manifest.txt
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md  
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md  
**Phase**: Phase 3: Ingestion Pipeline + Graph Upload  
**Tasks dossier**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-3-ingestion-pipeline/tasks.md  
**Execution log**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-3-ingestion-pipeline/execution.log.md  
**Review file**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/review.phase-3-ingestion-pipeline.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md | Modified | graph-storage | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md | Modified | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-2-auth/execution.log.md | Added | planning-docs | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-2-auth/tasks.fltplan.md | Added | planning-docs | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-2-auth/tasks.md | Added | planning-docs | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-3-ingestion-pipeline/execution.log.md | Added | planning-docs | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-3-ingestion-pipeline/tasks.fltplan.md | Added | planning-docs | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-3-ingestion-pipeline/tasks.md | Added | planning-docs | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/pyproject.toml | Modified | configuration | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_impl.py | Modified | graph-storage | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_pg.py | Added | graph-storage | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/pickle_security.py | Added | graph-storage | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/app.py | Modified | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/ingestion.py | Added | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py | Added | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/schema.py | Modified | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_upload.py | Added | server-tests | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_ingestion.py | Added | server-tests | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/uv.lock | Modified | dependencies | No |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py | Bind upload metadata as multipart form fields (`Form/File`) and enforce contract | Current signature treats metadata as query params; breaks documented multipart upload behavior |
| 2 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/ingestion.py | Harden error-path transaction handling (rollback + fresh status update) | Prevent secondary DB failures masking ingestion errors |
| 3 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_pg.py | Remove reverse dependency on `fs2.server.*` and satisfy GraphStore query contract expectations | Avoid domain cycle and runtime `NotImplementedError` on contract methods |
| 4 | /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_upload.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_ingestion.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_store_pg.py | Add missing behavior coverage for AC1/AC2/AC5/AC9 and PG store parity | Current tests do not validate critical phase outcomes |
| 5 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md | Update contracts/composition/source tables, dependency edges, and Domain Manifest entries | Domain artifacts are not synchronized with implemented changes |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md | Contracts/Composition/Source tables for `pickle_security.py` and `graph_store_pg.py` |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | Edge/cycle representation and labels aligned to current dependency graph |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md | Domain Manifest entries for newly changed files |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md | Boundary text still references background jobs; Phase 3 implementation is synchronous |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md --phase 'Phase 3: Ingestion Pipeline + Graph Upload'
