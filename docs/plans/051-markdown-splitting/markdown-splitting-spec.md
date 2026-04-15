# Markdown Section Splitting

**Mode**: Simple

📚 *This specification incorporates findings from `research-dossier.md` — including empirical analysis of 1,797 markdown files (580K lines) and a confirmed tree-sitter experiment.*

## Research Context

Based on the research dossier (`docs/plans/051-markdown-splitting/research-dossier.md`):

- **Empirical analysis**: H2 (`##`) splitting produces median 18-line chunks; 92.1% of chunks land in the 5–200 line sweet spot. H1 is too coarse (~1 chunk/file). H3 is too granular (many tiny leaf sections).
- **Architecture fit**: fs2 already has `CodeNode.create_section()`, the `"section"` category in `classify_node()`, and `ContentType.CONTENT`. Markdown is detected as `"markdown"` by `detect_language()`. The only gap is that `"markdown"` is not in `EXTRACTABLE_LANGUAGES`.
- **Tree-sitter rejected**: Experimentally confirmed that tree-sitter produces 14,454 nodes for a single 1,828-line plan file (7.9 nodes/line, 99.5% noise). A hand-rolled splitter (~80 lines) is simpler, faster, and zero new dependencies.
- **Existing patterns**: `rst` is already in `EXTRACTABLE_LANGUAGES` for section/heading extraction; markdown follows the same concept.

## Summary

**WHAT**: When FlowSpace scans a codebase, markdown files (`.md`, `.markdown`) should be split into `section:` nodes at `##` (H2) heading boundaries — just like code files are split into `callable:` and `type:` nodes by function/class. Each H2 section becomes a separately searchable, embeddable graph node.

**WHY**: In plan-heavy repositories (1,797+ markdown files, 580K lines), file-level resolution is too coarse for effective search. When a user searches for "testing philosophy" or "DI container pattern", they should find the specific H2 section — not an entire 1,800-line plan file. Sub-file markdown resolution makes FlowSpace documentation search genuinely useful for plan repositories, research dossiers, specs, and READMEs.

## Goals

1. **Sub-file markdown search** — Users can search for and find specific sections within markdown files, not just whole files. A search for "Phase 3" should return the Phase 3 section, not the entire plan document.

2. **Automatic splitting at scan time** — No user configuration required. When `fs2 scan` encounters a `.md` file, it automatically creates `section:` child nodes for each H2 heading, in addition to the existing `file:` node.

3. **Preamble preservation** — Content before the first H2 heading (title, metadata, summary) is captured as a section so it's not lost from search.

