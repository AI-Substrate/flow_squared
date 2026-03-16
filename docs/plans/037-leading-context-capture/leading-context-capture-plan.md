# Leading Context Capture — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-03-16
**Spec**: [leading-context-capture-spec.md](leading-context-capture-spec.md)
**Status**: COMPLETE

## Summary

Comments, decorators, and doc-comments above functions/classes are invisible to fs2 — tree-sitter excludes them from the node's byte range. This plan adds a `leading_context: str | None` field to CodeNode, populates it during parsing by walking `prev_named_sibling`, makes it searchable (text score 0.6), prepends it to embedding input, and passes it to the LLM for richer smart content. Single-phase Simple mode plan.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| models | existing | modify | Add `leading_context` field to CodeNode + 5 factory methods |
| adapters | existing | modify | Extract leading context from tree-sitter AST during parsing |
| search | existing | modify | Search `leading_context` as 4th text/regex field (score 0.6) |
| embedding | existing | modify | Prepend `leading_context` to content before chunking |
| smart_content | existing | modify | Include `leading_context` in LLM prompt context + 6 templates |
| cli | existing | modify | Add `leading_context` to get_node JSON output |
| mcp | existing | modify | Add `leading_context` to max detail output |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/core/models/code_node.py` | models | contract | Add field to public dataclass |
| `src/fs2/core/adapters/ast_parser_impl.py` | adapters | internal | New `_extract_leading_context()` + wire into `_create_node()` |
| `src/fs2/core/services/search/regex_matcher.py` | search | internal | Add 4th field search block |
| `src/fs2/core/services/embedding/embedding_service.py` | embedding | internal | Prepend leading_context in `_chunk_content()` |
| `src/fs2/core/services/smart_content/smart_content_service.py` | smart_content | internal | Add to `_build_context()` dict |
| `src/fs2/core/templates/smart_content/*.j2` | smart_content | internal | 6 templates: add `{% if leading_context %}` block |
| `src/fs2/cli/get_node.py` | cli | internal | Add to `_code_node_to_cli_dict()` explicit field list |
| `src/fs2/mcp/server.py` | mcp | internal | Add to `_code_node_to_dict()` max detail |
| `tests/unit/adapters/test_leading_context.py` | tests | internal | TDD tests for parser extraction |
| `tests/unit/services/search/test_leading_context_search.py` | tests | internal | Tests for search integration |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| RF-01 | Critical | `get_node.py` and `mcp/server.py` use **explicit field selection** — `leading_context` will NOT appear in output unless manually added to the dict (lines 48-61 in get_node.py, line 548 in server.py) | T08, T09: explicitly add field to both output dicts |
| RF-02 | Critical | `content_hash` is computed in 5 factory methods as `compute_content_hash(content)` — must NOT change. `leading_context` is metadata, not content | T01: add field with default None, verify hash untouched |
| RF-03 | High | `embedding_hash` is currently `node.content_hash` (line 759 of embedding_service.py). Per spec AC12, it should change when leading_context changes — but using `content_hash` as-is means comment edits don't trigger re-embedding | T06: compute `embedding_hash` from `content + (leading_context or "")` |
| RF-04 | High | Python `decorated_definition` wraps function + decorators as children, not siblings. Must walk from parent's siblings for comments. TypeScript `export_statement` has same issue. Validated in Workshop 002 | T03: handle WRAPPER_PARENT_TYPES in extraction |
| RF-05 | Medium | `text_matcher.py` delegates to `regex_matcher.py` — only need to modify regex_matcher | T07: only modify regex_matcher.py |
| RF-06 | Medium | `_create_node()` at line 820 of ast_parser_impl.py is the central dispatcher for 4 factory methods (type, callable, section, block). Single integration point | T03: call `_extract_leading_context()` before `_create_node()` |
| RF-07 | Low | Old graphs load fine — CodeNode field defaults to None. RestrictedUnpickler doesn't need changes. No migration needed | No action — backward compatible by design |
| RF-08 | Low | 6 Jinja2 template files exist for smart content prompts. All need a conditional `leading_context` block | T05: update all 6 templates |

## Implementation

**Objective**: Add `leading_context` to CodeNode, populate during parsing, make searchable via text/regex/semantic, enrich smart content prompts
**Testing Approach**: Hybrid — TDD for parser extraction (language edge cases), lightweight for search/embedding wiring

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | T01 | Add `leading_context: str \| None = None` field to CodeNode + add to 5 factory methods as optional param | models | `src/fs2/core/models/code_node.py` | Field exists, factories accept it, `content_hash` unchanged | RF-02: hash stability critical |
| [x] | T02 | Define extraction constants: `COMMENT_NODE_TYPES`, `SIBLING_DECORATOR_TYPES`, `WRAPPER_PARENT_TYPES`, `MAX_LEADING_CONTEXT_CHARS=2000` | adapters | `src/fs2/core/adapters/ast_parser_impl.py` | Constants defined, types from Workshop 002 table | AC10: 2000 char cap |
| [x] | T03 | Implement `_extract_leading_context(ts_node, source_bytes)` — walk `prev_named_sibling`, collect comments/decorators, handle wrapper parents, blank-line gap rule | adapters | `src/fs2/core/adapters/ast_parser_impl.py` | Returns `str \| None`, handles Python `decorated_definition` + TS `export_statement`, stops at blank line | RF-04, RF-06, AC02-06 |
| [x] | T04 | Wire `_extract_leading_context()` into parsing: call before `_create_node()`, pass result to factory methods; also wire for file nodes in `parse()` | adapters | `src/fs2/core/adapters/ast_parser_impl.py` | All created CodeNodes have `leading_context` populated from tree-sitter siblings | RF-06 |
| [x] | T05 | Add `leading_context` to smart content: update `_build_context()` dict + add conditional block to 6 templates (base, callable, file, block, type, section) | smart_content | `src/fs2/core/services/smart_content/smart_content_service.py`, `src/fs2/core/templates/smart_content/smart_content_{base,callable,file,block,type,section}.j2` | LLM prompt includes developer comments when present | RF-08, AC09 |
| [x] | T06 | Prepend `leading_context` to content before chunking in embedding service; compute `embedding_hash` from content + leading_context | embedding | `src/fs2/core/services/embedding/embedding_service.py` | Embedding vector includes comment semantics; hash changes when comments change | RF-03, AC08, AC12 |
| [x] | T07 | Add `leading_context` search to regex_matcher: 4th field with score 0.6 | search | `src/fs2/core/services/search/regex_matcher.py` | Text/regex search matches in leading_context with score 0.6 | RF-05, AC07 |
| [x] | T08 | Add `leading_context` to get_node CLI output: update `_code_node_to_cli_dict()` | cli | `src/fs2/cli/get_node.py` | `fs2 get-node` JSON output includes `leading_context` field | RF-01 |
| [x] | T09 | Add `leading_context` to MCP max detail output: update `_code_node_to_dict()` + docstring | mcp | `src/fs2/mcp/server.py` | MCP `get_node` with detail=max includes `leading_context` | RF-01 |
| [x] | T10 | TDD tests for parser extraction: Python comments, Python decorators, TS export wrapper, Rust attributes, blank-line gap, Go comments, Java Javadoc, C Doxygen, 2000-char cap | tests | `tests/unit/adapters/test_leading_context.py` | Tests parse real fixture files, verify leading_context populated correctly for each language pattern | AC02-06, AC10, AC13 |
| [x] | T11 | Tests for search + embedding + output integration | tests | `tests/unit/services/search/test_leading_context_search.py` | Text search finds nodes by leading_context; get_node includes field; content_hash stable, embedding_hash changes | AC07, AC11, AC12 |

### Acceptance Criteria

- [x] AC01: CodeNode has `leading_context: str | None` field, default None, backward compatible
- [x] AC02: Python `# comments` above function → `leading_context` populated
- [x] AC03: Python `@decorator` above function → `leading_context` includes decorator text
- [x] AC04: Blank line gap → comments NOT captured
- [x] AC05: TypeScript `export function` → captures comments from export_statement sibling
- [x] AC06: Rust `#[derive(Debug)]` → captured as leading context
- [x] AC07: Text search matches in `leading_context` (score 0.6)
- [x] AC08: Semantic search includes leading_context in embedding
- [x] AC09: Smart content references developer comments when present
- [x] AC10: `leading_context` capped at 2000 characters
- [x] AC11: `content_hash` unchanged by leading_context
- [x] AC12: `embedding_hash` changes when leading_context changes
- [x] AC13: All fixture languages produce leading_context

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Language-specific wrapper parents beyond Python/TS/TSX | Low | Medium | Workshop 002 validated all 13 languages; WRAPPER_PARENT_TYPES frozenset is extensible |
| `prev_named_sibling` walk could be O(N²) if unbounded | Low | Medium | Stop at first non-comment/decorator; blank-line gap rule limits walk depth |
| Old graphs have `leading_context=None` — no migration | N/A | N/A | By design: field defaults to None, old graphs work unchanged |
| Embedding vectors shift for nodes gaining leading_context | Expected | Low | Desirable behavior — next `fs2 scan --embed` re-embeds |

## Progress

- Tasks: 11/11 complete
- ACs verified: 13/13
- Tests: 1784 passed (+33 from baseline 1751), 25 skipped, 0 failed (8 pre-existing report_service failures excluded)
- Commits: `3e83eb3` feat(037), `1f29d26` fix(037) review fixes
- Review: REQUEST_CHANGES → 5 fix tasks applied (FT-001 through FT-005)
  - FT-001 HIGH: embedding_hash payload matched to chunking payload (`"\n".join([lc, content])`)
  - FT-002 HIGH: Added 5 missing language tests (TSX, JS, C++, Ruby, Bash) — 33 total
  - FT-003 MEDIUM: Added AC08 chunk prepend + AC09 build_context evidence tests
  - FT-004 MEDIUM: Path drift noted (actual `test_leading_context_integration.py` vs plan's `test_leading_context_search.py`)
  - FT-005 MEDIUM: Fixed ruff violations (unused imports, sort order)

### Domain Changes

| Domain | Files Changed | Contract Change? |
|--------|--------------|-----------------|
| models | `code_node.py` | YES — new `leading_context` field (backward compatible default None) |
| adapters | `ast_parser_impl.py` | No — internal implementation |
| search | `regex_matcher.py` | No — additive field search |
| embedding | `embedding_service.py` | No — internal chunking + hash |
| smart_content | `smart_content_service.py`, 6 `.j2` templates | No — additive prompt context |
| cli | `get_node.py` | No — additive output field |
| mcp | `server.py` | No — additive max-detail field |
