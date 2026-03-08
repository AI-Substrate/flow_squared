# Better Node Parsing: Skip Anonymous TypeScript Nodes

**Mode**: Simple

## Research Context

📚 This specification incorporates findings from `exploration.md` and `workshop.md`.

**Key findings**: When scanning TypeScript/TSX codebases, fs2 produces **13,649 anonymous `@line.column` nodes** (58.6% of the graph). These are overwhelmingly anonymous `arrow_function` callbacks (84%), body wrappers (`interface_body`, `class_body`), and type annotations (`function_type`). FastCode's parser already solves this problem by returning `None` for unnamed functions and filtering them out while still recursing into children. The workshop provides a proven fix pattern and a complete `skip_when_anonymous` set of 10 tree-sitter node kinds.

---

## Summary

**WHAT**: When fs2 scans a TypeScript/TSX codebase, every anonymous arrow function, interface body, class body, and function type annotation becomes a standalone node named `@line.column`. These nodes are useless — they have no meaningful name, their content is already captured by parent nodes, and they overwhelm tree/search output. The fix adds a `skip_when_anonymous` mechanism that skips node creation for specific tree-sitter node kinds when no name is found, while still recursing into their children to extract any named functions nested inside.

**WHY**: Anonymous nodes waste resources at every pipeline stage:
- **Storage**: 67% of total text storage (13.5 MB of 20.2 MB)
- **LLM costs**: ~11,000 wasted smart content API calls per scan
- **Embedding costs**: ~13,500 wasted embedding API calls (~54 MB vector data)
- **Graph size**: 450 MB inflated to 2-3× expected size
- **User experience**: Tree and search output is 58% noise, making the tool less useful for its primary audience (AI agents via MCP)

---

## Goals

- **G1**: Eliminate anonymous `@line.column` nodes for tree-sitter kinds that are never useful when unnamed (arrow functions, body wrappers, type annotations, heritage clauses)
- **G2**: Preserve extraction of **named** instances of the same kinds (e.g., `const handler = () => {}` should still produce a callable node)
- **G3**: Preserve extraction of named functions **nested inside** anonymous callbacks (recursion must continue into skipped nodes)
- **G4**: Reduce graph size and API costs for TypeScript/TSX codebases by ~50-60%
- **G5**: Add regression tests preventing anonymous node proliferation from recurring
- **G6**: Maintain backward compatibility — existing Python, Rust, Go, and other language parsing is unchanged

---

## Non-Goals

- **NG1**: Creating a full TypeScript language handler (`TypeScriptHandler`) — the inline `skip_when_anonymous` approach is sufficient and more precise than `container_types`
- **NG2**: Changing the `@line.column` naming convention (CF11) itself — the format is correct; the problem is over-application
- **NG3**: Modifying `classify_node()` — category classification is working correctly
- **NG4**: Adding cross-file symbol resolution or call graph extraction for TypeScript
- **NG5**: Changing the graph storage format or requiring a format version bump
- **NG6**: Retroactively migrating existing graphs — re-scanning is the expected path when parser logic changes

---

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| AST Parsing (adapters/ast_parser*) | existing | **modify** | Add `skip_when_anonymous` logic to `_extract_nodes()` |
| CodeNode Model (models/code_node*) | existing | **consume** | `classify_node()` unchanged; CodeNode structure unchanged |
| Language Support (adapters/ast_languages/) | existing | **consume** | Handler registry unchanged; no new handler needed |
| Scan Pipeline (services/stages/) | existing | **consume** | Pipeline stages unchanged; benefits from fewer nodes |
| Graph Storage (repos/graph_store*) | existing | **consume** | Storage unchanged; smaller graphs as side effect |

ℹ️ No domain registry exists. Domains identified from codebase structure.

---

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=0, D=0, N=0, F=0, T=1
  - **Surface Area (S=1)**: Primary change in one file (`ast_parser_impl.py`), plus new test file and fixtures
  - **Integration (I=0)**: Entirely internal — no external dependencies
  - **Data/State (D=0)**: No schema or storage format changes
  - **Novelty (N=0)**: Well-specified by workshop with proven FastCode reference implementation
  - **Non-Functional (F=0)**: Performance improves (fewer nodes); no security/compliance concerns
  - **Testing/Rollout (T=1)**: Integration-level testing needed (scan TypeScript fixture, verify node counts)
