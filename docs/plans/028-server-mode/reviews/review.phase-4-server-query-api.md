# Code Review: Phase 4: Server Query API

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md
**Phase**: Phase 4: Server Query API
**Date**: 2026-03-06
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

Phase 4 still has unmitigated HIGH findings: the tree/search/get-node API does not yet achieve local parity, semantic/model-validation behavior from T006 is not implemented, required core tests are missing, and the server imports a search-internal implementation rather than a public contract.

**Key failure areas**:
- **Implementation**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py` duplicates and diverges from local tree/search behavior, and semantic requests silently degrade instead of enforcing the promised validation path.
- **Domain compliance**: `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py` imports a search-internal module directly, while the touched domain docs/map do not yet describe a stable public boundary for the new matcher/router composition.
- **Reinvention**: tree orchestration and search-envelope logic were reimplemented in the route layer instead of reusing `TreeService` / `SearchResultMeta`, and the duplicates already drift from local behavior.
- **Testing**: core Phase 4 verification is incomplete — `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_pgvector_matcher.py` is missing, `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_store_pg.py` has no Phase 4 coverage, and AC10 has no benchmark evidence.

## B) Summary

Phase 4 establishes the main route and SQL scaffolding, but the implementation is not yet review-ready. The most serious issue is parity drift: the tree endpoint does not reproduce local expansion semantics, and the get-node/search serializers still differ from the existing local outputs. Semantic search/model-validation work is only partially wired — there is no `model` validation path, no 422 mismatch branch, and no configured embedding adapter in `create_app()`. Domain documentation was partially updated, but the server still depends on a search-internal implementation and the proof for AC6-AC10 is only partial (overall coverage confidence: 33%).

## C) Checklist

**Testing Approach: Hybrid**

For Hybrid:
- [ ] TDD-level coverage exists for server-core query logic (`PostgreSQLGraphStore`, `PgvectorSemanticMatcher`, semantic routing/model validation)
- [ ] Lightweight verification covers HTTP glue and response serialization paths
- [ ] Acceptance criteria AC6-AC10 are backed by concrete evidence

Universal (all approaches):
- [x] Only in-scope files changed
- [ ] Linters/type checks clean (targeted `ruff check` currently fails on `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py`)
- [ ] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:113-291 | correctness | Tree route reimplements folder/root assembly but never expands symbol children or depth-limited hidden counts like local `TreeService`, so AC6 parity is not met. | Replace route-local tree assembly with a shared service/wrapper that preserves local tree semantics and serializer behavior. |
| F002 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:487-533 | correctness | Semantic search/model validation promised by T006 is not implemented: no `model` parameter, no 422 mismatch branch, and `semantic` silently falls back to text when no adapter is configured. | Wire the embedding adapter in `create_app()`, add explicit semantic validation/error handling, and test the 422 mismatch path. |
| F003 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_pgvector_matcher.py:missing | testing | Required Phase 4 core tests are missing (`test_pgvector_matcher.py`, Phase 4 coverage in `test_graph_store_pg.py`), and AC10 has no latency evidence despite the execution log claiming completion. | Add matcher/store/query tests plus benchmark evidence, rerun them, and update the execution log with real outputs. |
| F004 | HIGH | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:24 | contract-imports | The server imports `fs2.core.services.search.pgvector_matcher.PgvectorSemanticMatcher` directly even though the plan classifies it as search-internal and `search/__init__.py` does not export it. | Promote the matcher to a public search contract (and move any shared protocol to an interface-only module) or hide it behind an existing public search API. |
| F005 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:327-570 | correctness | Get-node/search response serialization still diverges from local behavior: get-node returns a partial custom projection, and search uses a custom folder-distribution helper instead of `SearchResultMeta`. | Reuse the existing local serializers/models (`SearchResult.to_dict`, `SearchResultMeta.compute_folder_distribution`, documented get-node shape) and add parity tests. |
| F006 | MEDIUM | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md:41-47 | domain-md | The touched server/search/graph-storage domain docs record Phase 4 history but do not fully update Contracts/Composition for the new router/matcher/store relationships, and the domain map still labels an internal search dependency as a contract edge. | Refresh `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/search/domain.md`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md`, and `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md` after the boundary decision is fixed. |

## E) Detailed Findings

### E.1) Implementation Quality

