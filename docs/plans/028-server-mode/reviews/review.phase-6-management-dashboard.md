# Code Review: Phase 6: Management Dashboard

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md
**Phase**: Phase 6: Management Dashboard
**Date**: 2026-03-06
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

Phase 6 landed a usable dashboard shell and all 90 selected server tests passed during review, but the phase is still not review-ready: graph polling never disengages once started, AC18/AC24 are only partially implemented, and the domain artifacts still describe an auth integration the codebase has not actually reached.

**Key failure areas**:
- **Implementation**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/list.html`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py`, and `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/middleware.py` still miss the stop-polling, tenant-management, and tenant/graph logging behaviors promised for Phase 6.
- **Domain compliance**: `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md`, and `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md` still model auth as a live server dependency even though auth remains deferred in code.
- **Reinvention**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py` duplicates upload/list/delete/tenant-bootstrap logic already present in `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py`.
- **Testing**: `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/execution.log.md` overstates completion; upload POST, polling-stop behavior, and the full AC24 log payload are not actually proven.

## B) Summary

Phase 6 delivers a meaningful dashboard slice: the routes/templates exist, the access-log middleware is wired into the app, and both targeted and full server pytest runs passed during review (`24 passed` for the new dashboard/middleware tests; `90 passed, 2 deselected` for `tests/server`). However, the current implementation still diverges from the approved phase contract in material, user-visible ways. The biggest gaps are endless HTMX polling after ingest settles, the still-missing tenant creation promised by AC18, and access logs that omit the tenant/graph context required by AC24. Domain artifacts also need reconciliation because the code keeps temporary API-key logic in the server domain while the docs still describe a live AuthService/middleware dependency (overall coverage confidence: 37%).

## C) Checklist

**Testing Approach: Hybrid**

For Hybrid:
- [ ] Core validation tests exist for upload POST, polling-stop behavior, and access-log field completeness
- [x] Lightweight route/template checks exist for dashboard pages, graph list/delete, key CRUD, and basic middleware logging
- [ ] Acceptance criteria AC5, AC18, AC19, and AC24 are backed by concrete evidence

Universal (all approaches):
- [x] Only in-scope files changed
- [ ] Linters/type checks clean (if applicable)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/list.html:16-22 | correctness | Graph-list polling never stops once it starts. | Return/re-render the polling container (or update its attributes out-of-band) so `hx-trigger` is removed when `has_pending` becomes false, and cover the stop condition in tests. |
| F002 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md:127-135 | scope | AC18 still promises tenant creation, but Phase 6 only ships default-tenant API-key CRUD. | Either implement tenant creation UI/routes/tests for Phase 6 or formally defer tenant management by updating the spec/plan/phase artifacts before re-review. |
| F003 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/middleware.py:23-57 | correctness | Structured access logs omit the tenant and graph fields required by AC24/T007. | Add tenant and graph identifiers to the log payload (default tenant if needed) and extend the middleware tests to assert them. |
| F004 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:42-47 | domain-compliance | Domain artifacts still model auth as a live server dependency even though auth remains deferred. | Rebaseline `docs/domains/server/domain.md`, `docs/domains/auth/domain.md`, and `docs/domains/domain-map.md` so they describe planned auth extraction and temporary server-owned API-key logic accurately. |
| F005 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_dashboard.py:256-362 | testing | Phase evidence does not actually prove upload POST, polling-stop, or full AC24 logging behavior. | Add upload success/failure/oversize tests, polling-stop assertions, and tenant/graph logging checks; then record exact pytest commands/output in the execution log. |
| F006 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py:76-90 | error-handling | Dashboard home silently converts database failures into misleading zero counts. | Log the failure and surface an explicit error state (or fail the request) instead of swallowing exceptions and rendering fake healthy counters. |
| F007 | LOW | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py:35-239 | pattern | Dashboard graph list/upload/delete logic duplicates existing API-route logic instead of sharing helpers. | Extract shared server helpers (for tenant bootstrap and graph CRUD/query shaping) or route both surfaces through one internal service path to avoid drift. |

## E) Detailed Findings

### E.1) Implementation Quality

- **F001 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/list.html:16-22`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/_table.html:1-49`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/tasks.md:176`
  - `has_pending` only controls the initial wrapper render. Once the page first loads with a pending graph, `#graph-table-container` keeps its `hx-get`/`hx-trigger` attributes forever because `/dashboard/graphs/table` returns only a `<table>` fragment and never updates the wrapper attributes.
  - That violates T004 / DYK-P6-09’s “stops when all graphs settled” contract and leaves unnecessary 5-second polling running indefinitely.
  - **Fix**: return a polling-container fragment (or update the container out-of-band) so HTMX attributes are added/removed based on `has_pending`, then add settled-state regression coverage.

