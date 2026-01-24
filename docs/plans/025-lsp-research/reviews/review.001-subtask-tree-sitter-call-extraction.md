# Code Review: Phase 8 Subtask 001 - Tree-Sitter Call Extraction

**Plan**: `/workspaces/flow_squared/docs/plans/025-lsp-research/lsp-integration-plan.md`
**Phase**: Phase 8: Pipeline Integration
**Subtask**: 001-subtask-tree-sitter-call-extraction
**Review Date**: 2026-01-24
**Reviewer**: Claude Code (plan-7-code-review)

---

## A) Verdict

**REQUEST_CHANGES**

Issues found that require attention before merge:
1. **HIGH**: Missing footnote entry in plan ledger (graph integrity)
2. **HIGH**: mypy --strict failures (7 type annotation errors)
3. **MEDIUM**: Minor architectural deviation from dossier

---

## B) Summary

The implementation of Tree-Sitter call extraction for Subtask 001 is **functionally complete** with all tests passing (20/20). The core functionality works correctly:

- `extract_call_positions()` correctly identifies call sites in Python, TypeScript, JavaScript, TSX, Go, and C#
- Method calls correctly return method name position (not receiver position)
- LSP `get_definition` integration creates CALLS edges with proper symbol-level resolution
- Stdlib filtering prevents edges to standard library targets

**Blocking issues**:
1. Plan ledger missing footnote for this subtask (required for graph traversability)
2. mypy --strict fails with 7 type annotation errors in new code

**Non-blocking observations**:
- Implementation re-parses content instead of using pre-computed `call_sites` field (deviation from documented architecture, but functional)
- One execution log task shows "In Progress" status instead of "Complete" (cosmetic)

---

## C) Checklist

**Testing Approach: Full TDD**

- [x] Tests precede code (RED-GREEN evidence documented in execution log)
- [x] Tests as docs (assertions show behavior, comprehensive docstrings)
- [x] Mock usage matches spec: N/A (no mocks used - real LSP in integration tests)
- [x] Negative/edge cases covered (unknown language, empty content, no calls)

**Universal:**

- [x] BridgeContext patterns: N/A (Python implementation, not VS Code extension)
- [x] Only in-scope files changed (relationship_extraction_stage.py + 2 test files)
- [ ] **Linters/type checks are clean** - mypy fails with 7 errors
- [x] Absolute paths used: N/A (relative paths from project root)

---

## D) Findings Table

| ID | Severity | File:Lines | Summary | Recommendation |
|----|----------|------------|---------|----------------|
| LINK-001 | HIGH | Plan ledger | Subtask 001 completed but no footnote entry [^21] in plan ledger | Add footnote documenting implementation |
| LINK-002 | MEDIUM | Dossier:566 | Phase Footnote Stubs table is empty | Populate with implementation reference |
| TYPE-001 | HIGH | relationship_extraction_stage.py:107 | mypy error: get_parser argument type | Add proper type annotation or cast |
| TYPE-002 | HIGH | relationship_extraction_stage.py:118 | Missing type annotation for get_query_position | Add type hints |
| TYPE-003 | HIGH | relationship_extraction_stage.py:148 | Missing type annotation for visit() | Add type hints |
| TYPE-004 | HIGH | relationship_extraction_stage.py:162 | Missing type annotation for _find_method_identifier | Add type hints |
| PLAN-001 | MEDIUM | relationship_extraction_stage.py:482 | Re-parses content instead of using node.call_sites | Document deviation or refactor |
| TDD-001 | LOW | execution.log.md | ST003 status shows "In Progress" with completed timestamp | Update status indicator |
| LOG-001 | LOW | execution.log.md | ST001 has no log entry (noted as pre-completed) | Add brief log entry |

---

## E) Detailed Findings

### E.0) Cross-Phase Regression Analysis

**Verdict**: PASS (Full Mode - Phase 8 is later phase)

No regressions detected. Existing Phase 8 tests continue to pass. The new code is additive to `_extract_lsp_relationships()` without modifying existing get_references logic.

### E.1) Doctrine & Testing Compliance

#### Graph Integrity Violations (Step 3a)

**LINK-001 (HIGH)**: Subtask 001 completed all 6 tasks but has NO corresponding footnote entry in the plan's Change Footnotes Ledger. The last footnote is [^20] (Phase 9 Documentation).

**Impact**: Cannot traverse from changed files back to implementation tasks.

**Fix**: Add footnote [^21] to Change Footnotes Ledger:
```markdown
[^21]: Phase 8 Subtask 001 - Tree-Sitter Call Extraction
  - `function:src/fs2/core/services/stages/relationship_extraction_stage.py:extract_call_positions`
  - `function:src/fs2/core/services/stages/relationship_extraction_stage.py:_find_method_identifier`
  - `function:src/fs2/core/services/stages/relationship_extraction_stage.py:is_stdlib_target`
  - `file:tests/unit/services/stages/test_call_extraction.py` - 17 unit tests
  - `file:tests/integration/test_call_extraction_integration.py` - 3 integration tests
```

**LINK-002 (MEDIUM)**: Phase Footnote Stubs table in subtask dossier (line 566) is empty despite subtask completion.

**Fix**: Populate Phase Footnote Stubs table with reference to [^21].

#### TDD Compliance

**Verdict**: PASS

