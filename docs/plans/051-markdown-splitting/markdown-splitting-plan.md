# Markdown Section Splitting Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-04-15
**Spec**: [markdown-splitting-spec.md](./markdown-splitting-spec.md)
**Research**: [research-dossier.md](./research-dossier.md)
**Status**: COMPLETE

## Summary

Markdown files (`.md`, `.markdown`) are currently indexed as single `file:` nodes in the FlowSpace graph, making documentation search too coarse for plan-heavy repositories. This plan adds a hand-rolled `MarkdownSectionSplitter` (~80 lines) that creates `section:` child nodes at H2 (`##`) heading boundaries during `fs2 scan`. The splitter integrates into the existing `TreeSitterParser.parse()` method as a custom code path for markdown, bypassing tree-sitter entirely. All infrastructure — `CodeNode.create_section()`, `section` category, `ContentType.CONTENT`, storage edges, embedding pipeline — already exists.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| AST Parsing | inferred | **modify** | Add markdown splitting path to `TreeSitterParser.parse()` |
| Language Support | inferred | **modify** | New `MarkdownSectionSplitter` class |
| CodeNode Model | inferred | consume | Use existing `create_section()`, no changes |
| Scan Pipeline | inferred | consume | Existing discovery→parsing→storage flow, no changes |
| Graph Storage | inferred | consume | Existing graph store accepts section nodes, no changes |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/core/adapters/markdown_splitter.py` | Language Support | internal | New splitter class |
| `src/fs2/core/adapters/ast_parser_impl.py` | AST Parsing | internal | Add markdown hook in `parse()` |
| `tests/unit/adapters/test_markdown_splitter.py` | Language Support | internal | Unit tests for splitter |
| `tests/unit/adapters/test_ast_parser_impl.py` | AST Parsing | internal | Integration test for markdown parsing |
| `tests/fixtures/markdown/` | Language Support | internal | Test fixture `.md` files |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `parse()` calls `get_parser()` and `parser.parse()` BEFORE the `EXTRACTABLE_LANGUAGES` check. Markdown branch must hook in earlier — before tree-sitter is invoked (~`ast_parser_impl.py:515`) — to truly bypass tree-sitter | Add `if language == "markdown":` branch before `get_parser(language)` call, return file node + section nodes directly |
| 02 | High | `create_section()` requires `start_byte`, `end_byte`, and `signature`. Must compute byte offsets during line scan using UTF-8 encoding | Track cumulative byte offset via `len(line.encode('utf-8')) + 1` per line |
| 03 | High | `CodeNode` is frozen — `parent_node_id` must be set at construction. Splitter must accept `parent_node_id` parameter and pass it through to `create_section()` | Splitter signature: `split(file_path, content, parent_node_id)` |
| 04 | High | Existing collision convention uses `@{line}` not `@L{line}` (`ast_parser_impl.py:751-765`). Must match for ID stability | Use `@{line}` format for duplicate heading disambiguation |
| 05 | High | Windows paths need `as_posix()` normalization before building node IDs (`ast_parser_impl.py:536-555`) | Normalize file_path to POSIX before constructing section nodes |
| 06 | High | Sections with `content_type=CONTENT` are automatically embedded/indexed by `EmbeddingService` — no extra wiring needed | Use `create_section()` defaults (already `CONTENT`) |
| 07 | High | Existing parser tests have a skipped markdown test slot (`test_ast_parser_impl.py:392-666`) | Replace skipped test with real markdown splitter integration test |
| 08 | Medium | Existing section-node consumers include CLI tree icons (`cli/tree.py`), MCP tree icons (`mcp/server.py`), smart-content templates, and section token config | No code changes needed — but verify these consumers display markdown sections correctly in T005 |

## Implementation

**Objective**: Add markdown H2 section splitting to `fs2 scan` via a hand-rolled splitter integrated into the parse pipeline
**Testing Approach**: Full TDD — no mocks, real markdown fixtures only
**Complexity**: CS-2 (small)

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | T001 | Create test fixtures — markdown files covering: basic H2 splitting, preamble with H1 title, preamble without H1, code blocks containing `##` (with language specifier e.g. ` ```python `), tilde `~~~` code fences, consecutive H2s (empty sections), file with no H2s, file with duplicate H2 names, empty file (`empty.md`), H1-only file (`h1_only.md`), code-block-only file (`codeblock_only.md`), file with non-ASCII/UTF-8 content | Language Support | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/fixtures/markdown/` | 10+ fixture files exist, one per AC-11 edge case + UTF-8 | TDD: fixtures first |
| [x] | T002 | Write unit tests for `MarkdownSectionSplitter` — test each fixture: correct section count, correct names, correct line ranges, correct byte offsets (including UTF-8), preamble naming (H1 title and "Preamble" fallback), code-block skipping (backtick and tilde), duplicate heading disambiguation (`@{line}` format) | Language Support | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/adapters/test_markdown_splitter.py` | All tests written and initially FAILING (no implementation yet) | TDD: tests before code |
| [x] | T003 | Implement `MarkdownSectionSplitter` — line-by-line scanner that: tracks fenced code blocks (``` and ~~~ with language specifiers), splits at `## ` (not `### `), captures preamble with H1 title or "Preamble", computes UTF-8 byte offsets, uses `@{line}` for duplicate headings, normalizes paths with `as_posix()`, accepts `parent_node_id` parameter, returns `list[CodeNode]` via `create_section()` | Language Support | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/adapters/markdown_splitter.py` | All T002 tests pass | Splitter signature: `split(file_path, content, parent_node_id)` per finding 03 |
| [x] | T004 | Write failing integration test — scan a temp directory with markdown fixtures, verify graph contains correct file→section edges, verify `tree` output shows sections as children, verify `search` finds sections by content, verify section nodes are embeddable | AST Parsing | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/adapters/test_ast_parser_impl.py` | Integration test written and FAILING; replaces any skipped markdown test | TDD: test before integration code; covers AC-09, AC-10, AC-12; per finding 07 |
| [x] | T005 | Integrate into `TreeSitterParser.parse()` — add `if language == "markdown":` branch BEFORE `get_parser(language)` call (~line 515) to bypass tree-sitter entirely. Instantiate splitter with `parent_node_id=file_node.node_id`, call `split()`, return file node + section nodes | AST Parsing | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/adapters/ast_parser_impl.py` | T004 integration test passes; markdown files produce file + section nodes when parsed | Per finding 01; must hook BEFORE tree-sitter parse, not after |
| [x] | T006 | Run full test suite — verify no regressions in existing parser tests for Python, JS, TS, RST, etc. | AST Parsing | — | `uv run pytest` passes with 0 failures | Regression gate |

### Acceptance Criteria

- [ ] **AC-01**: `fs2 scan` produces `file:` + `section:` nodes for markdown files with H2 headings
- [ ] **AC-02**: Section node IDs: `section:{path}:{heading}`, duplicates use `@{line}` suffix
- [ ] **AC-03**: Section content spans from H2 line to next H2 (includes H3/H4 subsections)
- [ ] **AC-04**: Preamble captured as section with H1 title or "Preamble" fallback
- [ ] **AC-05**: Headings inside fenced code blocks (``` and ~~~) are skipped
- [ ] **AC-06**: Section nodes: `content_type=CONTENT`, `language="markdown"`, `category="section"`, valid `parent_node_id`
- [ ] **AC-07**: Accurate `start_line`, `end_line`, `start_byte`, `end_byte`
- [ ] **AC-08**: Files with zero H2s produce only the `file:` node
- [ ] **AC-09**: `fs2 tree` shows sections as children of file nodes
- [ ] **AC-10**: `fs2 search` finds sections by heading text or content
- [ ] **AC-11**: Edge cases handled without crashing (empty files, code-block-only files, consecutive H2s)
- [ ] **AC-12**: Embedding generation works for section nodes

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Byte offset computation error (especially UTF-8/CRLF) | Medium | Medium | Track cumulative bytes via `len(line.encode('utf-8')) + 1`; test with UTF-8 fixture |
| Fenced code block edge cases (nested, indented, language specifiers) | Low | Low | Handle ``` and ~~~ with optional language suffix; ignore indented code blocks; add fixtures |
| Frozen dataclass prevents post-construction edits | Low | High | Pass `parent_node_id` into splitter at construction time |
| Windows path format in node IDs | Low | Medium | Use `as_posix()` normalization per existing parser convention |
| Hook point before tree-sitter parse | Low | Medium | Branch early in `parse()` before `get_parser()` call; return file+section nodes directly |

---

## Validation Record (2026-04-15)

| Agent | Lenses Covered | Issues | Verdict |
|-------|---------------|--------|---------|
| Coherence (GPT-5.4) | System Behavior, Integration & Ripple, Hidden Assumptions, Domain Boundaries | 1 CRITICAL + 2 HIGH + 2 MEDIUM + 1 LOW — all fixed | ✅ |
| Risk & Completeness (GPT-5.4) | Edge Cases & Failures, Performance & Scale, Concept Documentation | 1 HIGH + 2 MEDIUM — all fixed | ✅ |
| Source Truth (GPT-5.4) | Technical Constraints, User Experience, Hidden Assumptions | 2 HIGH + 1 LOW — all fixed | ✅ |

**Fixes applied**:
- Hook point corrected: branch before `get_parser()`, not after file node
- Task order fixed: T004=write failing integration test, T005=implement integration (TDD)
- Splitter signature fixed: accepts `parent_node_id` at construction, no post-hoc mutation
- T001 fixtures expanded: added `empty.md`, `h1_only.md`, `codeblock_only.md`, UTF-8 fixture
- T004 now covers AC-12 (embedding verification)
- Domain manifest: added `test_ast_parser_impl.py`
- Finding 08 added: existing section-node consumers documented

Overall: ⚠️ VALIDATED WITH FIXES

---

## Fixes

| ID | Created | Summary | Domain(s) | Status | Source |
|----|---------|---------|-----------|--------|--------|
| FX001 | 2026-04-15 | Add E2E regression tests for tree/search/embedding with markdown section nodes | AST Parsing | **Done** | Code review F001 |
| FX002 | 2026-04-15 | Skip smart content generation for markdown section nodes (human-readable prose) | Scan Pipeline | **Done** | Workshop 001 |
