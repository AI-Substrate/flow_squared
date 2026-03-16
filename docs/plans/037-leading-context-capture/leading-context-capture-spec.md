# Leading Context Capture

**Plan**: 037-leading-context-capture
**Created**: 2026-03-16
**Status**: Draft

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
| fixtures | existing | **modify** | Updated GDScript, CUDA, Python, Ruby samples (DONE) |

No new domains created. All changes are additive to existing boundaries.

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

1. **OQ1**: Should `leading_context` score 0.5 or 0.6 in text/regex search? [NEEDS CLARIFICATION: Workshop 001 suggests 0.6 for human-authored intent, but keeping it at 0.5 (same as content) avoids surprising rank changes]
2. **OQ2**: Should smart content regeneration trigger when leading context changes? [Workshop recommends NO — only embedding re-triggers. But if a developer adds a detailed comment explaining an algorithm, the AI summary would benefit from re-generation]
3. **OQ3**: For `get_node` output, should `leading_context` be shown alongside `content` or separately? [Impacts CLI display and MCP tool responses]

---

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| ~~Leading Context Data Model~~ | ~~Data Model~~ | ~~DONE~~ | ~~Workshop 001~~ |
| ~~Tree-Sitter Extraction~~ | ~~Integration Pattern~~ | ~~DONE~~ | ~~Workshop 002~~ |

Both workshops identified in this feature have already been completed. No further workshops needed before architecture.
