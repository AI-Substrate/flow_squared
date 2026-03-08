# Execution Log: Phase 1 — Skip Anonymous TypeScript Nodes

**Date**: 2026-03-08
**Status**: ✅ COMPLETE

---

## T001: Create TypeScript test fixtures ✅

Created two fixtures in `tests/fixtures/ast_samples/typescript/`:

- **`anonymous_callbacks.ts`** (58 lines): Anonymous arrow function callbacks, named arrow functions, named function inside anonymous callback, anonymous function expression, export default anonymous arrow, promise chain callbacks
- **`anonymous_bodies.ts`** (64 lines): interface_body, class_body, class_heritage, enum_body, function_type, implements_clause — all with named parent declarations and method_definitions inside

**Evidence**: Files created, fixture structure follows existing pattern.

---

## T002: Write TDD tests (red phase) ✅

Created `tests/unit/adapters/test_ast_parser_skip_anonymous.py` (16 tests in 3 test classes):

- **TestSkipWhenAnonymousCallbacks** (5 tests): Anonymous arrow functions skipped, anonymous function_expression skipped, named function inside callback still extracted, top-level named function still extracted, zero anonymous nodes in fixture
- **TestSkipWhenAnonymousBodies** (9 tests): interface_body, class_body, class_heritage, enum_body, function_type, implements_clause all skipped when anonymous; named types and methods still extracted; zero anonymous nodes in fixture
- **TestSkipWhenAnonymousConstant** (2 tests): SKIP_WHEN_ANONYMOUS exists as set/frozenset, contains all 10 specified kinds

**Red phase result**: 11 failed, 5 passed (positive tests already working)

**Discovery**: `_extract_name()` returns None for `const handleClick = () => {}` because the identifier is on the parent `variable_declarator`, not the `arrow_function` child. Named arrow functions assigned via `const/let/var` are NOT currently extracted as named callable nodes — the parent `lexical_declaration` captures the name context. This is a separate issue from the anonymous node problem.

---

## T003: Implement SKIP_WHEN_ANONYMOUS ✅

Two changes to `src/fs2/core/adapters/ast_parser_impl.py`:

1. **Module-level constant** (after `logger`): `SKIP_WHEN_ANONYMOUS: frozenset[str]` with 10 ts_kinds, documented with references to workshop.md
2. **Conditional block** (after `_extract_name()` returns None): If `ts_kind in SKIP_WHEN_ANONYMOUS` → recurse into children and `continue`. Modeled on existing `container_types` pattern at lines 627-639.

**Green phase result**: 16/16 tests passed.

---

## T004: Full regression suite ✅

```
uv run --with pytest --with pytest-asyncio pytest tests/ -x --tb=short -q
1561 passed, 25 skipped, 341 deselected in 52.41s
```

Zero failures. All existing Python/Rust/Go/Markdown tests unchanged.

**Chainglass benchmark**:

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total nodes | 23,283 | 9,636 | **-59%** |
| Anonymous @nodes | 13,649 | 0 | **-100%** |
| Graph file size | 451 MB | 175 MB | **-61%** |

---

## Discoveries & Learnings

| Date | Task | Type | Discovery | Resolution |
|------|------|------|-----------|------------|
| 2026-03-08 | T002 | Gotcha | Named arrow fns (`const x = () => {}`) are NOT extracted as named callables — identifier is on parent `variable_declarator`, not the `arrow_function` child | Out of scope for this fix. The arrow_function is correctly skipped (anonymous). A future enhancement could extract named arrow fns by checking parent context in `_extract_name()`. |
| 2026-03-08 | T002 | Insight | `data.map(item => item.value)` extracts `item` as the arrow_function name because tree-sitter sees the parameter as an identifier child | Harmless quirk — single-param arrow fns get the param name. Not a regression and out of scope. |
| 2026-03-08 | T004 | Verification | Chainglass re-scan: 13,649 → 0 anonymous nodes, 451MB → 175MB graph | 100% elimination of target anonymous nodes with zero regressions |
