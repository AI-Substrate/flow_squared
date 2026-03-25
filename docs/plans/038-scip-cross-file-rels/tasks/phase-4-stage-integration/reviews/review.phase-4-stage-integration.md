# Code Review: Phase 4: Stage Integration

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-spec.md
**Phase**: Phase 4: Stage Integration
**Date**: 2026-03-21
**Reviewer**: Automated (plan-7-v2)
**Testing Approach**: Hybrid

## A) Verdict

**REQUEST_CHANGES**

Real SCIP indexing currently produces zero stored cross-file edges, so the phase does not meet its primary acceptance goal.

**Key failure areas**:
- **Implementation**: The stage hands project-relative SCIP document paths to adapter matching against repo-relative fs2 node IDs, so real indexed projects map every reference to `None`.
- **Testing**: The targeted verification run fails the real SCIP acceptance test (`1 failed, 21 passed`), which confirms AC1 is currently broken.
- **Doctrine**: N/A — no `docs/project-rules/*.md` files exist in this repository.

## B) Summary

The phase is directionally strong: the CLI/pipeline/context wiring is coherent, domain boundaries are respected, and the Serena removal is materially complete. Domain compliance review found no import-direction or placement violations, and the reinvention pass found no genuine duplicate subsystem being introduced. However, the end-to-end behavior is currently broken for the real Python fixture: `scip-python` runs, emits a valid `index.scip`, and the adapter extracts raw edges, but the stage integration never maps those project-relative file paths back onto repo-relative fs2 node IDs. In addition, mixed incremental scans can duplicate unchanged edges, and the legacy `docs/how/user/cross-file-relationships.md` guide still documents Serena instead of the new SCIP workflow.

## C) Checklist

**Testing Approach: Hybrid**

- [x] Core validation tests present
- [ ] Critical paths covered end-to-end
- [ ] Key verification points documented for all claimed ACs
- [x] Only in-scope implementation domains changed
- [x] Linters clean (`uv run ruff check ...`)
- [x] Domain compliance checks pass

## D) Findings Table

