# Fix Tasks — Phase 4: Batch Processing Engine

**Testing Approach**: Full TDD  
**Mock Usage**: Targeted mocks

Apply these in order (CRITICAL → HIGH → MEDIUM). After fixes: re-run `uv run pytest tests/unit -q` and then re-run `/plan-7` for Phase 4.

---

## CRITICAL

### FT-001: Sync plan Phase 4 task table to dossier/log

- **Problem**: Plan Phase 4 task table still shows all tasks as pending with no log links (`docs/plans/008-smart-content/smart-content-plan.md:983`).
- **Fix**:
  - Update rows `4.1`–`4.14` to `[x]`.
  - Set `Log` column to `[📋](tasks/phase-4-batch-processing-engine/execution.log.md#task-t001-t010-red-phase)` for 4.1–4.10 and `[📋](tasks/phase-4-batch-processing-engine/execution.log.md#task-t011-t014-green-phase)` for 4.11–4.14.
  - Add Notes with `log#...` + footnote tags `[^28]`–`[^32]` consistent with the Phase 4 ledger entries in the plan.

### FT-002: Add Task↔Log anchors + Task↔Footnote tags to Phase 4 dossier tasks table

- **Problem**: Dossier Phase 4 tasks table has `[x]` statuses but does not include log anchors or footnote tags (`docs/plans/008-smart-content/tasks/phase-4-batch-processing-engine/tasks.md:177`).
- **Fix** (minimal, matches Phase 1–3 conventions):
  - Add a per-row evidence link to the `Notes` column, e.g. `log#task-t001-t010-red-phase` for T001–T010 and `log#task-t011-t014-green-phase` for T011–T014 (or use explicit `execution.log.md#...` links).
  - Add `[^28]` to T001–T010 rows, `[^29]` to T011, `[^30]` to T012, `[^31]` to T013, `[^32]` to T014.

### FT-003: Populate dossier “Phase Footnote Stubs” from Plan ledger (plan is authority)

- **Problem**: Dossier stubs are blank (`docs/plans/008-smart-content/tasks/phase-4-batch-processing-engine/tasks.md:508`) while Plan § “Change Footnotes Ledger” defines `[^28]`–`[^32]` (`docs/plans/008-smart-content/smart-content-plan.md:1579`).
- **Fix**: Fill the stub table with the exact footnote numbers + node IDs + descriptions from the plan ledger.
  - Ensure numbering is sequential and matches the plan (no gaps/duplicates).
  - Ensure tasks table references those same `[^N]` tags.

---

## HIGH

### FT-004: Remove out-of-scope change from Phase 4 diff

- **Problem**: `.claude/settings.local.json` is modified but not part of Phase 4 deliverables.
- **Fix**: Revert this file before merge (or justify it in the Phase 4 dossier alignment brief and add provenance, if it truly must ship).

### FT-005: Make the “fair distribution” test actually assert fairness (or rewrite its contract)

- **Problem**: `test_given_100_items_10_workers_then_work_distributed_fairly` claims “Each worker processes at least 5 items” but does not assert any per-worker distribution (`tests/unit/services/test_smart_content_batch.py:243`).
- **Preferred fix (no production changes)**:
  - Wrap `FakeLLMAdapter.generate` in the test to record `asyncio.current_task().get_name()` for each call (workers are named `smart-content-worker-{i}`).
  - Assert all 10 worker names appear and that `min(counts.values()) >= 5` (or another documented threshold).
- **Patch hint (sketch, not exact)**:
  ```diff
  + from collections import Counter
  + call_workers = Counter()
    original_generate = llm_adapter.generate
    async def tracking_generate(*args, **kwargs):
  +     task = asyncio.current_task()
  +     if task is not None:
  +         call_workers[task.get_name()] += 1
        return await original_generate(*args, **kwargs)
  ...
  + assert len(call_workers) == 10
  + assert min(call_workers.values()) >= 5
  ```
- **Alternative**: If fairness is not a required guarantee, change the docstring “Acceptance Criteria” to match what the test *actually* proves (e.g., “batch completes under load with 10 workers”).

### FT-006: Align plan’s progress logging frequency to implementation

- **Problem**: Plan Phase 4 row 4.7 says “every 100 items” (`docs/plans/008-smart-content/smart-content-plan.md:989`) but code/tests are “every 50” (`src/fs2/core/services/smart_content/smart_content_service.py:383`).
- **Fix**: Update plan row 4.7 success criteria (and/or notes) to reflect 50.

---

## MEDIUM

### FT-007: Improve explicit AC7 ↔ test mapping

- **Problem**: Coverage for AC7 is strong but mostly inferred (tests do not explicitly tag “AC7” in names/docblocks).
- **Fix**: Add “AC7” to docblocks (or prefix a few test names) for the highest-value tests (throughput, progress logging, worker-count capping).

