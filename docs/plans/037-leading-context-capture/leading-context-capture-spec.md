# Leading Context Capture

**Plan**: 037-leading-context-capture
**Mode**: Simple
**Created**: 2026-03-16
**Status**: Clarified

📚 This specification incorporates findings from:
- `workshops/001-leading-context-design.md` — Data model, search integration, embedding strategy
- `workshops/002-tree-sitter-comment-extraction.md` — Per-language tree-sitter behavior, fixture validation

ℹ️ No domain registry exists. Domains identified below are based on codebase architecture.

---

## Summary

Comments, docstrings, and decorators that sit **above** a function, class, or method are invisible to fs2 today. Tree-sitter excludes them from the node's byte range, so they're not in `content`, not searchable, not embedded, and not passed to the LLM for smart content generation. This feature captures that "leading context" into a new CodeNode field and makes it fully searchable — by text, regex, and semantic search — so developers can find code by what the comments say about it, not just what the code itself contains.

**WHY**: A user searching for "cross-border transactions" should find the function that has that phrase in a comment above it. A user searching semantically for "tax calculation algorithm" should get a strong match when the comment above says exactly that. Today, both searches miss.

---

## Goals

- **G1**: Capture comments and decorators above functions/classes/methods into a `leading_context` field on CodeNode
- **G2**: Make `leading_context` searchable via text, regex, and semantic search
- **G3**: Include `leading_context` in embedding input so semantic search captures comment meaning
- **G4**: Pass `leading_context` to the LLM prompt so smart content summaries incorporate developer documentation
- **G5**: Work across all supported languages (Python, Go, Rust, Java, TypeScript, JavaScript, C, C++, Ruby, Bash, GDScript, CUDA)
- **G6**: Handle language-specific edge cases (Python `decorated_definition`, TypeScript `export_statement` wrapper)
- **G7**: Use blank-line gap rule to avoid capturing unrelated comments

---

## Non-Goals

- **NG1**: Extending the node's byte range (breaks `content_hash`, `start_line`, `signature`)
- **NG2**: Capturing trailing comments below a function (ambiguous ownership)
- **NG3**: Creating a separate embedding field for leading context (prepend to content instead)
- **NG4**: Triggering smart content regeneration when only comments change (embedding re-triggers, not LLM)
- **NG5**: Parsing comment content structure (e.g., extracting `@param` values from JSDoc/Javadoc)
- **NG6**: Multi-process locking or concurrent write safety for the graph

---

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| models | existing | **modify** | Add `leading_context: str \| None` field to CodeNode |
| adapters | existing | **modify** | Extract leading context from tree-sitter AST during parsing |
| search | existing | **modify** | Search `leading_context` as 4th text/regex field |
| embedding | existing | **modify** | Prepend `leading_context` to content before chunking |
| smart_content | existing | **modify** | Include `leading_context` in LLM prompt context |
| cli | existing | **modify** | Add `leading_context` to get_node JSON output (RF-01: explicit field selection) |
| mcp | existing | **modify** | Add `leading_context` to MCP max detail output (RF-01: explicit field selection) |

No new domains created. All changes are additive to existing boundaries.
Fixture updates (GDScript, CUDA, Python, Ruby) completed pre-plan.

---

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=2, I=0, D=1, N=1, F=0, T=1 → Total P=5
- **Confidence**: 0.85
- **Assumptions**:
  - Tree-sitter `prev_named_sibling` API works consistently across all grammars (validated in workshop 002)
  - Blank-line gap heuristic is sufficient (no need for semantic comment attribution)
  - CodeNode frozen dataclass field addition is backward compatible (default None)
- **Dependencies**: None external. Tree-sitter grammars already installed.
- **Risks**: 
  - Language-specific edge cases may surface beyond the 3 identified (Python, TS, TSX wrappers)
  - Ruby tree-sitter grammar uses `method` not `method_definition` — parser may need type-set expansion
- **Phases**: 
  1. CodeNode field + AST parser extraction
  2. Search + embedding + smart content integration
  3. Tests across all languages

---

## Acceptance Criteria

