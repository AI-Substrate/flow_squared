# Fix Tasks — Phase 1: Foundation & Infrastructure

**Purpose**: Address blocking findings from `reviews/review.phase-1-foundation-and-infrastructure.md` to reach **APPROVE**.  
**Approach**: Full TDD (tests-first where behavior changes).  

## CRITICAL

### FT-001: Complete the Plan Footnotes Ledger for all diff-touched files

**Issue**: Plan ledger omits diff-touched files, breaking provenance and the “each changed file/method has a corresponding footnote entry” gate.  
**Files**:
- `docs/plans/008-smart-content/smart-content-plan.md` (Change Footnotes Ledger)
- Missing entries for: `tests/unit/services/test_smart_content_exceptions.py`, `src/fs2/core/services/smart_content/__init__.py`, and (if kept) `AGENTS.md`

**Fix**:
1) Add node IDs for each missing file to an existing footnote (preferred: the task that introduced it) or add a new footnote number (keep numbering sequential).
2) Include at least a `file:<path>` node ID; add `class:` / `function:` entries if you want symbol-level provenance.

**Patch hint (example)**:
```diff
 [^11]: Task 1.11 - Smart content service-layer exception hierarchy
   - `file:src/fs2/core/services/smart_content/exceptions.py`
+  - `file:src/fs2/core/services/smart_content/__init__.py`
+  - `file:tests/unit/services/test_smart_content_exceptions.py`
   - `class:src/fs2/core/services/smart_content/exceptions.py:SmartContentError`
   - `class:src/fs2/core/services/smart_content/exceptions.py:TemplateError`
   - `class:src/fs2/core/services/smart_content/exceptions.py:SmartContentProcessingError`
```

### FT-002: Enforce plan authority by syncing dossier footnote stubs to the plan ledger

**Issue**: Dossier stubs list only a single “Affects” node per footnote, but the plan ledger contains a fuller node list; per doctrine, plan ledger is the authority and dossier must mirror it.  
**Files**:
- `docs/plans/008-smart-content/tasks/phase-1-foundation-and-infrastructure/tasks.md:306` (Phase Footnote Stubs)
- `docs/plans/008-smart-content/smart-content-plan.md:1441` (Change Footnotes Ledger)

**Fix**:
- For each `[^N]`, copy the plan ledger’s node list into the dossier stub entry (either by expanding the `Affects` cell to include multiple node IDs, or by adding a follow-on “Nodes” column/continuation lines that reproduce the plan ledger list exactly).

**Patch hint (conceptual)**:
```diff
- | [^1] | ... | `file:tests/unit/config/test_smart_content_config.py` | ...
+ | [^1] | ... | `file:tests/unit/config/test_smart_content_config.py`<br>`function:tests/unit/config/test_smart_content_config.py:test_given_no_args_when_constructed_then_has_spec_defaults`<br>... | ...
```

## HIGH

### FT-003: Resolve scope guard violation for `AGENTS.md`

**Issue**: `AGENTS.md` is in the diff but not referenced/justified by Phase 1 dossier scope.  
**Fix options**:
- **Preferred**: remove `AGENTS.md` from this phase diff (leave it for a dedicated repo hygiene phase/PR).  
- If it must ship in this phase: add explicit justification in `tasks.md` scope section and add footnote ledger provenance (`file:AGENTS.md`) in plan + dossier stubs.

## MEDIUM

### FT-004: Make new Phase 1 tests ruff-clean (import organization)

**Issue**: `uv run ruff check` reports `I001` import organization violations in `tests/unit/adapters/test_token_counter.py` (imports inside tests not organized).  
**Fix**:
- Prefer module-level imports where feasible, or group/format local imports consistently to satisfy ruff.

**Patch hint (example)**:
```diff
-        from fs2.config.service import FakeConfigurationService
-        from fs2.config.objects import LLMConfig
+        from fs2.config.objects import LLMConfig
+        from fs2.config.service import FakeConfigurationService
```

## LOW (Optional)

### FT-005: Strengthen bidirectional links in execution log metadata

**Issue**: `execution.log.md` contains task metadata but task IDs are not clickable links back to dossier/plan task rows.  
**Fix**:
- Turn `**Dossier Task**: T001` into a link to `tasks.md#...` (or a stable anchor), and similarly link `Plan Task`.

## Verification (must re-run)

```bash
# Ensure uv uses workspace-writable cache
export UV_CACHE_DIR=/workspaces/flow_squared/.uv_cache

# Tests
just test-unit

# Lint signal (at least for Phase 1 touched files)
uv run ruff check tests/unit/adapters/test_token_counter.py

# Re-run review gate
# /plan-7-code-review --phase \"Phase 1: Foundation & Infrastructure\" --plan \"/workspaces/flow_squared/docs/plans/008-smart-content/smart-content-plan.md\"
```

