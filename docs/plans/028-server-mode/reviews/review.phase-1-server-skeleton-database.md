# Code Review: Phase 1: Server Skeleton + Database

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md
**Phase**: Phase 1: Server Skeleton + Database
**Date**: 2026-03-05
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

Phase 1 has one unmitigated HIGH finding (AC22 operational stack mismatch: Redis is required by spec but not present in compose), plus multiple medium domain-documentation consistency gaps.

**Key failure areas**:
- **Domain compliance**: Domain documentation and domain map are not fully aligned with the implemented no-RLS direction and new configuration contracts.
- **Reinvention**: Schema/bootstrap ownership overlaps existing graph-storage responsibilities and needs explicit boundary documentation.
- **Testing**: AC22 lacks compliant evidence and AC23 lacks an explicit happy-path assertion in endpoint tests.

## B) Summary

Implementation quality for the new server package is solid: app factory, async pool wiring, schema bootstrap, and health route behavior are coherent and match Phase 1 task intent. The largest delivery gap is spec-level operational compliance: AC22 states a single compose stack of FastAPI + PostgreSQL + Redis, but the current compose file only contains FastAPI + PostgreSQL. Domain governance artifacts need alignment with the implementation decisions made in this phase, especially around no-RLS posture and newly introduced configuration contracts. Testing evidence is partially strong (endpoint and schema tests exist) but does not fully verify AC22 and only partially verifies AC23 behavior confidence.

## C) Checklist

**Testing Approach: Hybrid**

- [x] Core validation tests present
- [ ] Critical paths covered for all phase ACs
- [ ] Key verification points documented with command-level evidence
- [ ] Only in-scope files changed
- [x] Linters/type checks clean (per execution log)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/docker-compose.yml:10-53 | testing | Compose stack omits Redis although AC22 requires FastAPI + PostgreSQL + Redis. | Add Redis service with healthcheck and wiring; capture compose evidence. |
| F002 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md:74-90,133-142 | domain-md | Configuration domain docs do not include `ServerDatabaseConfig`/`ServerStorageConfig` contracts or Phase 1 history entry. | Update contracts/source/history sections to reflect new public config models. |
| F003 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md:11-31 | domain-md | Auth domain still describes RLS-centric design, conflicting with implemented no-RLS direction captured in phase artifacts. | Revise auth domain purpose/boundary/contracts/history to match current architecture. |
| F004 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:42-47 | map-edges | `server -> auth` edge label still references RLS middleware in map, inconsistent with current no-RLS model. | Relabel edge to API-key auth contracts and remove RLS wording. |
| F005 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:21-23,66-67 | map-nodes | Server domain remains marked as planned in map metadata despite active implementation in this phase. | Mark server node/health summary as active and update associated contract text. |
| F006 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md:26-57 | orphan | Plan `## Domain Manifest` does not account for all changed files in this phase diff (e.g., tests, Dockerfile, watch.py, routes package init). | Expand manifest or constrain phase diff to in-scope files only. |
| F007 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_health.py:63-76 | testing | Health tests validate status code/shape but do not assert explicit connected success payload for AC23. | Add a happy-path assertion test for `{\"status\":\"ok\",\"db\":\"connected\",\"graphs\":...}`. |
| F008 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/schema.py:22-138 | reinvention | Schema/bootstrap persistence logic overlaps graph-storage capability boundary and may drift without explicit ownership contract. | Document boundary as extension of graph-storage contract surface (or move ownership) to prevent duplicate evolution. |
| F009 | LOW | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md:13-21 | concepts-docs | Concepts table lacks entries for newly added server config concepts. | Add concepts rows for server DB/storage configuration entry points and responsibilities. |
| F010 | LOW | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-1-server-skeleton-database/execution.log.md:33-39 | testing | Evidence is summary-level; key AC checks lack raw command output artifacts. | Include command transcripts (compose status, health curl output) in execution log evidence. |

## E) Detailed Findings

### E.1) Implementation Quality

No correctness/security/performance defects were identified in the implemented server code paths (`app.py`, `database.py`, `schema.py`, `health.py`) relative to Phase 1 intent. The route behavior degrades safely on DB errors and pool lifecycle management follows the expected async pattern.

### E.2) Domain Compliance

