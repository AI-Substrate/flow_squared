# Review Report — Phase 4: Batch Processing Engine

**Plan**: `/workspaces/flow_squared/docs/plans/008-smart-content/smart-content-plan.md`  
**Phase Dossier**: `/workspaces/flow_squared/docs/plans/008-smart-content/tasks/phase-4-batch-processing-engine/tasks.md`  
**Execution Log**: `/workspaces/flow_squared/docs/plans/008-smart-content/tasks/phase-4-batch-processing-engine/execution.log.md`  
**Diff Basis**: `HEAD (5fb25e5) -> working tree + untracked files`

## A) Verdict

**REQUEST_CHANGES**

Blocking issues are primarily **graph integrity / provenance** (Plan↔Dossier↔Log↔Footnote links not wired up), plus an **out-of-scope file** in the diff and one **test that claims fairness without asserting it**.

## B) Summary

- Implementation in `SmartContentService.process_batch()` matches the Phase 4 brief (asyncio Queue + worker pool + barrier + sentinels + local stats/lock per CD10) and the unit suite is green.
- **Graph integrity is broken**: Phase 4 dossier tasks table has completed tasks but lacks required `log#...` anchors and `[^N]` footnote tags; dossier “Phase Footnote Stubs” are empty; plan Phase 4 task table remains `[ ]` with no log links.
- `.claude/settings.local.json` is modified but not part of Phase 4 scope.

## C) Checklist

**Testing Approach: Full TDD**  
**Mock Usage: Targeted mocks**

- [x] Tests exist for Phase 4 behavior (18/18) and include Purpose / Quality Contribution / Acceptance Criteria docblocks
- [x] Mock policy aligns (fakes used; no mocking frameworks detected)
- [x] Execution log captures RED→GREEN evidence (`execution.log.md:10`, `execution.log.md:96`)
- [x] Cross-phase regression check: unit suite passes (`690 passed`)
- [ ] Tests precede code (cannot be verified via git history because Phase 4 work is uncommitted)
- [ ] Graph integrity links (Task↔Log, Task↔Footnote, Plan↔Dossier) intact
- [ ] Only in-scope files changed

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| F-001 | CRITICAL | `docs/plans/008-smart-content/smart-content-plan.md:983` | Plan Phase 4 task table is still all `[ ]` with `Log` set to `-` (Plan↔Dossier sync broken) | Update Phase 4 rows (4.1–4.14) to `[x]`, add `[📋]` links to `execution.log.md` anchors, align Notes with dossier + plan footnotes |
| F-002 | CRITICAL | `docs/plans/008-smart-content/tasks/phase-4-batch-processing-engine/tasks.md:177` | Dossier tasks table lacks required `log#anchor` links and `[^N]` footnote tags for completed tasks | Add per-row `execution.log.md#...` (or `log#...`) + footnote tags matching Plan ledger `[^28]`–`[^32]` |
| F-003 | CRITICAL | `docs/plans/008-smart-content/tasks/phase-4-batch-processing-engine/tasks.md:508` | Dossier “Phase Footnote Stubs” is an empty placeholder and not synced to Plan ledger (authority conflict) | Populate stubs with Plan ledger `[^28]`–`[^32]` (plan is authority), then reference them from tasks table Notes |
| F-004 | HIGH | `.claude/settings.local.json:1` | Out-of-scope file modified for Phase 4 | Revert/remove from diff before merge |
| F-005 | HIGH | `tests/unit/services/test_smart_content_batch.py:243` | “Fair distribution” test claims per-worker fairness but does not assert distribution | Track per-worker work via `asyncio.current_task().get_name()` in a wrapped `FakeLLMAdapter.generate` and assert min-per-worker count |
| F-006 | HIGH | `docs/plans/008-smart-content/smart-content-plan.md:989` | Plan Phase 4 row 4.7 still says “INFO logged every 100 items” but dossier/code implement 50 | Update plan row 4.7 success criteria to 50 (or document the change explicitly in plan Notes) |
| F-007 | MEDIUM | `tests/unit/services/test_smart_content_batch.py:1` | Coverage mapping to AC7 is implied but not explicit (no “AC7” tag in test names/docblocks) | Add “AC7” to relevant test docblocks or test naming to increase mapping confidence |

## E) Detailed Findings

### E.0 Cross-Phase Regression Analysis

**Result: PASS**

- Re-ran unit suite against current working tree: `UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run pytest tests/unit -q` → `690 passed` (see Section G).

### E.1 Doctrine & Testing Compliance

**Graph Integrity Verdict: ❌ BROKEN** (requires changes before merge)

**F-002 (CRITICAL) — Task↔Log + Task↔Footnote missing in dossier tasks table**
- **Observed**: Phase 4 dossier tasks are marked complete (`tasks.md:179`) but the `Subtasks` column is `–` and the `Notes` column contains only `Plan 4.x` references (no `execution.log.md#...` / `log#...` anchors, no `[^N]` tags).
- **Expected**: Completed rows include a stable log anchor link (to Phase 4 execution log headings such as `execution.log.md:10`) plus a footnote tag tying the row to Plan § “Change Footnotes Ledger” (Phase 4: `smart-content-plan.md:1579`).
- **Impact**: Cannot traverse Plan↔Dossier↔Log evidence or Dossier↔Footnote↔File provenance deterministically.

