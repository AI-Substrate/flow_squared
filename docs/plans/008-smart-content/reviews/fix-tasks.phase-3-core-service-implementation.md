# Fix Tasks — Phase 3: Core Service Implementation

Apply these in severity order, then rerun `/plan-6` (Phase 3 fixes only) and `/plan-7`.

## FT-001 (CRITICAL) Restore Task↔Log bidirectional linking in Phase 3 execution log

**Files**:
- `/workspaces/flow_squared/docs/plans/008-smart-content/tasks/phase-3-core-service-implementation/execution.log.md`
- `/workspaces/flow_squared/docs/plans/008-smart-content/smart-content-plan.md` (only if log anchor IDs change)

**Issue**: Phase 3 log headings omit explicit `{#...}` anchors and per-entry metadata/backlinks, so plan links like `.../execution.log.md#task-t001-t006-t012` are not reliable.

**Fix (pattern)**:
- For each task section heading, add a stable anchor suffix like Phase 1 uses:
  - `## Task T000: ... {#task-t000-pre-flight-fakellmadapter-check}`
  - `## Task T001-T006 + T012: ... {#task-t001-t006-t012}`
  - `## Task T007-T011: ... {#task-t007-t011}`
- Under each task heading, add the metadata block used in Phase 1 logs:
  - `**Dossier Task**: T00X`
  - `**Plan Task**: 3.X`
  - `**Plan Reference**:` link back to plan
  - `**Dossier Reference**:` link back to dossier

**Patch hint (example, <10 lines)**:
```diff
-## Task T000: Pre-flight FakeLLMAdapter Check
+## Task T000: Pre-flight FakeLLMAdapter Check {#task-t000-pre-flight-fakellmadapter-check}
+**Dossier Task**: T000
+**Plan Task**: 3.0
+**Plan Reference**: ../../smart-content-plan.md
+**Dossier Reference**: ./tasks.md
```

## FT-002 (CRITICAL) Add task row log + footnote links in Phase 3 dossier table

**File**: `/workspaces/flow_squared/docs/plans/008-smart-content/tasks/phase-3-core-service-implementation/tasks.md`

**Issue**: Completed tasks in the dossier “Tasks” table have no `log#anchor` or `[^N]` tags in Notes.

**Fix**:
- For each completed task row, append both:
  - a log link to the matching anchor in `execution.log.md`
  - the footnote tag(s) that map to the plan ledger (`[^20]`–`[^27]`)

**Example**:
- T001–T006, T012 → `log#task-t001-t006-t012` + `[^20]` (and `[^26]` where relevant)
- T007 → `log#task-t007-t011` + `[^21]`
- T008 → `log#task-t007-t011` + `[^22]`
- T009 → `log#task-t007-t011` + `[^23]`
- T010 → `log#task-t007-t011` + `[^24]`
- T011 → `log#task-t007-t011` + `[^25]`
- Prereq section (if treated as a task) → `[^27]`

## FT-003 (CRITICAL) Sync dossier “Phase Footnote Stubs” to Plan §9 ledger (plan is authority)

**Files**:
- `/workspaces/flow_squared/docs/plans/008-smart-content/tasks/phase-3-core-service-implementation/tasks.md`
- `/workspaces/flow_squared/docs/plans/008-smart-content/smart-content-plan.md` (authority source; likely no edits needed)

**Issue**: Dossier stubs are placeholders (no node IDs/descriptions) and omit `[^27]`.

**Fix**:
- Populate each stub row to match the plan ledger entries for `[^20]`–`[^27]` (same numbers, same node IDs, same descriptions).
- Ensure numbering is sequential with no gaps/duplicates.

## FT-004 (HIGH) Remove or justify out-of-scope `.claude/settings.local.json` change

**File**: `/workspaces/flow_squared/.claude/settings.local.json`

**Issue**: Unrelated to Phase 3 deliverables; not mentioned in Phase 3 dossier scope.

**Fix options**:
- Preferred: revert this file from the Phase 3 diff before merge.
- If it must remain: add explicit scope justification in the Phase 3 dossier and add provenance in the plan ledger (e.g., `file:.claude/settings.local.json`).

## FT-005 (MEDIUM) Preserve exception layering for token counting failures

**File**: `/workspaces/flow_squared/src/fs2/core/services/smart_content/smart_content_service.py`

**Issue**: `_prepare_content()` calls `TokenCounterAdapter.count_tokens()` without translating adapter-layer failures (e.g., `TokenCounterError`) to service-layer `SmartContentProcessingError`.

**Fix**:
- Catch `TokenCounterError` (from `fs2.core.adapters.exceptions`) and raise `SmartContentProcessingError` including `node.node_id` for context.
- Add a unit test that configures `FakeTokenCounterAdapter` to raise and asserts `SmartContentProcessingError`.

**Patch hint (example, <10 lines)**:
```diff
from fs2.core.adapters.exceptions import TokenCounterError
...
        try:
            token_count = self._token_counter.count_tokens(content)
        except TokenCounterError as e:
            raise SmartContentProcessingError(f"Token counting failed for node {node.node_id}: {e}") from e
```

## FT-006 (LOW) Update stale header comment in Phase 3 test file

**File**: `/workspaces/flow_squared/tests/unit/services/test_smart_content_service.py`

**Issue**: Header says “RED - SmartContentService does not exist yet” but the service exists; this is confusing after GREEN.

**Fix**: Adjust the header to reflect Phase 3’s current state (tests cover init/skip/truncation/processing/errors/integration).

