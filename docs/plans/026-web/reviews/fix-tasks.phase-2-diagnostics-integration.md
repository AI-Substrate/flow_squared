# Fix Tasks: Phase 2 - Diagnostics Integration

**Review**: [review.phase-2-diagnostics-integration.md](review.phase-2-diagnostics-integration.md)
**Date**: 2026-01-16
**Priority**: CRITICAL/HIGH items first, then MEDIUM

---

## Fix-01: Add log anchors to T001-T007 Notes column (7 items)

**Severity**: HIGH
**File**: `docs/plans/026-web/tasks/phase-2-diagnostics-integration/tasks.md`
**Lines**: 207-213

### Current (lines 207-213):

The Notes column for T001-T007 contains generic comments but no log#anchor references.

### Required Changes:

Update the task table Notes column for each task to include log anchor:

| Task | Current Notes | Required Notes |
|------|---------------|----------------|
| T001 | `Pure functions, no CLI deps` | `Pure functions, no CLI deps · [log](./execution.log.md#task-t001-write-tests-for-shared-validation-module)` |
| T002 | `Single source of truth` | `Single source of truth · [log](./execution.log.md#task-t002-create-shared-validation-module)` |
| T003 | `~500 lines move to shared` | `~500 lines move to shared · [log](./execution.log.md#task-t003-refactor-doctorpy-to-use-shared-module)` |
| T004 | `~12 tests (less than before...)` | `~12 tests · [log](./execution.log.md#task-t004-write-tests-for-validationservice)` |
| T005 | `Thin wrapper over shared module` | `Thin wrapper · [log](./execution.log.md#task-t005-implement-validationservice)` |
| T006 | `Follow Phase 1 fake pattern` | `Phase 1 pattern · [log](./execution.log.md#task-t006-write-tests-for-fakevalidationservice)` |
| T007 | `–` | `[log](./execution.log.md#task-t007-implement-fakevalidationservice)` |

---

## Fix-02: Add footnote references to task table Notes (CRITICAL)

**Severity**: CRITICAL
**File**: `docs/plans/026-web/tasks/phase-2-diagnostics-integration/tasks.md`
**Lines**: 207-218

### Current:

Notes column lacks [^N] footnote references that link to plan § 12 ledger.

### Required Changes:

Add footnote tags to each task's Notes column per mapping:

| Task | Add Footnote |
|------|--------------|
| T001 | `[^11]` |
| T002 | `[^11]` |
| T003 | `[^12]` |
| T004 | `[^13]` |
| T005 | `[^13]` |
| T006 | `[^13]` |
| T007 | `[^13]` |
| T008 | `[^14]` |
| T009 | `[^14]` |
| T010 | `[^14]` |
| T011 | `[^14]` |
| T012 | `[^15]` |

**Example Combined Notes (T001)**:
```
Pure functions, no CLI deps · [log](./execution.log.md#task-t001-write-tests-for-shared-validation-module) · [^11]
```

---

## Fix-03: Remove unused import CONFIG_DOCS_URL

**Severity**: MEDIUM
**File**: `src/fs2/cli/doctor.py`
**Line**: 43

### Current:

```python
from fs2.core.validation.constants import CONFIG_DOCS_URL
```

### Fix:

Delete line 43 (the import is unused).

### Verification:

```bash
ruff check src/fs2/cli/doctor.py --select=F401
# Should show no F401 errors after fix
```

---

## Fix-04: Remove unused import find_placeholders_in_value

**Severity**: MEDIUM
**File**: `src/fs2/web/services/validation.py`
**Lines**: 13-19

### Current:

```python
from fs2.core.validation import (
    compute_overall_status,
    detect_literal_secrets,
    find_placeholders_in_value,  # UNUSED
    validate_embedding_config,
    validate_llm_config,
)
```

### Fix:

Remove `find_placeholders_in_value` from import list:

```python
from fs2.core.validation import (
    compute_overall_status,
    detect_literal_secrets,
    validate_embedding_config,
    validate_llm_config,
)
```

### Verification:

```bash
ruff check src/fs2/web/services/validation.py --select=F401
# Should show no F401 errors after fix
```

---

## Verification After All Fixes

Run these commands to verify all fixes are complete:

```bash
# 1. Verify tests still pass
pytest tests/unit/core/validation/ tests/unit/web/ tests/unit/cli/test_doctor.py -v

# 2. Verify no lint warnings
ruff check src/fs2/core/validation/ src/fs2/web/ src/fs2/cli/doctor.py src/fs2/cli/web.py

# 3. Re-run code review
/plan-7-code-review --phase "Phase 2: Diagnostics Integration" --plan "docs/plans/026-web/web-plan.md"
```

Expected outcome: **APPROVE** verdict with 0 violations.
