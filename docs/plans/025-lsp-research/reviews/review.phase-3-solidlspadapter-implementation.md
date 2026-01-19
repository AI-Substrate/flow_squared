# Code Review: Phase 3 - SolidLspAdapter Implementation

**Plan**: [../lsp-integration-plan.md](../lsp-integration-plan.md)
**Phase Doc**: [../tasks/phase-3-solidlspadapter-implementation/tasks.md](../tasks/phase-3-solidlspadapter-implementation/tasks.md)
**Reviewer**: plan-7-code-review
**Date**: 2026-01-19

---

## A) Verdict

**REQUEST_CHANGES**

Rationale: While the implementation successfully meets all acceptance criteria and follows TDD discipline, security review identified path traversal vulnerabilities that must be addressed before merge. Additionally, the footnote ledger is not synchronized between plan and dossier.

---

## B) Summary

Phase 3 successfully implements `SolidLspAdapter`, wrapping vendored SolidLSP for cross-file reference resolution. Key achievements:

- ✅ **31/31 tests pass** (7 integration, 9 type translation, 15 ABC/fake)
- ✅ **All 5 acceptance criteria met** (AC05, AC08-AC10, AC17)
- ✅ **Full TDD discipline** with documented RED→GREEN→REFACTOR
- ✅ **Clean static checks** (ruff, mypy --strict)
- ❌ **Security issues** - Path traversal in `_uri_to_relative()` and `_source_to_node_id()`
- ❌ **Footnote sync** - `[^14]` in dossier not defined in plan ledger

---

## C) Checklist

**Testing Approach: Full TDD**

- [x] Tests precede code (RED-GREEN-REFACTOR evidence in execution log)
- [x] Tests as docs (assertions show behavior, Given-When-Then naming)
- [x] Mock usage matches spec: **Targeted fakes** (FakeConfigurationService only)
- [x] Negative/edge cases covered (empty responses, invalid language, missing server)

**Universal Checks:**

- [x] BridgeContext patterns followed (N/A - Python adapter, not VS Code extension)
- [x] Only in-scope files changed (3 files: adapter + 2 test files)
- [x] Linters/type checks are clean
- [x] Absolute paths used (node IDs use `file:{rel_path}` format)

---

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| SEC-001 | **MEDIUM** | lsp_adapter_solidlsp.py:575-599 | Path traversal in `_uri_to_relative()` | Use `Path.resolve().relative_to()` with bounds check |
| SEC-002 | **MEDIUM** | lsp_adapter_solidlsp.py:570 | `lstrip('/')` removes ALL leading slashes | Use `.removeprefix('/')` or validate traversal |
| COR-001 | **HIGH** | lsp_adapter_solidlsp.py:457-460 | No error handling for malformed Location dict | Add defensive key validation |
| COR-002 | **HIGH** | lsp_adapter_solidlsp.py:549 | KeyError if Location missing 'uri' | Use `.get()` with fallback |
| COR-003 | **MEDIUM** | lsp_adapter_solidlsp.py:253-254,313-314 | Assert statements for production validation | Replace with explicit None checks |
| COR-004 | **MEDIUM** | lsp_adapter_solidlsp.py:509-511 | Dead code (unused variable `_`) | Remove unused assignment |
| LINK-001 | **HIGH** | tasks.md:463 | Footnote `[^14]` not defined in plan ledger | Sync ledgers via plan-6a |

---

## E) Detailed Findings

### E.0) Cross-Phase Regression Analysis

**Skipped**: Phase 3 has no prior phases with tests to regress against (Phase 1 & 2 are infrastructure).

### E.1) Doctrine & Testing Compliance

#### Graph Integrity (Step 3a)

| Check | Result | Notes |
|-------|--------|-------|
| Task↔Log links | ✅ PASS | 10/10 completed tasks have log entries |
| Task↔Footnote links | ❌ FAIL | `[^14]` in dossier stubs not in plan ledger |
| Footnote↔File links | ✅ PASS | All FlowSpace node IDs point to existing files |

**Violation Detail (LINK-001)**:
- **Dossier tasks.md** (line 463): References `[^14]` in Phase Footnote Stubs
- **Plan lsp-integration-plan.md**: Only defines `[^13]` for Phase 3
- **Impact**: Broken bidirectional graph link
- **Fix**: Run `plan-6a --sync-footnotes` or manually add `[^14]` to plan

#### TDD Discipline

| Check | Result | Evidence |
|-------|--------|----------|
| RED phase documented | ✅ PASS | T002/T003: "TDD RED achieved — tests fail with ModuleNotFoundError" |
| Tests before impl | ✅ PASS | T002 @23:30 → T004 @23:40 (10-minute gap) |
| GREEN phase documented | ✅ PASS | T010: "31 passed, ruff clean, mypy --strict clean" |
| Behavioral test names | ✅ PASS | All tests use Given-When-Then pattern |

#### Mock Usage

| Check | Result | Evidence |
|-------|--------|----------|
| Integration uses real server | ✅ PASS | test_lsp_pyright.py drives real Pyright |
| Mock count | 0 | No unittest.mock imports |
| Policy compliance | ✅ PASS | "Targeted fakes with real servers" honored |

### E.2) Semantic Analysis