| ID | Severity | File:Lines | Category | Summary | Recommendation |
|----|----------|------------|----------|---------|----------------|
| F001 | HIGH | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:319-333` | correctness | Real SCIP runs produce raw edges, but stage integration maps against the wrong file-path shape and stores zero edges. | Normalize SCIP document paths from project-relative to repo-relative before adapter/node-id matching, then lock it with the failing real acceptance test. |
| F002 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:277-340` | correctness | Incremental scans concatenate `reused_edges` and `fresh_edges` without deduplication even though fresh extraction reindexes unchanged files too. | Deduplicate the merged edge list or avoid reintroducing unchanged-file edges from fresh extraction. |
| F003 | MEDIUM | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/cross-file-relationships.md:1-159` | scope | The docs/how guide still instructs Serena installation/configuration, so T008's user-guide deliverable is incomplete and conflicts with the new SCIP behavior. | Rewrite the docs/how guide for SCIP or retire it and point every surfaced docs entry at the authoritative SCIP guide. |

## E) Detailed Findings

### E.1) Implementation Quality

**F001 — HIGH — repo-relative/project-relative path mismatch breaks real edge extraction**

- **Where**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:319-333`
- **What happens**: The stage runs `scip-python` successfully and then calls `adapter.extract_cross_file_edges(index_path, known_ids)`. The generated SCIP documents use project-relative paths (`handler.py`, `model.py`, `service.py`), while fs2 node IDs for the same files are repo-relative (`file:tests/fixtures/cross_file_sample/service.py`, etc.).
- **Observed evidence**:
  - Targeted command: `uv run python -m pytest -q tests/unit/services/stages/test_cross_file_rels_stage.py tests/integration/test_cross_file_acceptance.py --override-ini='addopts='`
  - Result: `1 failed, 21 passed`
  - Failing test: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_acceptance.py:40-84`
  - Additional repro: real index file contained 5 raw edges, but `adapter.extract_cross_file_edges(...)` returned `0`.
- **Why it matters**: This is the core phase objective. As shipped, real SCIP indexing can succeed while producing no persisted cross-file edges.
- **Fix**: Thread project-root context into the mapping step so `service.py` becomes `tests/fixtures/cross_file_sample/service.py` before matching, or otherwise normalize file paths consistently on both sides.

**F002 — MEDIUM — mixed incremental scans can reintroduce duplicate edges**

- **Where**: `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py:277-340`
- **What happens**: `reused_edges` are preserved for unchanged files, but `fresh_edges` are still extracted from full project indexes. The stage then assigns `context.cross_file_edges = reused_edges + fresh_edges` without deduplicating the merged list.
- **Why it matters**: This can inflate `cross_file_rels_edges`, add redundant work in storage, and violates the spirit of AC11 even if the backing graph store later collapses duplicates.
- **Fix**: Deduplicate after merge, or restrict fresh extraction to changed-file edges only.

### E.2) Domain Compliance

| Check | Status | Details |
|-------|--------|---------|
| File placement | ✅ | Modified source/test files remain in planned domains: `cli`, `core/services`, `core/services/stages`, and `tests`. |
| Contract-only imports | ✅ | Stage uses `create_scip_adapter()` factory; no direct import of adapter implementation modules from the wrong layer. |
| Dependency direction | ✅ | Observed flow remains `cli -> services -> adapters/config`; no reverse infrastructure-to-business dependency was introduced. |
| Domain.md updated | ✅ | Repository has no `docs/domains/` tree; there is no phase-specific domain document to fall out of date. |
| Registry current | ✅ | Repository has no `docs/domains/registry.md`; no new domain was introduced by this phase. |
| No orphan files | ✅ | All changed implementation files map cleanly to the plan manifest; ancillary plan/review artifacts are phase-support documentation. |
| Map nodes current | ✅ | Repository has no `docs/domains/domain-map.md`; no maintained map artifact exists to update. |
| Map edges current | ✅ | Static dependency review found no cross-domain internal import violations requiring map-edge updates. |
| No circular business deps | ✅ | No new circular business dependency is introduced by the changed source files. |
| Concepts documented | N/A | Repository has no `docs/domains/` system to update. |

Domain review result: no material domain-compliance violations found.

### E.3) Anti-Reinvention

| New Component | Existing Match? | Domain | Status |
|--------------|----------------|--------|--------|
| SCIP stage integration flow | None | core/services/stages | proceed |
| Project-config threading into scan pipeline | Existing wiring pattern reused | core/services / cli | proceed |
| Cache directory helper logic | None | core/services/stages | proceed |

Anti-reinvention result: no genuine duplicate subsystem found.

### E.4) Testing & Evidence

**Coverage confidence**: 62%

| AC | Confidence | Evidence |
|----|------------|----------|
| AC1 | 5% | `uv run python -m pytest -q tests/unit/services/stages/test_cross_file_rels_stage.py tests/integration/test_cross_file_acceptance.py --override-ini='addopts='` fails in `TestRealSCIPAcceptance.test_scan_with_real_scip_produces_reference_edges`: `cross_file_rels_edges == 0`. |
| AC5 | 75% | Stage unit suite includes `test_returns_false_when_binary_missing`; stage logs install hints from `INDEXER_INSTALL` when a binary is missing. |
| AC9 | 85% | Stage unit suite passed, including `test_auto_discovers_when_entries_empty` and `test_skips_when_auto_discover_disabled_and_empty`. |
| AC11 | 35% | Adapter-layer dedup exists, but the changed stage code merges `reused_edges + fresh_edges` without a final dedup step. |
| AC12 | 60% | Filtering still exists in adapter logic, but the broken real path mapping prevents strong end-to-end confidence. |
| AC15 | 45% | Cache directory and `.gitignore` creation are present, but this phase does not actually reuse cached indexes on re-scan; it always reruns the indexer. |

Additional verification:

- `uv run ruff check src/fs2/cli/scan.py src/fs2/core/services/pipeline_context.py src/fs2/core/services/scan_pipeline.py src/fs2/core/services/stages/cross_file_rels_stage.py tests/integration/test_cross_file_acceptance.py tests/unit/services/stages/test_cross_file_rels_stage.py` → passed.
- Direct `uv run python` repro showed:
  - SCIP documents: `handler.py`, `model.py`, `service.py`
  - Raw extracted edges: `5`
  - Adapter-mapped edges: `0`
  - Known file IDs: `file:tests/fixtures/cross_file_sample/{handler,model,service}.py`

### E.5) Doctrine Compliance

N/A — no `docs/project-rules/rules.md`, `idioms.md`, `architecture.md`, or `constitution.md` files exist in this repository.

### E.6) Harness Live Validation

N/A — no harness configured.

## F) Coverage Map

| AC | Description | Evidence | Confidence |
|----|-------------|----------|------------|
| AC1 | `fs2 scan` on Python project with `scip-python` produces cross-file edges | Real acceptance test fails with zero edges; direct repro shows 5 raw SCIP edges dropping to 0 mapped fs2 edges | 5% |
| AC5 | Missing indexer logs install instructions and scan continues | Unit test `test_returns_false_when_binary_missing`; code logs from `INDEXER_INSTALL` path | 75% |
| AC9 | Empty entries + `auto_discover=true` discovers projects | Unit tests `test_auto_discovers_when_entries_empty` and `test_skips_when_auto_discover_disabled_and_empty` passed in targeted suite | 85% |
| AC11 | Edges are deduplicated | Adapter has dedup, but stage merge path can duplicate unchanged edges during mixed incremental scans | 35% |
| AC12 | Local/stdlib/self refs filtered | Adapter filtering remains in place, but broken end-to-end mapping reduces confidence | 60% |
| AC15 | `index.scip` cached for re-use | Cache file and `.gitignore` are created, but reuse behavior is not implemented in the changed stage | 45% |

**Overall coverage confidence**: 62%

## G) Commands Executed

```bash
git --no-pager status --short
git --no-pager log --oneline -10
git --no-pager show --stat --summary --format=fuller e3dc4b1
git --no-pager show --stat --summary --format=fuller bbe3db2
git --no-pager show --stat --summary --format=fuller 9fcfc42
git --no-pager diff 469e2db..HEAD > /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-4-stage-integration/reviews/_computed.diff
git --no-pager diff --name-status 469e2db..HEAD > /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-4-stage-integration/reviews/_manifest.txt
uv run ruff check src/fs2/cli/scan.py src/fs2/core/services/pipeline_context.py src/fs2/core/services/scan_pipeline.py src/fs2/core/services/stages/cross_file_rels_stage.py tests/integration/test_cross_file_acceptance.py tests/unit/services/stages/test_cross_file_rels_stage.py
uv run python -m pytest -q tests/unit/services/stages/test_cross_file_rels_stage.py tests/integration/test_cross_file_acceptance.py --override-ini='addopts='
uv run python - <<'PY'
# reproduced the real SCIP run, inspected generated index.scip,
# printed raw SCIP edges, known fs2 node IDs, and mapped edge count
PY
```

## H) Handover Brief

> Copy this section to the implementing agent. It has no context on the review —
> only context on the work that was done before the review.

**Review result**: REQUEST_CHANGES

**Plan**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md
**Spec**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-spec.md
**Phase**: Phase 4: Stage Integration
**Tasks dossier**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-4-stage-integration/tasks.md
**Execution log**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-4-stage-integration/execution.log.md
**Review file**: /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-4-stage-integration/reviews/review.phase-4-stage-integration.md

### Files Reviewed

| File (absolute path) | Status | Domain | Action Needed |
|---------------------|--------|--------|---------------|
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/README.md` | Changed | docs | Recheck after docs/how guide is corrected |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/suggestions.md` | Changed | docs | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/reviews/_computed.diff` | Changed | docs | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/reviews/fix-tasks.phase-3-config-discovery-cli.md` | Changed | docs | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-3-config-discovery-cli/reviews/review.phase-3-config-discovery-cli.md` | Changed | docs | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-4-stage-integration/execution.log.md` | Changed | docs | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-4-stage-integration/tasks.fltplan.md` | Changed | docs | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/tasks/phase-4-stage-integration/tasks.md` | Changed | docs | None |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/cli/scan.py` | Changed | cli | Revisit only if the path-normalization fix needs config-root threading |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/pipeline_context.py` | Changed | core/services | Revisit only if extra project-root metadata is needed |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/scan_pipeline.py` | Changed | core/services | Revisit only if extra project-root metadata is needed |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py` | Changed | core/services/stages | **Fix required** |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/integration/test_cross_file_acceptance.py` | Changed | tests | **Fix required** — keep failing test green after path normalization |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py` | Changed | tests | **Fix required** — add regression coverage for merge dedup and path normalization |
| `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/cross-file-relationships.md` | Reviewed (unchanged) | docs | **Fix required** — rewrite from Serena to SCIP |

### Required Fixes (if REQUEST_CHANGES)

| # | File (absolute path) | What To Fix | Why |
|---|---------------------|-------------|-----|
| 1 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py` | Normalize SCIP file paths so project-relative `index.scip` document paths map onto repo-relative fs2 node IDs | Real acceptance test currently writes zero cross-file edges despite a valid index with raw edges |
| 2 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/src/fs2/core/services/stages/cross_file_rels_stage.py` and `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/tests/unit/services/stages/test_cross_file_rels_stage.py` | Deduplicate the merged `reused_edges + fresh_edges` path and add regression coverage | Mixed incremental scans can duplicate unchanged edges |
| 3 | `/Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/how/user/cross-file-relationships.md` | Replace Serena instructions with SCIP workflow or retire the file and repoint surfaced docs | The phase claims docs/how was updated, but user-facing guide content is still Serena-only |

### Domain Artifacts to Update (if any)

| File (absolute path) | What's Missing |
|---------------------|----------------|
| `None` | No `docs/domains/` artifacts exist in this repository; no domain-doc update is required for this phase. |

### Next Step

/plan-6-v2-implement-phase --plan /Users/jordanknight/substrate/fs2/031-cross-file-rels-take-2/docs/plans/038-scip-cross-file-rels/scip-cross-file-rels-plan.md --phase 'Phase 4: Stage Integration'