1. **AC01**: CodeNode has a `leading_context: str | None` field, default None, backward compatible with existing graphs
2. **AC02**: `fs2 scan` on a Python file with `# comments` above a function populates `leading_context` with those comments
3. **AC03**: `fs2 scan` on a Python file with `@decorator` above a function populates `leading_context` with the decorator text
4. **AC04**: Comments separated from a definition by a blank line are NOT captured (blank-line gap rule)
5. **AC05**: TypeScript `export function` captures comments that are siblings of `export_statement`, not the function
6. **AC06**: Rust `#[derive(Debug)]` attributes are captured as leading context
7. **AC07**: `fs2 search "cross-border" --mode text` finds a node whose `leading_context` contains "cross-border"
8. **AC08**: Semantic search for "tax calculation" returns stronger match when `leading_context` contains relevant comments (embedding includes leading context)
9. **AC09**: Smart content generated with `leading_context` present references information from the developer's comments
10. **AC10**: `leading_context` is capped at 2000 characters to prevent license header bloat
11. **AC11**: `content_hash` does NOT change when leading context changes (code-only hash, stable)
12. **AC12**: `embedding_hash` DOES change when leading context changes (triggers re-embedding)
13. **AC13**: All fixture languages (Python, Go, Rust, Java, TS, TSX, JS, C, C++, Ruby, Bash, GDScript, CUDA) produce leading context for nodes with comments above them

---

## Risks & Assumptions

| Risk | Impact | Mitigation |
|------|--------|------------|
| Some tree-sitter grammars may not expose comment nodes as named siblings | Medium — language would have no leading context | Probe already validated 13 languages; degrade gracefully (None) |
| Blank-line gap rule may be too aggressive or too lenient | Low — heuristic, not critical for correctness | Can tune threshold later; captures 95%+ of cases correctly |
| Graph size increase from storing comment text | Low — comments are small (~50-200 bytes typical) | 2000-char cap prevents pathological cases |
| Embedding vectors change for nodes gaining leading context | Medium — existing search results shift | Expected and desirable; re-embed on next `fs2 scan --embed` |
| Python `decorated_definition` is the only parent-wrapper pattern that puts decorators as children; others may exist | Low — workshop 002 validated all 13 languages | Add wrapper types to frozenset as discovered |

**Assumptions**:
- `prev_named_sibling` is a stable tree-sitter API across all grammar versions
- Comment nodes are always named nodes (is_named=True) in all grammars
- Users want decorator text (e.g., `@dataclass`) as part of leading context, not just comments

---

## Open Questions

All resolved — see Clarifications below.

---

## Testing Strategy

- **Approach**: Hybrid — TDD for parser extraction, lightweight for search/embedding wiring
- **Rationale**: Parser extraction has language-specific edge cases (Python `decorated_definition`, TS `export_statement`, blank-line gap) that benefit from test-first. Search/embedding integration is simpler additive wiring.
- **Mock Usage**: No mocks — always parse real fixture files with real tree-sitter. Use project-standard fakes for adapter testing (per fs2 convention: fakes over mocks).
- **Focus Areas**: Multi-language comment extraction, blank-line gap rule, wrapper parent handling
- **Excluded**: Manual testing of every language × search mode combination (fixture-based tests cover this)

## Documentation Strategy

- **Location**: No new documentation files — `leading_context` is an internal field. Existing docs (configuration-guide.md) don't need updates since this is automatic behavior with no user config.
- **Rationale**: Users don't configure leading context. It "just works" during scan.

---

## Clarifications

### Session 2026-03-16

**Q1: Workflow Mode** → **Simple** — Single-phase plan, inline tasks. Well-scoped, workshops done, low risk.

**Q2: Testing Strategy** → **Hybrid** — TDD for parser extraction (language edge cases), lightweight for search/embedding wiring.

**Q3: Mock Usage** → **No mocks** — Always parse real fixture files with real tree-sitter. Use project fakes (not mocks) per fs2 convention.

**Q4 (OQ1): Search Score** → **0.6** — Leading context scores higher than raw content (0.5) since it's human-authored intent. Node_id still highest (0.8-1.0).

**Q5 (OQ2): Smart content regen on comment change** → **No** — Only re-embed when leading context changes. Smart content hash stays based on code-only `content_hash`. Avoids expensive LLM calls for comment typo fixes.

**Q6 (OQ3): get_node display** → **Separate field** — `leading_context` appears as its own key in JSON and tree output, not merged into content.

---

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| ~~Leading Context Data Model~~ | ~~Data Model~~ | ~~DONE~~ | ~~Workshop 001~~ |
| ~~Tree-Sitter Extraction~~ | ~~Integration Pattern~~ | ~~DONE~~ | ~~Workshop 002~~ |

Both workshops identified in this feature have already been completed. No further workshops needed before architecture.