- **F002 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md:127-135`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py:125-137`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/settings/keys.html:37-95`
  - AC18 still says “A server operator can create tenants and generate API keys through the dashboard,” but the shipped dashboard only exposes API-key CRUD and silently bootstraps one hard-coded default tenant.
  - The phase dossier documents the Phase 2 auth gap, but the governing artifacts were never reconciled, so the implemented feature and the approved contract still disagree.
  - **Fix**: either implement tenant creation UI/routes/tests for Phase 6 or formally defer tenant management by updating the spec/plan/phase artifacts before re-review.

- **F003 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/middleware.py:23-57`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/tasks.md:179`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md:135`
  - `AccessLogMiddleware` emits method/path/status/duration/content_length/query, but it never records the tenant or graph context that T007 and AC24 require for monitoring.
  - The accompanying tests only assert method/path/status/duration, so the gap is both implemented and unverified.
  - **Fix**: add tenant and graph identifiers to the structured log payload (default tenant if that is still the active model) and extend the caplog assertions accordingly.

- **F006 (MEDIUM)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py:76-90`
  - `dashboard_home()` catches every exception, logs nothing, and renders `0` ready / `0` ingesting graphs as though the system were healthy.
  - That makes a database outage or query failure look like an empty but healthy dashboard.
  - **Fix**: log the exception and render an explicit error state (or fail the request) rather than silently converting failures into zero counts.

- **F007 (LOW)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py:35-239`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py:27-193`
  - The dashboard duplicates graph-list shaping, upload streaming, delete SQL, and default-tenant bootstrapping already present in the API routes, despite the phase dossier calling for shared-path reuse.
  - This is not a correctness blocker today, but it increases drift risk and already left `_ensure_default_tenant()` “shared” only within dashboard routes.
  - **Fix**: extract shared server helpers or route both surfaces through one internal service path.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New source files land under `src/fs2/server/dashboard/` / `src/fs2/server/`, matching the phase dossier. |
| Contract-only imports | ✅ | No new Python module reaches into another domain’s private internals; the new code stays within server/config/ingestion surfaces. |
| Dependency direction | ✅ | No reverse business/infrastructure dependency or business-cycle regression was introduced. |
| Domain.md updated | ❌ | `server/domain.md` and `auth/domain.md` still disagree with the current temporary Phase 6 ownership split and the absence of auth middleware. |
| Registry current | ✅ | `docs/domains/registry.md` still correctly lists `server` as active and `auth` as planned; no new formal domain was added in this phase. |
| No orphan files | ✅ | All changed code files map to the server domain; the plan/execution artifacts are review artifacts rather than orphan domain code. |
| Map nodes current | ❌ | The server/auth node labels and health summary still describe an AuthService/RLS shape that the codebase does not yet implement. |
| Map edges current | ❌ | `server --> auth | AuthService + API key middleware` is still shown as a live solid edge even though the server code does not consume any auth-domain contract. |
| No circular business deps | ✅ | No circular business dependency exists in the current map. |
| Concepts documented | ✅ | `docs/domains/server/domain.md` includes Phase 6 concepts for dashboard administration, access logging, and API-key management. |

- **F004 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:42-47`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md:66-67`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md:11-22`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md:35-56`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md:11-19`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md:42-58`
  - The domain map and both server/auth domain docs still describe AuthService/auth middleware as live server dependencies and current auth contracts, but `src/fs2/auth/` does not exist and Phase 6 explicitly keeps API-key CRUD inline in `src/fs2/server/dashboard/routes.py` with enforcement disabled.
  - This leaves the documented domain topology materially ahead of the code and makes the current dependency boundary look healthier/more formalized than it really is.
  - **Fix**: rebaseline the server/auth docs and domain map so auth is clearly marked as planned/deferred and the server domain’s temporary ownership of minimal API-key logic is explicit.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| Dashboard graph upload route | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py` (`upload_graph()`) | server | ⚠ Extend/extract the existing upload path/helper instead of duplicating file streaming + tenant bootstrap. |
| Dashboard graph list helper (`_fetch_graphs`) | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py` (`list_graphs()`) | server | ⚠ Extend/extract shared query shaping to avoid drift between API and dashboard views. |
| Dashboard graph delete route | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py` (`delete_graph()`) | server | ⚠ Centralize shared delete logic or a common internal helper. |
| AccessLogMiddleware | None | — | ✅ Proceed — genuinely new capability, not duplicate functionality. |

### E.4) Testing & Evidence

**Spec approach**: Hybrid  
**Observed evidence profile**: Mostly lightweight/static.  
**Coverage confidence**: 37%

**Evidence gaps retained in review**:
- **HIGH** — `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_dashboard.py:256-362` exercises the upload page and key CRUD, but not multipart upload POST success/failure/oversize behavior.
- **HIGH** — `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_middleware.py:80-142` proves only method/path/status/duration fields, not the tenant/graph contract required by AC24.
- **MEDIUM** — No test demonstrates that polling stops once all graphs settle; the suite only verifies the table fragment and ingesting badge.
- **MEDIUM** — `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/execution.log.md:117-120` reports pass counts, but the per-task sections do not capture concrete command/output evidence for T002-T007.

