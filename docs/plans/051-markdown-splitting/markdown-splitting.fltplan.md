# ✈️ Flight Plan: Markdown Section Splitting

**Status**: Landed
**Plan**: [`markdown-splitting-plan.md`](./markdown-splitting-plan.md)
**Spec**: [`markdown-splitting-spec.md`](./markdown-splitting-spec.md)
**Research**: [`research-dossier.md`](./research-dossier.md)
**Mode**: Simple
**Complexity**: CS-2 (small) — 2 points

---

## Mission

Enable sub-file search resolution for markdown documents by splitting `.md` files into `section:` nodes at H2 (`##`) heading boundaries during `fs2 scan`.

## Before → After

```
BEFORE (file-level only)                 AFTER (section-level)
─────────────────────────                ─────────────────────
file:docs/plan.md                        file:docs/plan.md
  (1828 lines, single node)                ├── section:docs/plan.md:Plan Title
                                           ├── section:docs/plan.md:Executive Summary
                                           ├── section:docs/plan.md:Technical Context
                                           ├── section:docs/plan.md:Implementation Phases
                                           ├── section:docs/plan.md:Testing Philosophy
                                           └── section:docs/plan.md:Progress Tracking

Search "testing philosophy"              Search "testing philosophy"
→ Returns entire 1828-line file          → Returns 20-line Testing Philosophy section ✅
```

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Split level | H2 (`##`) | Empirical: 92.1% of H2 chunks in 5–200 line sweet spot |
| Implementation | Hand-rolled splitter | Tree-sitter produces 14,454 nodes/file (99.5% noise) |
| Dependencies | None (stdlib only) | Zero new packages |
| Node model | Existing `CodeNode.create_section()` | Already supports section category and IDs |
| Collision handling | `@{line}` suffix | Matches existing parser convention |
| Preamble naming | H1 title → "Preamble" fallback | Preserves document title in search |
| Testing | Full TDD, no mocks | Pure-function logic, real fixtures |

## Implementation (Simple Mode — Single Phase)

| ID | Task | Done When |
|----|------|-----------|
| T001 | Create 8+ markdown test fixtures | Fixtures cover all AC edge cases |
| T002 | Write failing unit tests | All tests written and RED |
| T003 | Implement `MarkdownSectionSplitter` | All unit tests GREEN |
| T004 | Integrate into `TreeSitterParser.parse()` | Markdown → file + section nodes |
| T005 | Write integration test | Graph, tree, search all work |
| T006 | Full regression check | `uv run pytest` passes |

## Key Findings

| # | Finding | Action |
|---|---------|--------|
| 01 | Hook point: `parse()` after file node, before `EXTRACTABLE_LANGUAGES` | Add `if language == "markdown":` branch |
| 02 | `create_section()` requires byte offsets | Compute cumulative bytes in line scan |
| 03 | `CodeNode` is frozen — `parent_node_id` at construction | Pass `parent_node_id=file_node.node_id` |
| 04 | Existing collision uses `@{line}` not `@L{line}` | Match convention exactly |

## Risk Summary

| Risk | Severity | Mitigation |
|------|----------|------------|
| Byte offset computation | Medium | Track cumulative bytes; test with known positions |
| Code block edge cases | Low | Handle ``` and ~~~; ignore indented blocks |
| Frozen dataclass | Low | Set parent_node_id at creation time |

## Flight Log

| Date | Event |
|------|-------|
| 2026-04-14 | Research dossier created (6 subagents, 1797 files analyzed) |
| 2026-04-14 | Tree-sitter experiment: 14,454 nodes/file confirmed — hand-roll decision |
| 2026-04-14 | Spec created, 7 clarifications resolved |
| 2026-04-15 | Plan created (Simple mode, 6 tasks), validated (3 agents, fixes applied) |
| 2026-04-15 | Implementation complete: 27 unit tests + 1 integration test, all GREEN |
| 2026-04-15 | Regression: 0 new failures (8 pre-existing in report service) |