**F-003 (CRITICAL) — Plan authority conflicts / unsynced footnote stubs**
- **Observed**: Plan ledger defines Phase 4 footnotes `[^28]`–`[^32]` (`smart-content-plan.md:1579`), but dossier stubs are blank (`tasks.md:508`).
- **Authority**: Plan § “Change Footnotes Ledger” is primary; dossier stubs must be derived and synchronized.
- **Impact**: File→Footnote→Task provenance traversal is broken.

**F-001 (CRITICAL) — Plan↔Dossier sync broken**
- **Observed**: Plan Phase 4 tasks table still shows `[ ]` and no log links (`smart-content-plan.md:983`) while dossier tasks show `[x]` (`tasks.md:179`) and Phase 4 execution log claims completion (`execution.log.md:18`, `execution.log.md:104`).
- **Impact**: Progress tracking and navigation are inconsistent between plan and dossier.

**TDD & Mock Policy**
- **TDD evidence**: Execution log contains explicit RED failing test evidence and GREEN passing evidence (`execution.log.md:80`, `execution.log.md:148`).
- **Mock policy**: Targeted mocks honored (FakeLLMAdapter/FakeTokenCounterAdapter used; no mock frameworks detected).

### E.2 Semantic Analysis (Spec Alignment)

- **AC7** implemented by `SmartContentService.process_batch()` with asyncio Queue + worker pool, configurable workers via `SmartContentConfig.max_workers`, and progress tracking (`src/fs2/core/services/smart_content/smart_content_service.py:240`).
- **CD10** respected: queue + lock are local variables and passed into `_worker_loop` (`src/fs2/core/services/smart_content/smart_content_service.py:274`).
- **CD07** partial failures handled by catching exceptions per item and appending to `stats["errors"]` (`src/fs2/core/services/smart_content/smart_content_service.py:397`); authentication errors re-raise to fail the batch (`src/fs2/core/services/smart_content/smart_content_service.py:393`).

### E.3 Quality & Safety Analysis

**Safety Score: 100/100** (CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0)  
**Verdict: APPROVE (code safety)** — separate from the overall merge verdict, which is blocked by provenance/graph issues and the fairness test gap.

## F) Coverage Map (Acceptance Criteria ↔ Tests)

Overall coverage confidence (Phase 4): **75%** (behavioral match, but no explicit “AC7” IDs in tests)

| AC | Confidence | Test(s) | Notes |
|----|------------|---------|------|
| AC7 | 75% | `tests/unit/services/test_smart_content_batch.py:test_given_500_nodes_with_50ms_delay_then_completes_under_2s` | Throughput evidence (<2s with 50ms delay) |
| AC7 | 75% | `tests/unit/services/test_smart_content_batch.py:test_given_max_workers_10_when_processing_then_10_workers_spawned`, `...:test_given_3_nodes_and_max_workers_50_then_only_3_workers_spawned` | Configured worker count + capping |
| AC7 | 75% | `tests/unit/services/test_smart_content_batch.py:test_given_250_nodes_when_processing_then_progress_logged_at_50_100_150_200` | Progress logging every 50 (dossier-aligned) |

## G) Commands Executed

```bash
git status --porcelain=v1 -uall
git diff --name-status
git diff --unified=3 --no-color

UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run pytest tests/unit -q
UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run ruff check src/fs2/core/services/smart_content/
UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run mypy src/fs2/core/services/smart_content/smart_content_service.py
```

## H) Decision & Next Steps

- Apply `docs/plans/008-smart-content/reviews/fix-tasks.phase-4-batch-processing-engine.md`.
- Re-run `/plan-6-implement-phase --phase 4` (or perform equivalent sync steps) to regenerate Phase 4 artifacts with correct links/footnote stubs.
- Re-run `/plan-7-code-review` for Phase 4.

## I) Footnotes Audit (Diff Paths ↔ Footnote Tags ↔ Node IDs)

| Diff Path | Footnote Tag(s) in dossier | Node IDs (Plan Ledger) |
|----------|-----------------------------|------------------------|
| `tests/unit/services/test_smart_content_batch.py` | (missing) | `file:tests/unit/services/test_smart_content_batch.py` (`smart-content-plan.md:1579`) · `function:tests/unit/services/test_smart_content_batch.py:test_given_500_nodes_with_50ms_delay_then_completes_under_2s` (`smart-content-plan.md:1592`) |
| `src/fs2/core/services/smart_content/smart_content_service.py` | (missing) | `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService.process_batch` (`smart-content-plan.md:1583`) · `function:src/fs2/core/services/smart_content/smart_content_service.py:create_synchronized_worker` (`smart-content-plan.md:1586`) · `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService._worker_loop` (`smart-content-plan.md:1589`) |
| `docs/plans/008-smart-content/tasks/phase-4-batch-processing-engine/tasks.md` | N/A | (not tracked in Plan ledger; dossier stubs must be synced to plan) |
| `docs/plans/008-smart-content/tasks/phase-4-batch-processing-engine/execution.log.md` | N/A | (not tracked in Plan ledger; referenced by dossier + plan log links) |
| `docs/plans/008-smart-content/smart-content-plan.md` | N/A | Plan authority document (ledger is source of truth) |
| `.claude/settings.local.json` | (missing) | (missing) |

