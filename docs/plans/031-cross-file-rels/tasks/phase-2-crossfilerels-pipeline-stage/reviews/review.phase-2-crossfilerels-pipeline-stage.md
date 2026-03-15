# Code Review: Phase 2: CrossFileRels Pipeline Stage

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md
**Phase**: Phase 2: CrossFileRels Pipeline Stage
**Date**: 2026-03-13
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

The phase's core happy path is not yet reliable: project routing is mis-scoped, real Serena reference payloads will not map back to fs2 node IDs, and the new pool is not actually used in parallel.

**Key failure areas**:
- **Implementation**: `CrossFileRelsStage` resolves everything through the first detected project root and parses documented Serena reference objects into lookup keys that cannot match fs2 qualified names.
- **Domain compliance**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py` mixes service orchestration with concrete FastMCP/subprocess infrastructure instead of depending on adapter contracts.
- **Testing**: The committed tests never exercise successful `CrossFileRelsStage.process()` orchestration, pool lifecycle, or multi-project routing, so the main regressions escaped.

## B) Summary

The lightweight pieces of the phase landed cleanly: `PipelineContext.cross_file_edges` and `StorageStage`'s write path are covered by focused tests, and both the focused suite (`40 passed`) and a fresh repo-wide run (`1608 passed, 25 skipped, 341 deselected`) succeeded. The problems are in the new stage's actual runtime behavior, not in baseline repository stability.

Static review plus direct repo probing show the implementation does not yet match the phase contract. Running `detect_project_roots('.')` in this repository returned six roots, with three `.venv` sample roots and `tests/fixtures/samples/json` ahead of the repo root; `process()` then starts exactly one Serena pool for `project_roots[0]`, while `shard_nodes()` ignores project grouping entirely. Separately, workshop `002-serena-benchmarks.md` documents `find_referencing_symbols` payloads as objects containing `name_path`, but the production parser stringifies those objects and then looks them up as qualified names, which means real results will not resolve to fs2 node IDs.

Domain/document governance is only partly applicable here: this repository has no `docs/domains/` or `docs/project-rules/` trees, so domain validation was anchored to `AGENTS.md`, `CLAUDE.md`, and the plan/spec manifest tables. Anti-reinvention checks were otherwise clean: the new code mostly adapts existing `scripts/serena-explore/` prototypes rather than recreating an existing production capability.

## C) Checklist

**Testing Approach: Hybrid**

For Hybrid:
- [ ] TDD-designated orchestration/pool behavior shows explicit RED → GREEN evidence
- [x] Lightweight validation covers `PipelineContext` field wiring and `StorageStage` edge writing
- [ ] Critical phase paths are covered by automated tests (successful `CrossFileRelsStage.process()` and multi-project routing are not)
- [ ] Acceptance criteria are actively verified (`AC1` and `AC7` remain unproven)

Universal (all approaches):
- [x] Only in-scope phase implementation files changed
- [ ] Linters/type checks clean (targeted `uv run ruff check ...` fails on touched files)
- [ ] Domain compliance checks pass fully (service layer still owns concrete Serena/FastMCP infrastructure)

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:125-160,445-477,667-697 | correctness | Project detection and sharding do not implement the promised per-project routing: ignored/vendor roots are detected, only the first root gets a Serena pool, and `shard_nodes()` ignores `project_roots`. | Derive scan roots from `ScanConfig.scan_paths`, filter to real scan scope, assign nodes to their most-specific `ProjectRoot`, and resolve each project with its own pool/port range and root-relative paths. |
| F002 | HIGH | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:543-557,587-603 | correctness | The production parser stringifies Serena reference objects and then looks them up as fs2 qualified names, so documented real responses will not map back to node IDs. | Extract `name_path` from Serena response objects, normalize it to the lookup key format, and add tests using the documented response shape. |
| F003 | HIGH | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:299-337,705-714 | performance | The stage never uses the Serena pool concurrently and still schedules work against ports that failed readiness, so the 20-instance design does not deliver the benchmarked speedup or robust partial-start behavior. | Resolve only on ready ports and run per-instance micro-batches with one async gather across the pool instead of serial `asyncio.run()` calls per port. |
| F004 | HIGH | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py:466-520 | testing | The committed tests cover helper functions and the skip path, but not the successful `CrossFileRelsStage.process()` orchestration, pool lifecycle, cleanup, or multi-project routing claimed in the dossier/execution log. | Add fake-backed success-path tests for orchestration, partial startup, cleanup, and multi-project routing, then refresh the execution evidence. |
| F005 | HIGH | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:168-219,227-417,505-562 | domain-compliance | The new service-layer stage owns concrete subprocess, HTTP readiness, PID-file, and FastMCP client code directly, bypassing the repository's services→adapter contract boundary. | Move `DefaultSubprocessRunner`, `SerenaPool`, and `DefaultSerenaClient` to `core/adapters/` as concrete implementations. Protocols stay in the stage file. |

## E) Detailed Findings

### E.1) Implementation Quality

1. **F001 — Project routing is mis-scoped and incomplete**
   - `detect_project_roots()` walks every marker file under the derived `scan_root` without honoring scan scope. In this repository, `uv run python - <<'PY' ... detect_project_roots('.') ...` returned six roots, with `.venv` sample directories and `tests/fixtures/samples/json` ahead of the real repo root.
   - `process()` then starts exactly one Serena pool for `project_roots[0].path`, and `shard_nodes()` ignores `project_roots` entirely. Nodes from secondary roots therefore run against the wrong Serena project, and unmatched files are never skipped/reportable as the task dossier requires.
   - The scan-root derivation itself is fragile: `scan_root = Path(context.graph_path).parent.parent` ignores `context.scan_config.scan_paths`, so a custom graph path can silently change what gets scanned for project markers.

2. **F002 — Real Serena payloads will not resolve to fs2 node IDs**
   - Workshop `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/workshops/002-serena-benchmarks.md:273-275` documents `find_referencing_symbols` payloads as `{file_path: {symbol_kind: [{name_path, body_location, content_around_reference}]}}`.
   - `DefaultSerenaClient.find_referencing_symbols()` instead converts each reference object into `str(sym)`, and `resolve_node_batch()` looks that string up in `node_lookup[(file_path, qualified_name)]`.
   - The simplified fake tests use string symbols like `"caller"`, so they pass while the documented real payload shape would produce zero (or near-zero) edges.

3. **F003 — Multiple Serena instances are started, but not used as a concurrent pool**
   - Workshop `002-serena-benchmarks.md` found that one instance cannot be parallelized internally, and the speedup comes from driving multiple instances concurrently.
   - The current `process()` implementation iterates `for port, port_nodes in shards.items()` and calls `asyncio.run(resolve_node_batch(...))` per batch, while `resolve_node_batch()` awaits each node sequentially. That keeps the stage effectively serial.
   - If `wait_ready()` reports a partial failure, the stage still shards over `pool.ports` rather than a ready-port subset and then swallows connection errors inside `resolve_node_batch()`, which can leave `cross_file_rels_skipped = False` even when resolution barely ran.

### E.2) Domain Compliance

Repository note: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/` does not exist, so domain validation relied on `AGENTS.md`, `CLAUDE.md`, and the phase plan/spec manifest tables.

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | All changed implementation files remain under the phase-declared trees (`core/services`, `core/services/stages`, `tests`, phase docs). |
| Contract-only imports | ✅ | No cross-domain internal import violation was introduced between fs2 domains. |
| Dependency direction | ❌ | `core/services/stages/cross_file_rels_stage.py` owns concrete FastMCP and subprocess behavior rather than depending on adapter contracts. Must use adapters per project doctrine. |
| Domain.md updated | N/A | No `docs/domains/<slug>/domain.md` files exist in this repository. |
| Registry current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/registry.md` does not exist. |
| No orphan files | ✅ | The phase's code/test files align with the dossier and execution log. |
| Map nodes current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` does not exist. |
| Map edges current | N/A | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/domains/domain-map.md` does not exist. |
| No circular business deps | N/A | No formal domain map exists to validate topology separately. |
| Concepts documented | N/A | No domain-doc Concepts tables exist in this repository. |

Retained domain finding:

- **F005 — Service-layer stage owns concrete Serena infrastructure**
  - The file placement is fine, but the content crosses the declared boundary: the stage embeds subprocess management, HTTP readiness probing, PID-file cleanup, and FastMCP transport code directly.
  - That makes `core/services` own integration details that repository guidance places behind adapters.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| `CrossFileRelsStage` orchestration | None | None | proceed |
| `SerenaPool` | `scripts/serena-explore/benchmark_multi.py:start_serena_instances,wait_for_instances,stop_instances` | scripts/serena-explore | extend |
| `detect_project_roots()` | `scripts/serena-explore/test_multi_lang.py:detect_project_roots` | scripts/serena-explore | extend |
| Serena client / reference resolution | `scripts/serena-explore/benchmark_multi.py:query_node`, `scripts/serena-explore/test_multi_lang.py:query_symbols` | scripts/serena-explore | extend |
| `build_node_lookup()` | None | None | proceed |

No retained duplication finding was warranted; the new work mainly promotes benchmark/prototype logic into production code.

### E.4) Testing & Evidence

**Coverage confidence**: 35%

Focused validation re-run:
- `uv run python -m pytest -q tests/unit/services/stages/test_cross_file_rels_stage.py tests/unit/services/test_storage_stage.py` → `40 passed in 2.11s`
- `uv run python -m pytest -q` → `1608 passed, 25 skipped, 341 deselected in 41.85s`

| AC | Confidence | Evidence |
|----|------------|----------|
| AC1 | 18% | Helper-level tests prove edge tuples can be built and `StorageStage` can persist supplied edges, but there is no successful `CrossFileRelsStage.process()` test, and findings **F001-F002** show the actual happy path would misroute or fail to map real Serena results. |
| AC4 | 84% | `TestGracefulSkip.test_skips_when_serena_not_available` verifies the skip path, metrics, and zero-edge outcome; helper tests cover PATH detection; full suite remains green. The info log itself is not asserted. |
| AC7 | 5% | No phase-local benchmark output was captured, and finding **F003** shows the implementation does not execute the multi-instance pattern that produced the workshop's 14.3x speedup. |

Retained testing finding:

- **F004 — Execution evidence overstates what the tests prove**
  - `execution.log.md` claims pool lifecycle coverage and phase completion.
  - The committed tests only cover helpers, payload mapping with simplified fakes, and the Serena-unavailable skip path.

### E.5) Doctrine Compliance

N/A for `docs/project-rules/*` — this repository does not contain `rules.md`, `idioms.md`, `architecture.md`, `constitution.md`, or `harness.md`. `AGENTS.md` and `CLAUDE.md` were therefore used as the governing doctrine.

Additional note: targeted `uv run ruff check src/fs2/core/services/pipeline_context.py src/fs2/core/services/stages/storage_stage.py src/fs2/core/services/stages/cross_file_rels_stage.py tests/unit/services/stages/test_cross_file_rels_stage.py tests/unit/services/test_storage_stage.py` failed on touched files, so the lint checklist is currently open even aside from the retained findings.

### E.6) Harness Live Validation

N/A — no harness configured. `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/project-rules/harness.md` is absent, and the plan records harness as not applicable for this feature.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC1 | `fs2 scan` with Serena produces `edge_type="references"` edges | Helper tests for `resolve_node_batch()` plus `StorageStage` reference-edge persistence; **no successful orchestration test and findings F001-F002 contradict the happy path** | 18% |
| AC4 | Scan without Serena produces no errors and skips cleanly | `TestGracefulSkip.test_skips_when_serena_not_available`; availability helper tests; full suite pass | 84% |
| AC7 | Resolution completes in under 60 seconds for ≤5000 nodes | Workshop `002-serena-benchmarks.md` shows the target for a concurrent design, but this phase's implementation does not yet follow that design and no benchmark output was recorded in the phase evidence | 5% |

**Overall coverage confidence**: 35%

## G) Commands Executed

```bash
git --no-pager diff --stat
git --no-pager diff --staged --stat
git --no-pager status --short
git --no-pager log --oneline -10

git --no-pager show --stat --summary 6ae5d21
git --no-pager rev-parse 6ae5d21^
git --no-pager diff --name-status 1bd864b..6ae5d21

git --no-pager diff 1bd864b..6ae5d21 > /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-2-crossfilerels-pipeline-stage/reviews/_computed.diff

git --no-pager diff --unified=3 1bd864b..6ae5d21 -- \
  src/fs2/core/services/pipeline_context.py \
  src/fs2/core/services/stages/storage_stage.py \
  src/fs2/core/services/stages/cross_file_rels_stage.py \
  tests/unit/services/stages/test_cross_file_rels_stage.py \
  tests/unit/services/test_storage_stage.py | sed -n '1,260p'

uv run python -m pytest -q tests/unit/services/stages/test_cross_file_rels_stage.py tests/unit/services/test_storage_stage.py
uv run ruff check src/fs2/core/services/pipeline_context.py src/fs2/core/services/stages/storage_stage.py src/fs2/core/services/stages/cross_file_rels_stage.py tests/unit/services/stages/test_cross_file_rels_stage.py tests/unit/services/test_storage_stage.py
uv run python -m pytest -q

uv run python - <<'PY'
from fs2.core.services.stages.cross_file_rels_stage import detect_project_roots
roots = detect_project_roots('.')
print(f'count={len(roots)}')
for root in roots[:10]:
    print(root.path, root.languages)
PY
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md
**Phase**: Phase 2: CrossFileRels Pipeline Stage
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-2-crossfilerels-pipeline-stage/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-2-crossfilerels-pipeline-stage/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-2-crossfilerels-pipeline-stage/reviews/review.phase-2-crossfilerels-pipeline-stage.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md | Modified | docs/plans | Keep multi-project promises aligned with the eventual implementation/fix scope |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-2-crossfilerels-pipeline-stage/tasks.md | Added | docs/plans | Keep dossier expectations aligned with fixes |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-2-crossfilerels-pipeline-stage/execution.log.md | Added | docs/plans | Refresh evidence after adding orchestration/pool tests |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/pipeline_context.py | Modified | core/services | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/storage_stage.py | Modified | core/services/stages | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py | Added | core/services/stages | Fix required |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/test_storage_stage.py | Modified | tests | None |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py | Added | tests | Expand to cover happy-path orchestration/pool behavior |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py | Implement scan-root scoping and per-project routing/sharding instead of resolving everything through `project_roots[0]` | Current project detection picks `.venv`/fixture roots ahead of the repo root and `shard_nodes()` ignores project boundaries, so cross-file edges can be resolved against the wrong Serena project |
| 2 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py | Parse real Serena reference objects (`name_path`) into lookup keys instead of stringifying dicts | Documented `find_referencing_symbols` responses will not map to fs2 node IDs as implemented |
| 3 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py | Use the Serena pool concurrently and resolve only against ready ports | The current stage is effectively serial and can silently degrade when some instances fail readiness |
| 4 | /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py | Add success-path orchestration, pool lifecycle, cleanup, and multi-project tests | The main bugs escaped because only helper functions and the skip path are covered |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-spec.md | The spec promises a per-project Serena pool; keep that promise only if the code is fixed to match it |
| /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/tasks/phase-2-crossfilerels-pipeline-stage/execution.log.md | Pool lifecycle / happy-path orchestration evidence is overstated and should be refreshed after tests land |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/031-cross-file-rels/cross-file-rels-plan.md --phase "Phase 2: CrossFileRels Pipeline Stage"