Evidence from execution log shows correct TDD order:
- ST002 (unit tests) completed at 23:15 BEFORE ST003 (implementation) started
- ST004 (integration tests) completed at 23:30 BEFORE ST005 (integration) started

RED-GREEN evidence documented:
- RED: ImportError (function doesn't exist)
- GREEN: 17/17 unit tests pass, 3/3 integration tests pass

Test documentation quality is excellent with Given-When-Then naming and comprehensive docstrings.

### E.2) Semantic Analysis

**Verdict**: PASS

The implementation correctly:
1. Extracts call positions from AST using tree-sitter
2. Returns method name position (not receiver) for method calls
3. Filters stdlib targets using pattern matching
4. Creates CALLS edges with `resolution_rule="lsp:definition"`

No domain logic violations detected.

### E.3) Quality & Safety Analysis

**Safety Score: 88/100** (0 CRITICAL, 2 HIGH [type errors], 1 MEDIUM, 2 LOW)

#### Type Errors (TYPE-001 through TYPE-004)

**Severity**: HIGH (blocks strict type checking)

mypy --strict output:
```
relationship_extraction_stage.py:107: error: Argument 1 to "get_parser" has incompatible type "str"
relationship_extraction_stage.py:118: error: Function is missing a type annotation
relationship_extraction_stage.py:148: error: Function is missing a type annotation
relationship_extraction_stage.py:162: error: Function is missing a return type annotation
```

**Fix**: Add type annotations to inner functions:

```python
# Line 118
def get_query_position(call_node: Any) -> tuple[int, int]:
    ...

# Line 148
def visit(node: Any) -> None:
    ...

# Line 162
def _find_method_identifier(access_node: Any, language: str) -> Any | None:
    ...
```

For line 107, cast the language parameter:
```python
from typing import cast
parser = get_parser(cast(Language, language))
```

#### Correctness Observations

**COR-001 (LOW)**: `source_line=node.start_line + rel_line` at line 513 stores a value that's never used (source is already symbol-level for get_definition edges). Not a bug but unnecessary computation.

**COR-002 (LOW)**: Language parameter not normalized for case sensitivity. If language is "Python" instead of "python", extraction silently returns empty. Minor since tree-sitter languages are lowercase by convention.

#### Security Assessment

No security vulnerabilities detected. File paths come from tree-sitter and LSP responses, not user input.

### E.4) Doctrine Evolution Recommendations

**ADR Candidate**: None identified - implementation follows existing patterns.

**Rules Candidate**: Consider documenting the 0-indexed vs 1-indexed convention:
- tree-sitter positions: 0-indexed
- CodeNode.start_line: 1-indexed
- LSP lines: 0-indexed
- find_node_at_line: expects 1-indexed

**Idioms Candidate**: The pattern of extracting AST positions then querying LSP could be documented as a standard approach for future extractors.

---

## F) Coverage Map

| Acceptance Criterion | Test | Confidence |
|---------------------|------|------------|
| ST001: Document call node types | N/A (documentation task) | 100% |
| ST002: Unit tests for extract_call_positions | test_call_extraction.py (17 tests) | 100% |
| ST003: Implement extract_call_positions | All 17 unit tests pass | 100% |
| ST004: Integration tests for outgoing calls | test_call_extraction_integration.py (3 tests) | 100% |
| ST005: Integrate with _extract_lsp_relationships | test_given_python_function_with_call_when_scanned_then_creates_calls_edge | 100% |
| ST006: Validate outgoing call edges | test_given_cross_file_call_when_scanned_then_resolves_to_target_method | 100% |

**Overall Coverage Confidence**: 100% - All acceptance criteria have explicit test coverage.

---

## G) Commands Executed

```bash
# Tests
uv run pytest tests/unit/services/stages/test_call_extraction.py tests/integration/test_call_extraction_integration.py -v --no-cov
# Result: 20 passed in 6.89s

# Linting
uv run ruff check src/fs2/core/services/stages/relationship_extraction_stage.py
# Result: All checks passed!

# Type checking
uv run mypy src/fs2/core/services/stages/relationship_extraction_stage.py --strict
# Result: 7 errors (missing type annotations)
```

---

## H) Decision & Next Steps

**Verdict**: REQUEST_CHANGES

**Required Fixes** (must address before approval):

1. **Add footnote [^21]** to plan's Change Footnotes Ledger documenting this subtask
2. **Fix mypy errors** by adding type annotations to inner functions in relationship_extraction_stage.py

**Optional Improvements** (nice to have):

3. Populate Phase Footnote Stubs table in subtask dossier
4. Update ST003 status in execution log from "In Progress" to "Complete"
5. Add brief log entry for ST001 referencing research dossier

**After Fixes**: Rerun `/plan-7-code-review` to verify → APPROVE → merge

---

## I) Footnotes Audit

| Diff-Touched Path | Footnote Tag(s) | Plan Ledger Node-IDs |
|-------------------|-----------------|----------------------|
| src/fs2/core/services/stages/relationship_extraction_stage.py | **MISSING** | N/A |
| tests/unit/services/stages/test_call_extraction.py (new) | **MISSING** | N/A |
| tests/integration/test_call_extraction_integration.py (new) | **MISSING** | N/A |

**Status**: INCOMPLETE - All modified/created files lack footnote documentation.

**Required Action**: Add [^21] to plan ledger with FlowSpace node IDs for all implementation artifacts.