4. **Code-block awareness** — Headings inside fenced code blocks (`` ``` ``) are not treated as section boundaries. `## This is a comment in code` inside a Python code block must be ignored.

5. **Consistent node model** — Section nodes use the existing `CodeNode.create_section()` factory and `section:` node ID prefix, fitting seamlessly into the graph, search, and embedding pipelines.

6. **Hand-rolled splitter** — Implementation uses a simple line-by-line Python scanner (~80 lines), not tree-sitter. Zero new dependencies. Predictable, testable, maintainable.

## Non-Goals

1. **Configurable heading depth** — Splitting at H1 or H3 is not in scope. H2 is the default and only level. Configurability may come later.

2. **Nested section hierarchy** — H3/H4 subsections are NOT separate nodes. They are included in the content of their parent H2 section. There is no `section:` → `section:` parent-child nesting.

3. **Inline formatting parsing** — No extraction of bold, italic, links, tables, or other inline markdown elements. The splitter works at the heading level only.

4. **Setext heading support** — Only ATX-style headings (`## Heading`) are recognized as split points. Setext-style headings (underlined with `---` or `===`) are treated as regular content. This matches the near-universal convention in plan/spec files.

5. **Tree-sitter integration** — The splitter deliberately bypasses tree-sitter. Markdown is not added to tree-sitter's extraction path.

6. **Non-markdown content splitting** — This feature only applies to `.md`/`.markdown` files. Other content files (`.txt`, `.rst`, `.adoc`) are not affected.

7. **Smart content generation for sections** — Section nodes get their raw content only. Smart content summarization for markdown sections is out of scope.

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| AST Parsing | inferred | **modify** | Add markdown splitting path to `TreeSitterParser.parse()` |
| CodeNode Model | inferred | **consume** | Use existing `create_section()`, `section` category (no changes) |
| Scan Pipeline | inferred | **consume** | Existing discovery→parsing→storage flow handles new nodes (no changes) |
| Language Support | inferred | **modify** | New `MarkdownSectionSplitter` adapter alongside `LanguageHandler` pattern |
| Graph Storage | inferred | **consume** | Existing graph store accepts section nodes with parent edges (no changes) |

*No formal domain registry exists. Domains inferred from codebase structure per PL-04.*

## Complexity

**Score**: CS-2 (small)

**Breakdown**:

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | New splitter class + integration in parser; touches 2-3 files |
| Integration (I) | 0 | No external dependencies; stdlib only |
| Data/State (D) | 0 | No schema changes; uses existing CodeNode and graph model |
| Novelty (N) | 0 | Well-specified from research; clear implementation path |
| Non-Functional (F) | 0 | Standard performance; no security/compliance concerns |
| Testing/Rollout (T) | 1 | Unit + integration tests; verify graph/search/embedding behavior |

**Total**: S(1) + I(0) + D(0) + N(0) + F(0) + T(1) = **2** → **CS-1** (borderline CS-2)

**Confidence**: 0.95

**Assumptions**:
- Existing `CodeNode.create_section()` works for markdown sections without modification
- Storage and embedding pipelines handle new section nodes without changes
- H2 is universally the right split level for our documentation style

**Dependencies**: None — all infrastructure exists

**Risks**:
- Duplicate heading names (e.g., "## Overview" in multiple files) — node IDs include file path so this is safe
- Very large H2 sections (>800 tokens) — embedding chunking already handles oversized content
- Edge cases in fenced code block detection (nested, indented, or tildes `~~~`)

**Phases**:
1. Implement `MarkdownSectionSplitter` with tests
2. Integrate into `TreeSitterParser.parse()` pipeline
3. End-to-end verification (scan → search → embedding)

## Acceptance Criteria

**AC-01**: When `fs2 scan` processes a markdown file with H2 headings, the graph contains one `file:` node plus one `section:` node per H2 heading.

**AC-02**: Section node IDs follow the format `section:{file_path}:{heading_text}`. When duplicate heading text exists in the same file, subsequent occurrences append `@{line_number}` (matching the existing parser collision convention). First occurrence keeps the clean name.

**AC-03**: Each section node's `content` field contains the full text from the H2 heading line through to (but not including) the next H2 heading or end of file. H3/H4 subsections are included in the parent H2 section's content.

**AC-04**: Content before the first H2 heading (preamble) is captured as a section node. Its name is the H1 title text if present; otherwise "Preamble".

**AC-05**: Headings inside fenced code blocks (`` ``` `` or `~~~`) are NOT treated as section boundaries. The splitter correctly skips code blocks.

**AC-06**: Section nodes have `content_type=CONTENT`, `language="markdown"`, `category="section"`, and a valid `parent_node_id` pointing to the file node.

**AC-07**: Section nodes include accurate `start_line`, `end_line`, `start_byte`, and `end_byte` fields that match the actual position in the source file.

**AC-08**: A markdown file with zero H2 headings produces only the existing `file:` node — no section nodes are created.

**AC-09**: The `tree` command (`fs2 tree`) displays section nodes as children of their file node, showing heading text as the name.

**AC-10**: The `search` command (`fs2 search`) can find section nodes by heading text or section content, returning the section (not the whole file).

**AC-11**: The splitter handles edge cases without crashing: empty files, files with only H1 headings, files with only code blocks, files with H2 headings inside code blocks, and files with consecutive H2 headings (no content between them).

**AC-12**: Embedding generation works for section nodes — each section is embeddable as a separate chunk, using the existing `ContentType.CONTENT` (800 token) chunking strategy.

## Risks & Assumptions

### Risks

1. **Fenced code block edge cases** — Indented code blocks, tildes (`~~~`), and nested code blocks (e.g., markdown-in-markdown examples) could fool a simple toggle. Mitigation: handle both `` ``` `` and `~~~` fences; ignore indented code blocks (they rarely contain headings).

2. **Very long H2 sections** — Some sections (e.g., "Implementation Phases") may span 300+ lines. These are still valid chunks — the embedding pipeline already handles oversized content via chunking. No mitigation needed.

3. **Heading deduplication** — Multiple H2s could have the same text in one file (e.g., repeated "## Tasks" across phases). **Resolved**: append `@L{line}` to duplicate node IDs; first occurrence keeps the clean name.

### Assumptions

1. All project markdown uses ATX-style headings (`## Heading`), not setext style.
2. H2 is the universal logical section boundary across plan/spec/research files.
3. Existing graph storage, search, and embedding pipelines require no changes to accommodate section nodes.
4. The `create_section()` factory and `section:` node ID prefix are the correct integration points.

## Open Questions

*All resolved — see [Clarifications](#clarifications).*

## Testing Strategy

**Approach**: Full TDD
**Mock Usage**: No mocks — real markdown fixtures only
**Rationale**: The splitter is pure-function logic (string in → CodeNode list out) — ideal for test-first development. Integration tests use real `.md` fixture files.
**Focus Areas**:
- Unit tests for splitter: basic splitting, preamble, code blocks, edge cases
- Integration tests: scan → graph → search with real markdown fixtures
**Excluded**: No mocking of any kind. All tests use real data.

## Documentation Strategy

**Location**: No new documentation — changes are internal to the scan pipeline. Existing `fs2 scan` / `fs2 tree` / `fs2 search` commands gain markdown section support automatically.

## Clarifications

### Session 2026-04-14

**Q1: Workflow Mode** → **Simple** — CS-2 feature, single-phase plan, inline tasks, skip plan-4/plan-5 gates.

**Q2: Testing Strategy** → **Full TDD** — splitter is pure logic with clear inputs/outputs, ideal for test-first.

**Q3: Mock Usage** → **No mocks** — use real markdown fixtures only. Fakes-over-mocks per project convention.

**Q4: Preamble Naming** → **Use H1 title if present, fall back to "Preamble"**. The preamble section (content before first H2) uses the first H1 heading text as its name. If no H1 exists, the section is named "Preamble".

**Q5: Duplicate Heading Disambiguation** → **Append line number** — e.g., `section:path/to/file.md:Tasks@120`. Uses the existing parser collision convention (`@{line}`, not `@L{line}`). Only applied when a duplicate heading text is detected within the same file. First occurrence keeps the clean name.

**Q6: Minimum Section Size** → **No minimum** — all sections are included regardless of line count. Even 1-2 line sections are valid search targets.

**Q7: Domain Review** → **Confirmed** — AST Parsing and Language Support are the two modify domains; CodeNode Model, Scan Pipeline, and Graph Storage are consumed without changes.

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| Fenced code block edge cases | Integration Pattern | Multiple fence styles (```` ``` ````, `~~~`, indented), nesting, and language-specific quirks need careful handling | How many fence styles to support? Handle nesting? What about HTML `<pre>` blocks? |