- **F001 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:113-291`
  - `_compute_folder_hierarchy()`, `_build_folder_tree()`, and `_build_pattern_tree()` duplicate local tree assembly but never call the child-expansion logic that local `TreeService` uses. For folder mode, files always come back with `children=[]`; for pattern mode, matched roots are returned flat without recursive expansion.
  - This means the remote tree response cannot match `fs2 tree` once symbol children or depth limits matter, even though `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/tasks.md` marks AC6/T001/T007 complete.
  - **Fix**: extract/reuse a parity-preserving tree service (or async wrapper over the existing logic) and assert remote/local equality in tests.

- **F002 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:487-533`, `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/app.py:40-77`
  - The route never accepts a `model` query parameter and never compares the requested model to `graphs.embedding_model`. Instead, explicit semantic requests without `query_vector` silently fall back to text when `app.state.embedding_adapter` is missing.
  - This contradicts T006, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/execution.log.md`, and the AC7/AC10 acceptance path described in the spec.
  - **Fix**: wire the embedding adapter in the app factory, reject unsupported semantic requests explicitly, and add a 422 mismatch branch with tests.

- **F005 (MEDIUM)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:327-570`
  - `_code_node_to_dict()` emits a custom subset rather than the full `fs2 get-node` shape promised by the phase doc, and `_compute_folder_distribution()` bypasses the existing `SearchResultMeta.compute_folder_distribution()` behavior.
  - This leaves get-node/search parity only partially implemented even when the underlying SQL returns the right rows.
  - **Fix**: reuse the existing result models/serializers and update the tests to compare remote vs local outputs directly.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | New files land under the declared server/search/test source trees from the Domain Manifest (`src/fs2/server/routes/query.py`, `src/fs2/core/services/search/pgvector_matcher.py`, `tests/server/test_query_api.py`). |
| Contract-only imports | ❌ | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py` imports `fs2.core.services.search.pgvector_matcher.PgvectorSemanticMatcher` directly even though `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/search/__init__.py` does not export it and the plan marks it internal. |
| Dependency direction | ✅ | No reverse imports from graph-storage/search back into server were introduced; the issue is contract surface, not the overall dependency orientation captured in the current domain map. |
| Domain.md updated | ❌ | `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md`, `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/search/domain.md`, and `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md` add history entries but do not fully refresh Contracts/Composition for the Phase 4 router/matcher/store relationships. |
| Registry current | ✅ | `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/registry.md` already lists the touched domains and no new domain was introduced in this phase. |
| No orphan files | ❌ | Planning artifacts under `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/` plus `/Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/workshops/003-remotes-cli-mcp.md` are outside the current Domain Manifest, so manifest-based orphan checks still fail. |
| Map nodes current | ✅ | `/Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md` contains the server/search/graph-storage/configuration/auth nodes involved in this phase. |
| Map edges current | ❌ | The server → search edge is labeled `SearchService + PgvectorMatcher`, but `PgvectorSemanticMatcher` is not yet a published search-domain contract/export. |
| No circular business deps | ✅ | The current domain map does not introduce a business→business cycle. |
| Concepts documented | ✅ | The touched domain docs all retain a Concepts section with minimum concept tables. |

- **F004 (HIGH)** — `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py:24`
  - The server currently depends on a search-internal implementation file instead of a documented/exported search contract.
  - `PgvectorSemanticMatcher` also imports `ConnectionProvider` from `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_pg.py`, so the public-interface story is not yet clean across the server/search/graph-storage boundary.

- **F006 (MEDIUM)** — domain artifacts drift
  - The touched domain docs partially acknowledge Phase 4 in history, but they still do not show how `app.py`, `routes/query.py`, `routes/graphs.py`, `Database`, `PostgreSQLGraphStore`, and `PgvectorSemanticMatcher` compose the new boundary.
  - The map label should be corrected once the public contract decision is made.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| Query route handlers: tree | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/tree_service.py` | graph-storage | ❌ Duplicate/extend existing tree orchestration instead of reimplementing it in the route layer |
| Query route handlers: search orchestration | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/search/search_service.py` | search | ⚠️ Extend/reuse public search contracts rather than embedding custom mode routing and serialization in the route layer |
| Search response envelope | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/models/search/search_result_meta.py` | search | ⚠️ Reuse existing folder-distribution and envelope helpers |
| PgvectorSemanticMatcher | None | None | ✅ Proceed — SQL-native matcher is a distinct server-mode capability; the issue is boundary exposure, not duplication |

### E.4) Testing & Evidence

**Coverage confidence**: 33%

**Evidence violations**:
- **HIGH** — The spec’s Hybrid strategy expects TDD-grade coverage for server-core behavior, but the diff adds only `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py`.
- **HIGH** — `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_pgvector_matcher.py` is missing and `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_store_pg.py` has no Phase 4 tree/search coverage.
- **HIGH** — AC10 has no latency benchmark output and the phase artifacts downgrade the scale target from 500K nodes (spec) to 200K+ without recorded justification.

| AC | Confidence | Evidence |
|----|------------|----------|
| AC6 | 46% | `uv run pytest tests/server -m 'not slow' -q` passed and `test_query_api.py` adds five tree endpoint tests, but none compare remote tree output against local `TreeService` output. |
| AC7 | 20% | Text mode and auto→text fallback are covered, but regex mode, semantic mode, mismatch-422 handling, and multi-graph attribution/sorting are not verified. |
| AC8 | 44% | Get-node 200/404/detail=max cases exist, but there is no full local-parity assertion for the complete `CodeNode` field set promised by the phase doc. |
| AC9 | 49% | `GET /api/v1/graphs?status=ready` exists and one test checks the envelope shape, but metadata/status-filter behavior is only lightly asserted. |
| AC10 | 9% | `/Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/search/pgvector_matcher.py` exists, but there is no matcher test file, no benchmark output, and no proof at the 500K-node spec target. |

### E.5) Doctrine Compliance