Domain compliance issues are documentation and mapping currency gaps rather than runtime import-direction violations.

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New runtime files are placed under expected domain trees (`src/fs2/server`, `src/fs2/config`, `tests/server`). |
| Contract-only imports | ✅ | No cross-domain internal import violations found in changed code. |
| Dependency direction | ✅ | Direction remains `server -> configuration` and internal server modules only; no infrastructure-to-business reversal observed. |
| Domain.md updated | ❌ | `configuration/domain.md` and `auth/domain.md` are stale versus phase outcomes (F002, F003). |
| Registry current | ✅ | `docs/domains/registry.md` includes server/auth domain entries. |
| No orphan files | ❌ | Domain manifest in plan does not map all changed files from computed diff (F006). |
| Map nodes current | ❌ | Domain map still marks server as planned though phase implementation is active (F005). |
| Map edges current | ❌ | Domain map edge label retains RLS wording inconsistent with no-RLS phase direction (F004). |
| No circular business deps | ✅ | No business-domain cycle introduced in current map relationships. |
| Concepts documented | ⚠️ | Configuration concepts table missing new server config concepts (F009). |

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| FastAPI app factory lifecycle orchestration | MCP server bootstrap pattern (protocol server only) | cli-presentation (informal) | Proceed |
| Async PostgreSQL connection-pool contract | None | server | Proceed |
| Relational schema bootstrap for graph persistence | Existing graph persistence capability in graph-storage | graph-storage | Extend (document ownership boundary) |
| HTTP health endpoint | CLI doctor diagnostics (non-HTTP) | cli-presentation (informal) | Proceed |
| ServerDatabaseConfig typed model | Existing typed config model pattern in configuration | configuration | Extend |

### E.4) Testing & Evidence

**Coverage confidence**: 44%

| AC | Confidence | Evidence |
|----|------------|----------|
| AC22 | 20% | Spec requires FastAPI + PostgreSQL + Redis stack (`server-mode-spec.md:132-134`), but compose file contains only `db` and `server` (`docker-compose.yml:10-53`). |
| AC23 | 68% | Health route implements connected/degraded behavior (`src/fs2/server/routes/health.py:11-49`); tests verify endpoint status/shape and degraded mode (`tests/server/test_health.py:63-89`) but not explicit connected payload assertion. |

### E.5) Doctrine Compliance

N/A — no project-rules files were found under `/Users/jordanknight/substrate/fs2/028-server-mode/docs/project-rules/`.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC22 | Server deployable as single Docker Compose stack (FastAPI + PostgreSQL + Redis) | Compose file currently defines FastAPI + PostgreSQL only; no Redis service present. | 20 |
| AC23 | `/health` returns server status, DB connectivity, graph count | Route implementation present; tests partially verify behavior but omit explicit connected payload assertion. | 68 |

**Overall coverage confidence**: 44%

## G) Commands Executed

```bash
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager status --short
git --no-pager log --oneline -15
mkdir -p /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews
git --no-pager diff HEAD^..HEAD > /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/_computed.diff
git --no-pager diff --name-status HEAD^..HEAD > /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/_manifest.txt
```

Subagent analyses were run in parallel for: implementation quality, domain compliance, anti-reinvention, testing evidence, and doctrine/rules validation.

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md
**Phase**: Phase 1: Server Skeleton + Database
**Tasks dossier**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-1-server-skeleton-database/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-1-server-skeleton-database/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/review.phase-1-server-skeleton-database.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/Dockerfile | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docker-compose.yml | A | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md | A | auth | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md | A | configuration | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | A | cross-domain | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md | A | graph-storage | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/registry.md | A | cross-domain | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/search/domain.md | A | search | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/external-research/database-selection.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/external-research/management-dashboard.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/external-research/remote-cli-protocol.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/external-research/synthesis.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/research-dossier.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md | A | planning | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-1-server-skeleton-database/execution.log.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-1-server-skeleton-database/tasks.fltplan.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-1-server-skeleton-database/tasks.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/workshops/001-database-schema.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/workshops/002-prototype-validation.md | A | planning | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/pyproject.toml | M | cross-domain | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/scripts/scratch/pgvector_prototype.py | A | tooling | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/cli/watch.py | M | cli-presentation (informal) | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/config/objects.py | M | configuration | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/__init__.py | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/app.py | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/database.py | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/__init__.py | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/health.py | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/schema.py | A | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/__init__.py | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_database.py | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_health.py | A | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_schema.py | A | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/uv.lock | M | cross-domain | No |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/028-server-mode/docker-compose.yml | Add Redis service and verify full stack startup evidence for AC22. | AC22 requires FastAPI + PostgreSQL + Redis compose stack. |
| 2 | /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_health.py | Add explicit connected success-path assertion for AC23 payload. | Current tests check shape/degraded mode but not explicit success payload. |
| 3 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md | Add server config contracts/history/concepts entries. | Domain docs are stale after adding new public config models. |
| 4 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md | Align auth domain text with no-RLS architecture direction. | Current auth docs still mandate RLS, conflicting with phase decisions. |
| 5 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | Update server status and auth edge labels to current architecture. | Map metadata and dependency labels are outdated. |
| 6 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md | Expand Domain Manifest coverage or scope the phase diff to mapped files. | No-orphan mapping requirement currently fails. |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/configuration/domain.md | New contracts (`ServerDatabaseConfig`, `ServerStorageConfig`) in Contracts/History/Concepts sections. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md | No-RLS-aligned purpose/boundary/contracts/history language. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | Active server node status and non-RLS auth dependency labeling. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md | Complete file-to-domain mapping for all files in phase diff. |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md --phase "Phase 1: Server Skeleton + Database"
