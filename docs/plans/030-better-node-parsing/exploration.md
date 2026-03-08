# Exploration Dossier: Fix Anonymous TS Node Extraction

**Feature**: Stop fs2's TypeScript/TSX parser producing thousands of useless anonymous `@line.column` nodes
**Branch**: `030-better-node-parsing`
**Date**: 2026-03-08
**Research Method**: 8 parallel subagents (FlowSpace + FastCode multi-graph analysis)

---

## Problem Statement

When scanning a TypeScript/TSX codebase (Chainglass, 450MB graph), fs2 produces **13,649 anonymous `@line.column` nodes** — 58.6% of the graph. These nodes:
- Have no useful name (e.g., `callable:test.ts:@19.29`)
- Consume 67% of total text storage (13.5 MB)
- Waste ~11K LLM calls for smart content generation
- Waste ~13.5K embedding API calls (~54 MB embedding data)
- Make tree/search output nearly unusable

**Dominant offender**: `arrow_function` at 84% (11,456 nodes) — mostly test callbacks (`describe(() => {`, `it(() => {`), React handlers, and promise chains.

---

## Root Cause

**Location**: `src/fs2/core/adapters/ast_parser_impl.py` lines 658-667

```python
name = self._extract_name(child, language)
if name is None:
    # Anonymous node - use position-based ID per CF11
    line = child.start_point[0] + 1
    col = child.start_point[1]
    name = f"@{line}.{col}"   # ← CREATES UNWANTED NODES
```

**Three-stage failure chain**:
1. `classify_node()` maps `arrow_function` → `"callable"` (substring match on "function")
2. `_extract_name()` correctly returns `None` (no identifier child)
3. Parser synthesizes `@line.col` name instead of skipping → anonymous node created

**FastCode's solution** (`~/github/fastcode/fastcode/parser.py:665`): Returns `None` for unnamed functions, caller filters with `if func_info:`, but **still recurses into children** to find named functions nested inside callbacks.

---

## Key Research Findings

### Architecture & Implementation

| ID | Finding | Source |
|----|---------|--------|
| IA-04 | Root cause is 8 lines at ast_parser_impl.py:659-667 — name synthesis instead of filtering | Implementation Archaeologist |
| IA-07 | FastCode's `_extract_js_function()` returns None for unnamed + caller filters + recurses | Implementation Archaeologist |
| DC-09 | Fix location confirmed: ast_parser_impl.py:658-666, extend with skip logic | Dependency Cartographer |
| PS-03 | Two-tier skip pattern exists: `skip_entirely` (hard stop) + `container_types` (skip but traverse) | Pattern Scout |
| PS-05 | `@line.col` naming (CF11) is intentional and correct — problem is over-extraction | Pattern Scout |

### Interfaces & Contracts

| ID | Finding | Source |
|----|---------|--------|
| IC-01 | ASTParser ABC returns ALL structural elements — no filtering contract | Interface Analyst |
| IC-05 | `_extract_name()` returns None for anonymous classes, lambdas, default exports, computed props | Interface Analyst |
| IC-10 | Removing anonymous nodes requires coordinated changes across 10+ interfaces | Interface Analyst |

### Domain Boundaries

| ID | Finding | Source |
|----|---------|--------|
| DB-02 | Fix belongs in language handler layer OR inline in parser (debate) | Domain Scout |
| DB-04 | Node ID is critical cross-domain contract — uniqueness must be preserved | Domain Scout |
| DB-05 | Language Handler is architecturally correct location for language-specific logic | Domain Scout |

### Testing & Quality

| ID | Finding | Source |
|----|---------|--------|
| QT-01 | 103 existing parser tests across 2,691 LOC — well structured | Quality Investigator |
| QT-02 | 4 TypeScript fixture files exist but NO tests for anonymous node production | Quality Investigator |
| QT-10 | **CRITICAL GAP**: Zero regression tests for TypeScript @line.column production | Quality Investigator |
| QT-04 | Language handler framework well-tested — PythonHandler pattern proven | Quality Investigator |

### Documentation & Prior Art

| ID | Finding | Source |
|----|---------|--------|
| DE-01 | CF11 specifies position-based naming — format is correct, usage is too broad | Documentation Historian |
| DE-04 | Language handler system documented in plan 008 phase 6 subtask 002 | Documentation Historian |
| PL-05 | Inline `skip_when_anonymous` preferred over TypeScript handler (named arrow fns need extraction) | Prior Learnings Scout |

---

## Design Decision: Inline Skip vs TypeScript Handler

### Option A: Inline `skip_when_anonymous` set (RECOMMENDED)

Add a `skip_when_anonymous` set in `_extract_nodes()` — when `_extract_name()` returns None AND `ts_kind` is in this set, skip node creation but still recurse into children.

**Pros**:
- Minimal change (single `if` block)
- Preserves named arrow function extraction (`const handler = () => {}`)
- Cross-language — these ts_kinds appear in JS, TS, and TSX grammars
- Follows FastCode's proven pattern
- `container_types` mechanism would skip extraction AND name lookup — too aggressive

**Cons**:
- Language-specific logic in parser core (not in handler)

### Option B: TypeScript Language Handler

Create `TypeScriptHandler` with expanded `container_types`.

**Pros**:
- Follows established PythonHandler pattern
- Clean Architecture — language logic in handler layer

**Cons**:
- `container_types` skips extraction AND recursion differently — would miss named arrow functions
- Need to register for 3 languages (typescript, tsx, javascript)
- Over-engineering for what's essentially a 10-line fix