N/A — no files matched `/Users/jordanknight/substrate/fs2/028-server-mode/docs/project-rules/*.md`, so doctrine/rules validation had no project-rules artifacts to evaluate under this command.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC6 | `fs2 tree --fs2-remote <url> --graph <name>` returns the same hierarchical structure as the local graph | Tree endpoint shape/status tests exist in `/Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py`, but there is no direct local-parity comparison and the current implementation does not expand symbol children like local `TreeService`. | 46% |
| AC7 | Remote search supports single/multi/all graphs and all four modes (text, regex, semantic, auto) with local-equivalent behavior | Text mode and auto→text fallback are covered; regex mode, semantic mode, model-mismatch 422 behavior, and multi-graph attribution/sorting remain unverified and partly unimplemented. | 20% |
| AC8 | `fs2 get-node --fs2-remote <url> --graph <name> <node_id>` returns full node content identical to local get-node | Get-node basic success/404/detail=max tests exist, but no test compares the remote response to the full local `CodeNode` serialization promised in the phase doc. | 44% |
| AC9 | `fs2 list-graphs --fs2-remote <url>` shows all accessible graphs with metadata/status | The route returns metadata and one test checks `?status=ready`, but field-level assertions and negative-filter coverage are still shallow. | 49% |
| AC10 | Semantic search uses pgvector HNSW and returns results under 100ms for graphs up to 500K nodes | `pgvector_matcher.py` exists, but there is no dedicated matcher test file, no benchmark output, and no evidence at the 500K-node target. | 9% |

**Overall coverage confidence**: 33%

## G) Commands Executed

```bash
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager log --oneline -12
mkdir -p docs/plans/028-server-mode/reviews && git --no-pager diff 9ece4a3..HEAD > docs/plans/028-server-mode/reviews/_computed.diff
git --no-pager diff --name-status 9ece4a3..HEAD
uv run pytest tests/server -m 'not slow' -q
uv run ruff check src/fs2/server src/fs2/core/repos/graph_store_pg.py src/fs2/core/services/search/pgvector_matcher.py tests/server/test_query_api.py
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-spec.md
**Phase**: Phase 4: Server Query API
**Tasks dossier**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/reviews/review.phase-4-server-query-api.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md | modified | graph-storage | Update Composition for `ConnectionProvider` / `PostgreSQLGraphStore` |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/search/domain.md | modified | search | Update Composition/Contracts for `PgvectorSemanticMatcher` boundary |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md | modified | server | Add Phase 4 Contracts + Composition for query routes/app wiring |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/execution.log.md | created | planning-artifact | Correct claims and append rerun evidence after fixes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/tasks.fltplan.md | created | planning-artifact | None |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/tasks.md | created | planning-artifact | Reconcile task completion/evidence after fixes |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/workshops/003-remotes-cli-mcp.md | created | planning-artifact | None |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/repos/graph_store_pg.py | modified | graph-storage | Add/verify Phase 4 tree+search behavior and dedicated tests |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/search/pgvector_matcher.py | created | search | Add tests and clean up public boundary/protocol import |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/app.py | modified | server | Wire embedding adapter or reject unsupported semantic requests explicitly |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/graphs.py | modified | server | Extend verification if list-graphs metadata behavior changes |
| /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py | created | server | Replace duplicated tree/search logic; implement semantic validation/parity |
| /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py | created | server | Add missing semantic/regex/parity tests and clean lint failures |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py | Remove duplicated tree assembly and restore local tree parity semantics | Current remote tree output cannot match local `TreeService` behavior for child expansion/depth limits |
| 2 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/app.py | Implement real semantic model validation (`model` param, adapter wiring, 422 mismatch path) | T006/AC7 behavior is missing and currently degrades silently to text |
| 3 | /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_pgvector_matcher.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_graph_store_pg.py; /Users/jordanknight/substrate/fs2/028-server-mode/tests/server/test_query_api.py; /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/tasks/phase-4-server-query-api/execution.log.md | Add missing core tests/benchmark evidence and update logged claims | Core server/search changes are under-tested and AC10 lacks proof |
| 4 | /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/server/routes/query.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/search/__init__.py; /Users/jordanknight/substrate/fs2/028-server-mode/src/fs2/core/services/search/pgvector_matcher.py | Eliminate cross-domain internal import by exposing a public search contract or refactoring the dependency | Current server → search import violates contract-only import rules |
| 5 | /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/search/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md; /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | Refresh domain artifacts after the boundary decision and parity fixes | The docs/map currently trail the reviewed implementation |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/server/domain.md | Phase 4 Contracts + Composition for query routes, app wiring, and REST surface |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/search/domain.md | `PgvectorSemanticMatcher` composition details and a clear public-boundary decision |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/graph-storage/domain.md | `ConnectionProvider` / `PostgreSQLGraphStore` composition details for server-query execution |
| /Users/jordanknight/substrate/fs2/028-server-mode/docs/domains/domain-map.md | Correct server → search edge label after the public contract is fixed |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/028-server-mode/docs/plans/028-server-mode/server-mode-plan.md --phase 'Phase 4: Server Query API'
