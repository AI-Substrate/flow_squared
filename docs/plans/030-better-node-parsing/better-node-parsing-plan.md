# Better Node Parsing Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-03-08
**Spec**: `better-node-parsing-spec.md`
**Status**: DRAFT

## Summary

fs2's TypeScript/TSX parser produces 13,649 useless anonymous `@line.column` nodes (58.6% of the graph) because `_extract_nodes()` synthesizes position-based names instead of skipping unnamed nodes for specific tree-sitter kinds. The fix adds a `SKIP_WHEN_ANONYMOUS` constant — a set of 10 ts_kinds — that triggers "skip this node but recurse into children" when `_extract_name()` returns None. This follows FastCode's proven pattern and is a surgical 10-line change to the extraction loop, plus new TypeScript test fixtures and regression tests.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| AST Parsing (`adapters/ast_parser*`) | existing | **modify** | Add `SKIP_WHEN_ANONYMOUS` logic to `_extract_nodes()` |
| CodeNode Model (`models/code_node*`) | existing | consume | Unchanged |
| Language Support (`adapters/ast_languages/`) | existing | consume | Unchanged |
| Scan Pipeline (`services/stages/`) | existing | consume | Benefits from fewer nodes |
| Graph Storage (`repos/graph_store*`) | existing | consume | Unchanged |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/core/adapters/ast_parser_impl.py` | AST Parsing | internal | Add `SKIP_WHEN_ANONYMOUS` set and conditional skip logic |
| `tests/fixtures/ast_samples/typescript/anonymous_callbacks.ts` | AST Parsing | internal | New fixture: anonymous arrow functions, callbacks, nested named fns |
| `tests/fixtures/ast_samples/typescript/anonymous_bodies.ts` | AST Parsing | internal | New fixture: interface_body, class_body, enum_body, class_heritage, function_type |
| `tests/unit/adapters/test_ast_parser_skip_anonymous.py` | AST Parsing | internal | New test file: TDD tests for skip_when_anonymous behavior |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | Root cause is `ast_parser_impl.py:660-666` — when `_extract_name()` returns None, code synthesizes `@line.col` name instead of skipping. The fix inserts a conditional check AFTER line 659 and BEFORE line 660. | T003: Add SKIP_WHEN_ANONYMOUS check |
| 02 | Critical | Recursion into children MUST be preserved when skipping — named functions nested inside anonymous callbacks must still be extracted (FastCode pattern). | T003: Use same recurse-and-continue pattern as `container_types` block at lines 627-639 |
| 03 | High | `_extract_name()` returns None for anonymous `arrow_function` nodes because they have no `identifier` child. Named arrow fns (`const handler = () => {}`) ARE extracted correctly — the identifier lives on the parent `variable_declarator`, not the arrow_function itself. | T001: Test fixture must cover both named and anonymous arrow functions |
| 04 | High | Existing `skip_entirely` set (lines 611-618) does NOT recurse; `container_types` (lines 624-639) DOES recurse. The new `SKIP_WHEN_ANONYMOUS` follows the `container_types` pattern (skip + recurse). | T003: Model code on lines 627-639 |
| 05 | Medium | Zero existing tests for TypeScript anonymous node production despite 103 parser tests and 4 TS fixture files. | T001-T002: Create fixtures and tests FIRST (TDD) |
| 06 | Medium | The `ast_samples_path` fixture in `conftest.py:168` provides path to `tests/fixtures/ast_samples/` — new TS fixtures go in the existing `typescript/` subdirectory. | T001: Place fixtures at standard location |

## Harness Strategy

Harness: Not applicable (user override — parser change validated by unit/integration tests, no runtime server needed).

## Implementation

**Objective**: Add `SKIP_WHEN_ANONYMOUS` mechanism to `_extract_nodes()` that skips anonymous nodes for 10 specific ts_kinds while recursing into their children.
**Testing Approach**: Hybrid — TDD for skip logic, integration for full-file scanning.
**Complexity**: CS-2 (small)

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [ ] | T001 | Create TypeScript test fixtures for anonymous node scenarios | AST Parsing | `/Users/jordanknight/substrate/fs2/030-better-node-parsing/tests/fixtures/ast_samples/typescript/anonymous_callbacks.ts`, `/Users/jordanknight/substrate/fs2/030-better-node-parsing/tests/fixtures/ast_samples/typescript/anonymous_bodies.ts` | Fixtures contain: (a) anonymous arrow callbacks (`describe(() => {})`), (b) named arrow function (`const handler = () => {}`), (c) named function nested inside anonymous callback, (d) interface_body, class_body, class_heritage, enum_body, function_type, implements_clause examples | TDD — fixtures first |
| [ ] | T002 | Write TDD tests for skip_when_anonymous behavior | AST Parsing | `/Users/jordanknight/substrate/fs2/030-better-node-parsing/tests/unit/adapters/test_ast_parser_skip_anonymous.py` | Tests cover: (a) anonymous arrow_function → no `@line.col` node, (b) named arrow function → callable node with correct name, (c) named function inside anonymous callback → still extracted, (d) all 10 skip_when_anonymous ts_kinds covered, (e) tests FAIL before implementation | TDD — red phase. Per finding 05 |
| [ ] | T003 | Implement `SKIP_WHEN_ANONYMOUS` logic in `_extract_nodes()` | AST Parsing | `/Users/jordanknight/substrate/fs2/030-better-node-parsing/src/fs2/core/adapters/ast_parser_impl.py` | (a) Module-level constant `SKIP_WHEN_ANONYMOUS` with 10 ts_kinds, (b) After `_extract_name()` returns None on line 659: if ts_kind in set → recurse into children and `continue`, (c) Preserve `@line.col` fallback for other anonymous nodes, (d) All T002 tests pass | Per findings 01, 02, 04. Model on lines 627-639 |
| [ ] | T004 | Run full existing test suite — verify no regressions | AST Parsing | `/Users/jordanknight/substrate/fs2/030-better-node-parsing/tests/` | `uv run pytest tests/ -x -q` passes. All existing Python/Rust/Go parser tests unchanged. | AC5, AC6 |

### Acceptance Criteria

- [ ] AC1: Anonymous arrow function callbacks produce zero `@line.column` nodes
- [ ] AC2: Named arrow function (`const handler = () => {}`) produces callable node with name `handler`
- [ ] AC3: Named function nested inside anonymous callback is still extracted
- [ ] AC4: `interface_body`, `class_body`, `class_heritage`, `enum_body`, `function_type`, `implements_clause` produce no `@line.column` nodes
- [ ] AC5: Existing Python parsing tests pass unchanged
- [ ] AC6: Existing Rust, Go, and other language tests pass unchanged
- [ ] AC7: New TypeScript-specific tests cover all 10 `skip_when_anonymous` node kinds
- [ ] AC8: `SKIP_WHEN_ANONYMOUS` is a clear, documented module-level constant
- [ ] AC9: Re-scanning Chainglass project reduces anonymous nodes from ~13,649 to near zero (manual)

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Named arrow functions misidentified as anonymous | Low | Medium | T002 test covers this case explicitly; `_extract_name()` finds identifiers via parent `variable_declarator` |
| Some legitimate anonymous construct skipped | Low | Low | Set curated from real-world analysis of 13,649 nodes; extend later if needed |
| Existing tests break due to node count changes | Low | Low | T004 catches this; update assertions to reflect correct behavior |