### Decision: **Option A** — inline `skip_when_anonymous`

The workshop analysis and FastCode comparison both confirm the inline approach is more precise. The `container_types` mechanism is designed for structural wrappers (like Python's `block`), not for conditionally-anonymous constructs like `arrow_function`.

---

## Existing Skip Infrastructure

### `skip_entirely` set (ast_parser_impl.py:611-618)
Hard stop — don't extract AND don't recurse. Currently covers parameter-related types.

### `container_types` (language handlers)
Skip extraction but DO recurse. Python adds `"block"`. Default handler has ~8 structural wrapper types.

### NEW: `skip_when_anonymous` (proposed)
Skip extraction when unnamed, but DO recurse into children. Applied AFTER `_extract_name()` returns None.

```
skip_entirely       → don't extract, don't recurse (parameters)
container_types     → don't extract, DO recurse (structural wrappers)
skip_when_anonymous → don't extract WHEN UNNAMED, DO recurse (anonymous callbacks)
```

---

## Files That Must Change

### Primary (Implementation)
1. **`src/fs2/core/adapters/ast_parser_impl.py`** — Add `skip_when_anonymous` logic after line 659
   - Define the set of ts_kinds to skip when anonymous
   - When name is None AND ts_kind in set: recurse into children, then `continue`
   - Preserve existing `@line.col` fallback for other anonymous nodes

### Testing
2. **`tests/unit/adapters/test_ast_parser_impl.py`** — Add TypeScript anonymous node tests
3. **`tests/fixtures/ast_samples/typescript/`** — Add fixture with anonymous arrow functions
4. Possibly **`tests/unit/models/test_code_node.py`** — Verify classify_node coverage

### No Changes Needed
- `code_node.py` — `classify_node()` is correct (category mapping unchanged)
- `ast_languages/` — No new handler needed (inline approach)
- `graph_store*.py` — Storage unchanged
- `scan_pipeline.py` — Pipeline unchanged
- MCP server — Automatically benefits (fewer useless nodes)

---

## The `skip_when_anonymous` Set

From workshop analysis + FastCode comparison:

```python
skip_when_anonymous = {
    "arrow_function",       # 11,456 nodes — callbacks, handlers
    "function",             # Anonymous function expressions
    "function_expression",  # Same
    "generator_function",   # Anonymous generators
    "interface_body",       # 1,176 nodes — body of interface (parent has name)
    "class_body",           # 220 nodes — body of class (parent has name)
    "class_heritage",       # 192 nodes — extends/implements (parent has context)
    "enum_body",            # 2 nodes — body of enum (parent has name)
    "function_type",        # 602 nodes — type annotations like (x: string) => boolean
    "implements_clause",    # 1 node — implements Foo
}
```

**Expected impact**: Eliminates ~13,649 anonymous nodes. Graph drops from 23,283 → ~10,000 nodes. File size from 450MB → ~150-200MB.

---

## Backward Compatibility

### Low Risk
- New scans produce fewer, better nodes — this is improvement, not breakage
- No graph format version change needed (same CodeNode structure)
- Named nodes unchanged — only anonymous nodes removed
- Search quality improves (less noise)
- Smart content/embedding costs decrease dramatically

### Medium Risk
- Existing graphs still contain anonymous nodes until re-scanned
- Tests asserting specific node counts will need updating
- Any agent workflow relying on `@line.col` node IDs will see them disappear on rescan

### Mitigation
- Re-scanning is already expected when parser logic changes
- Node count assertions in tests should be updated to reflect correct behavior

---

## Testing Strategy

1. **New TypeScript fixture** with anonymous arrow functions, named arrow functions, interfaces, classes
2. **Positive test**: Named arrow function `const handler = () => {}` IS extracted
3. **Negative test**: Anonymous callback `describe(() => {})` is NOT extracted as standalone node
4. **Recursion test**: Named function INSIDE anonymous callback IS extracted
5. **Regression test**: Existing Python, Rust, Go tests still pass
6. **Integration test**: Scan TypeScript fixture, assert zero `@` in node names for skip_when_anonymous types

---

## Verification Plan

After implementation, re-scan the Chainglass project:
```bash
cd /Users/jordanknight/substrate/066-wf-real-agents
uv run --project /path/to/030-better-node-parsing fs2 scan --no-smart-content --no-embeddings
```

**Expected**: @anonymous nodes drop from ~13,649 to near zero. Total nodes ~10,000-12,000.

---

## Discoveries & Learnings

### D1: FastCode's Elegant Simplicity
FastCode's `return None` + `if func_info:` pattern is remarkably simple compared to fs2's complex @line.col synthesis. The key insight: **anonymous functions don't need nodes — their content is already captured by parent nodes.**

### D2: container_types vs skip_when_anonymous
These are fundamentally different mechanisms. `container_types` always skips (Python's `block` is never useful). `skip_when_anonymous` is conditional — `arrow_function` should be extracted when named but skipped when anonymous.

### D3: Dual Classification is Correct but Coarse
`classify_node()` correctly maps ts_kinds to categories via substring matching. The issue isn't classification — it's that ALL classified nodes get extracted regardless of whether they have meaningful names.

### D4: Testing Gap is Critical
Zero tests for TypeScript anonymous node production despite 103 parser tests. This is the #1 thing to fix — tests should prevent regression.

### D5: Three-Tier Skip Architecture
The fix creates a clean three-tier hierarchy: `skip_entirely` (hard stop) → `container_types` (structural wrappers) → `skip_when_anonymous` (conditional on name). This is a reusable pattern for future language-specific filtering.