All acceptance criteria semantically satisfied:
- **AC05**: Exception translation wraps SolidLSP exceptions in LspAdapterError hierarchy
- **AC08**: `get_references()` → `CodeEdge(EdgeType.REFERENCES, confidence=1.0)`
- **AC09**: `get_definition()` → `CodeEdge(EdgeType.CALLS)` per DYK-3
- **AC10**: All edges have `resolution_rule="lsp:{method}"`
- **AC17**: Integration tests validate with real Pyright

### E.3) Quality & Safety Analysis

**Safety Score: 70/100** (MEDIUM: 4, HIGH: 2)
**Verdict: REQUEST_CHANGES**

#### Security Findings

**SEC-001: Path Traversal in _uri_to_relative()** (MEDIUM)
- **Issue**: URI handler lacks traversal protection. A malicious LSP response with `file:///../../sensitive.py` could escape project_root.
- **Impact**: File path disclosure outside project boundary
- **Fix**: Use `Path(abs_path).resolve().relative_to(Path(project_root).resolve())` with try/except ValueError

**SEC-002: lstrip('/') Misuse** (MEDIUM)
- **Issue**: `lstrip('/')` removes ALL leading slashes. `///../../file.py` becomes `../file.py`.
- **Fix**: Use `.removeprefix('/')` or add traversal validation

#### Correctness Findings

**COR-001 & COR-002: Malformed Location Dict** (HIGH)
- **Issue**: `_translate_reference()` and `_location_to_node_id()` access dict keys without validation
- **Impact**: KeyError propagates if SolidLSP returns unexpected structure
- **Fix**: Add defensive `.get()` with fallbacks or try/except KeyError

**COR-003: Assert for Production Validation** (MEDIUM)
- **Issue**: Lines 253-254, 313-314 use `assert` which is disabled with `-O`
- **Fix**: Replace with explicit `if self._server is None: raise RuntimeError(...)`

**COR-004: Dead Code** (MEDIUM)
- **Issue**: Lines 509-511 assign to unused `_` variable
- **Fix**: Remove dead code

#### Performance Findings

✅ **PASS** - No critical performance issues. Translation loops are O(n), no N+1 patterns, proper delegation to SolidLSP for I/O.

---

## F) Coverage Map

| Acceptance Criterion | Test File | Test Name | Confidence |
|---------------------|-----------|-----------|------------|
| AC05: Exception translation | test_lsp_pyright.py | test_given_invalid_language_when_initialize_then_raises_initialization_error | 100% |
| AC08: References → REFERENCES | test_lsp_type_translation.py | test_given_lsp_location_when_translating_reference_then_creates_code_edge | 100% |
| AC09: Definition → CALLS | test_lsp_type_translation.py | test_given_lsp_location_when_translating_definition_then_creates_code_edge | 100% |
| AC10: confidence=1.0 | test_lsp_type_translation.py | test_given_translation_when_creating_edge_then_confidence_is_1_0 | 100% |
| AC10: lsp: prefix | test_lsp_type_translation.py | test_given_translation_when_creating_edge_then_resolution_rule_has_prefix | 100% |
| AC17: Real Pyright | test_lsp_pyright.py | test_given_python_project_when_get_definition_then_returns_code_edge | 100% |

**Overall Coverage Confidence: 100%** - All ACs explicitly mapped to tests with criterion IDs.

---

## G) Commands Executed

```bash
# Tests (31/31 pass)
uv run pytest tests/unit/adapters/test_lsp_type_translation.py \
  tests/integration/test_lsp_pyright.py \
  tests/unit/adapters/test_lsp_adapter.py \
  tests/unit/adapters/test_lsp_adapter_fake.py -v

# Static checks
uv run ruff check src/fs2/core/adapters/lsp_adapter_solidlsp.py  # clean
uv run mypy src/fs2/core/adapters/lsp_adapter_solidlsp.py --strict  # clean
```

---

## H) Decision & Next Steps

**Decision**: REQUEST_CHANGES

**Required Before Merge**:
1. Fix security issues (SEC-001, SEC-002) - Path traversal protection
2. Fix correctness issues (COR-001, COR-002) - Defensive dict access
3. Sync footnote ledger (LINK-001) - Add `[^14]` to plan or update dossier

**Recommended (Non-Blocking)**:
4. Remove dead code (COR-004)
5. Replace asserts with explicit checks (COR-003)

**Approvers**: Technical Lead or Security Review (for path traversal)

**After Fixes**: Re-run `/plan-7-code-review --phase "Phase 3"` to verify

---

## I) Footnotes Audit

| Diff-Touched File | Footnote Tag | Node ID(s) in Plan Ledger |
|-------------------|--------------|---------------------------|
| src/fs2/core/adapters/lsp_adapter_solidlsp.py | [^13] | `class:src/fs2/core/adapters/lsp_adapter_solidlsp.py:SolidLspAdapter` |
| tests/integration/test_lsp_pyright.py | [^13] | `file:tests/integration/test_lsp_pyright.py` |
| tests/unit/adapters/test_lsp_type_translation.py | [^13] | `file:tests/unit/adapters/test_lsp_type_translation.py` |

**Note**: Dossier Phase Footnote Stubs references `[^14]` but plan only defines `[^13]`. Ledgers out of sync.