| AC | Confidence | Evidence |
|----|------------|----------|
| AC5 | 35% | `upload.html` contains XHR progress UI and `graphs/list.html` + `graphs/_table.html` implement polling; tests only cover ingesting badge and table fragment, not upload POST or polling stop. |
| AC18 | 15% | `test_api_key_generation` / `test_api_key_revoke` prove API-key CRUD only. No tenant-creation route, UI, or test exists. |
| AC19 | 20% | The upload form page renders, but there is no passing test for successful multipart POST, rejection paths, or size-limit behavior. |
| AC20 | 60% | Graph list HTML, empty state, ingesting badge, and table fragment are covered; the stop-polling condition is still unproven. |
| AC21 | 65% | Dashboard DELETE returns 200/404 and removes the fake graph entry, but related-data cascade and browser-side confirmation behavior are not proven. |
| AC24 | 25% | Middleware logging is wired and tested for method/path/status/duration, but tenant/graph fields are missing from both the code and the assertions. |

### E.5) Doctrine Compliance

N/A — no `docs/project-rules/*.md` files were present in the repository, so there was no project-rules doctrine bundle to validate against.

### E.6) Harness Live Validation

N/A — no harness configured (`docs/project-rules/harness.md` not found).

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC5 | Dashboard shows ingestion progress | Upload-progress UI exists in `upload.html`; polling UI exists in `graphs/list.html`; tests only cover ingesting badge + table partial. | 35% |
| AC18 | Operator can create tenants + API keys | Key generation/revoke tested; tenant creation still absent and only a default tenant is auto-created. | 15% |
| AC19 | Tenant can upload graph pickles via dashboard with progress feedback | Upload form renders, but POST success/error/oversize behavior is untested. | 20% |
| AC20 | Tenant can view graphs + ingestion progress | Graph list, empty state, and ingesting badge are covered; stop-polling behavior is not. | 60% |
| AC21 | Tenant can delete a graph and associated data | Dashboard DELETE happy path + 404 path tested; cascade/browser confirmation not proven. | 65% |
| AC24 | Structured request metrics are logged | Middleware is mounted and tested for method/path/status/duration, but tenant/graph fields are missing. | 25% |

**Overall coverage confidence**: 37%

## G) Commands Executed

```bash
git --no-pager status --short
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager log --oneline -15
git --no-pager log --oneline -- docs/plans/028-server-mode/tasks/phase-6-management-dashboard src/fs2/server/dashboard src/fs2/server/middleware.py tests/server/test_dashboard.py tests/server/test_middleware.py src/fs2/server/schema.py src/fs2/server/app.py | head -20
git --no-pager diff --name-status 4106eb0..HEAD
git --no-pager diff --stat 4106eb0..HEAD
git --no-pager diff 4106eb0..HEAD > docs/plans/028-server-mode/reviews/_computed.diff
uv run pytest tests/server/test_dashboard.py tests/server/test_middleware.py -q
uv run pytest tests/server -q
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md
**Phase**: Phase 6: Management Dashboard
**Tasks dossier**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/review.phase-6-management-dashboard.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md | Modified | server-doc | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/execution.log.md | Added | plan-artifact | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/tasks.fltplan.md | Added | plan-artifact | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/tasks.md | Added | plan-artifact | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/app.py | Modified | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/__init__.py | Added | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py | Added | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/base.html | Added | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/_table.html | Added | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/list.html | Added | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/upload.html | Added | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/index.html | Added | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/settings/keys.html | Added | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/middleware.py | Added | server | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/schema.py | Modified | server | No |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_dashboard.py | Added | server-test | Yes |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_middleware.py | Added | server-test | Yes |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/list.html; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/graphs/_table.html; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_dashboard.py | Make HTMX polling stop when `has_pending` becomes false. | The current wrapper keeps polling every 5s forever after the first pending render. |
| 2 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/tasks.md; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/templates/settings/keys.html | Reconcile tenant-management scope with AC18 (implement it or formally defer it). | The shipped dashboard only manages keys for a hard-coded default tenant, but the governing artifacts still promise tenant creation. |
| 3 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/middleware.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_middleware.py | Add tenant and graph context to structured access logs and test it. | AC24/T007 require those fields, and they are currently missing from both the code and the assertions. |
| 4 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | Update domain docs/map to reflect deferred auth and temporary server-owned API-key CRUD. | Current domain artifacts still describe active AuthService/middleware contracts that do not exist in the codebase. |
| 5 | /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_dashboard.py; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-6-management-dashboard/execution.log.md | Add concrete upload/polling/logging evidence and sync the execution log. | The review can confirm page rendering and happy-path key CRUD, but not upload POST, oversize handling, polling stop, or the full logging contract. |
| 6 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/dashboard/routes.py | Stop swallowing dashboard-home database errors. | Rendering zero counts on DB failure hides operational problems and undermines the dashboard’s status view. |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|-----------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md | Remove stale auth/RLS language and document the temporary server-owned API-key CRUD added in Phase 6. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/auth/domain.md | Mark AuthService/auth middleware/source location as planned/deferred until `src/fs2/auth/` actually exists. |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | Convert the live server→auth edge to planned/deferred and refresh the server/auth node labels + health summary. |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md --phase 'Phase 6: Management Dashboard'