- **Total P**: 2 → CS-2
- **Confidence**: 0.95
- **Assumptions**:
  - The 10 tree-sitter kinds in `skip_when_anonymous` are comprehensive for JS/TS/TSX
  - Named arrow functions (variable assignments) are correctly identified by `_extract_name()`
  - No downstream consumers depend on anonymous node presence for correctness
- **Dependencies**: None — self-contained parser change
- **Risks**: Low — minimal change surface, well-tested existing infrastructure, proven reference pattern

---

## Acceptance Criteria

1. **AC1**: Scanning a TypeScript file containing anonymous arrow function callbacks (e.g., `describe(() => {`, `it(() => {`) produces **zero** `@line.column` callable nodes for those callbacks
2. **AC2**: Scanning a TypeScript file containing a **named** arrow function (`const handler = () => {}`) produces a callable node with name `handler`
3. **AC3**: A named function **nested inside** an anonymous callback is still extracted (recursion into skipped nodes works)
4. **AC4**: `interface_body`, `class_body`, `class_heritage`, `enum_body`, `function_type`, and `implements_clause` nodes do not produce `@line.column` nodes when anonymous
5. **AC5**: Existing Python parsing tests pass unchanged
6. **AC6**: Existing Rust, Go, and other language tests pass unchanged
7. **AC7**: New TypeScript-specific tests cover all 10 `skip_when_anonymous` node kinds
8. **AC8**: The `skip_when_anonymous` set is defined as a clear, documented constant (not inline magic)
9. **AC9**: Re-scanning the Chainglass project reduces anonymous nodes from ~13,649 to near zero (manual verification)

---

## Risks & Assumptions

### Risks
- **R1** (Low): Some legitimate anonymous construct may be in the `skip_when_anonymous` set — mitigated by the set being curated from real-world graph analysis (13,649 nodes examined)
- **R2** (Low): `_extract_name()` may not correctly identify named arrow functions in all cases (e.g., destructured assignments) — mitigated by existing test coverage of `_extract_name()`
- **R3** (Low): Tests asserting specific node counts may need updating — expected and straightforward

### Assumptions
- **A1**: The `@line.column` naming convention (CF11) remains correct for other legitimate anonymous constructs (e.g., Python lambdas)
- **A2**: No MCP consumer workflow depends on the existence of anonymous TypeScript nodes
- **A3**: The tree-sitter grammar for TypeScript/TSX/JavaScript uses the same node kind names (`arrow_function`, `interface_body`, etc.)

---

## Testing Strategy

- **Approach**: Hybrid (TDD for core skip logic, lightweight for integration)
- **Rationale**: The `skip_when_anonymous` logic is the critical new behavior — TDD ensures it works for all 10 node kinds and the recursion contract. Integration tests (scan TS fixture, count nodes) provide confidence without being brittle.
- **Focus Areas**:
  - TDD: Each node kind in `skip_when_anonymous` — anonymous → skipped, named → extracted
  - TDD: Recursion into skipped nodes finds nested named functions
  - Integration: Scan TypeScript fixture, verify zero `@line.col` nodes for skip kinds
  - Regression: Existing Python/Rust/Go tests pass unchanged
- **Mock Usage**: Avoid mocks — use real tree-sitter parsing with fixture files (project convention: fakes over mocks)
- **Excluded**: No performance benchmarking, no load testing

---

## Documentation Strategy

- **Location**: No new documentation
- **Rationale**: Internal parser change. The `skip_when_anonymous` set is self-documenting via code comments. Workshop.md serves as the design record.

---

## Open Questions

All resolved — see Clarifications.

---

## Clarifications

### Session 2026-03-08

**Q1: Workflow Mode** → **Simple** (CS-2 task, single phase, quick path)

**Q2: Testing Strategy** → **Hybrid** (TDD for skip logic, lightweight for integration)

**Q3: Documentation Strategy** → **No new documentation** (internal parser change)

**Q4: Domain Review** → **No new domains** (all existing, only AST Parsing modified)

**Q5: OQ1 — Anonymous default exports** → **Skip** — file-level node captures the content, no need for a separate `@line.col` node for `export default () => { ... }`

**Q6: OQ2 — Skip set completeness** → **10 kinds from workshop are sufficient**. Start with the curated set derived from real-world analysis of 13,649 nodes. Extend later if needed.

**Q7: Harness** → No agent harness exists. Feature doesn't need one — parser change validated by unit/integration tests.
