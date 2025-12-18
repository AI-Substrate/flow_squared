# Fix Tasks — Phase 2: Template System

**Scope**: Fix Phase 2 blockers from `docs/plans/008-smart-content/reviews/review.phase-2-template-system.md`.  
**Testing Approach**: Full TDD (tests/docstrings first where applicable).  

## CRITICAL

### FT-001: Repair execution log anchors + metadata (graph integrity)

**Files**:
- `docs/plans/008-smart-content/tasks/phase-2-template-system/execution.log.md`

**Issue**:
- Plan + dossier link to `execution.log.md#task-...`, but Phase 2 log headings do not define `{#task-...}` anchors (unlike Phase 1). This breaks Task↔Log and Plan↔Log navigation.

**Fix**:
1) For each Phase 2 task section, change the heading to include the exact anchor referenced by plan/dossier Notes (kebab-case), e.g.:
   - `## Task T004: Write TemplateService init tests {#task-t004-write-templateservice-init-tests}`
2) Restore the Phase 1 metadata block structure under each heading (minimum):
   - `**Dossier Task**: T00X`
   - `**Plan Task**: 2.Y` (match plan Phase 2 table)
   - `**Plan Reference**: docs/plans/008-smart-content/smart-content-plan.md`
   - `**Dossier Reference**: docs/plans/008-smart-content/tasks/phase-2-template-system/tasks.md`
3) Ensure every `log#...` referenced in the dossier task table and plan Phase 2 table resolves to a real `{#...}` anchor in the log.

**Patch hint (example pattern, adapt per task)**:
```diff
-## Task T004: Write TemplateService init tests
+## Task T004: Write TemplateService init tests {#task-t004-write-templateservice-init-tests}
+**Dossier Task**: T004
+**Plan Task**: 2.1
+**Plan Reference**: `docs/plans/008-smart-content/smart-content-plan.md`
+**Dossier Reference**: `docs/plans/008-smart-content/tasks/phase-2-template-system/tasks.md`
```

**Validation**:
- Click/resolve: `docs/plans/008-smart-content/smart-content-plan.md` Phase 2 log links
- Click/resolve: `docs/plans/008-smart-content/tasks/phase-2-template-system/tasks.md` `log#...` anchors

## HIGH

### FT-002: Make Phase 2 tests comply with plan “Test Documentation” fields

**Files**:
- `tests/unit/services/test_template_service.py`

**Issue**:
- The plan requires every test include docstring fields: `Purpose:`, `Quality Contribution:`, `Acceptance Criteria:`. All 8 Phase 2 tests omit `Acceptance Criteria:`.

**Fix**:
- Add an `Acceptance Criteria:` line to each test’s docstring, ideally referencing the relevant spec AC ID(s) (AC8/AC11/AC4) and stating the measurable assertions already present.

**Patch hint (template)**:
```diff
     """
     Purpose: ...
     Quality Contribution: ...
+    Acceptance Criteria: AC11 — category→template mapping matches spec table for all 9 categories.
     """
```

**Validation**:
- `UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run pytest -q tests/unit/services/test_template_service.py`
- `UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache uv run ruff check tests/unit/services/test_template_service.py`

## LOW

### FT-003: Update outdated module docstring (“RED”) in Phase 2 tests

**Files**:
- `tests/unit/services/test_template_service.py`

**Issue**:
- Module docstring says “TDD Phase: RED - these tests should fail…”, but tests now pass.

**Fix**:
- Update to reflect current status (or remove the “RED” statement).

