# Workshop: Leading Context Capture & Search

**Type**: Data Model + Integration Pattern
**Plan**: 037-leading-context-capture
**Created**: 2026-03-16
**Status**: Draft

**Related Documents**:
- `src/fs2/core/models/code_node.py` — CodeNode dataclass
- `src/fs2/core/adapters/ast_parser_impl.py` — Tree-sitter traversal
- `src/fs2/core/services/search/regex_matcher.py` — Text search
- `src/fs2/core/services/search/semantic_matcher.py` — Embedding search
- `src/fs2/core/services/embedding/embedding_service.py` — Chunk & embed

---

## Purpose

Capture code comments and decorators that sit *above* a function, class, or method — content that tree-sitter excludes from the node's byte range but that humans consider part of the node's documentation. Make this captured text searchable via both text and semantic search.

## Key Questions Addressed

- Q1: What content is currently lost? (comments above functions, decorators, file-level docstrings as annotations)
- Q2: Should we extend the node's byte range, or store leading context as a separate field?
- Q3: How do we make leading context searchable in text and semantic search?
- Q4: What's the impact on embeddings — separate embedding or concatenated?
- Q5: How do different languages handle this? (Python `#`, `"""`, `@decorator`; JS `//`, `/** */`, TypeScript decorators)

---

## The Problem

### What Tree-Sitter Gives Us

```python
# This is an important algorithm for calculating tax rates.
# It handles edge cases for cross-border transactions.
@dataclass
@validate_input
def calculate_tax(amount: float, region: str) -> float:
    """Calculate tax based on region rules."""
    return amount * get_rate(region)
```

Tree-sitter's `function_definition` node starts at `def` (byte 106), NOT at the comment (byte 0):

```
module [0:0 - 6:0]
  ├─ comment [0:0 - 0:55]    "# This is an important algorithm..."
  ├─ comment [1:0 - 1:53]    "# It handles edge cases..."
  ├─ decorated_definition [2:0 - 5:37]
  │   ├─ decorator [2:0 - 2:10]    "@dataclass"
  │   ├─ decorator [3:0 - 3:15]    "@validate_input"
  │   └─ function_definition [4:0 - 5:37]
  │       ├─ name: "calculate_tax"
  │       ├─ parameters: (amount, region)
  │       └─ block: ...
```

**What `node.content` captures**: `def calculate_tax(amount: float, region: str) -> float:\n    ...`
**What's lost**: The two comment lines AND the two decorators.

**Python docstrings** (inside the function body) ARE included because they're within the byte range. But `#` comments above and `@decorators` above are NOT.

### Why This Matters

1. **Search miss**: Searching for "cross-border transactions" finds nothing — it's in a comment above `calculate_tax`, not in `node.content`
2. **Embedding gap**: The semantic meaning of "tax rate calculation" is in the comments, not captured in the embedding
3. **Smart content blind spot**: LLM generating summaries doesn't see the developer's own explanation
4. **Context loss**: Decorators like `@deprecated`, `@abstractmethod`, `@dataclass` carry critical semantic information

---

## Current State Inventory

### CodeNode Fields Today

| Field | Searched (text)? | Embedded? | Contains comments? |
|-------|-----------------|-----------|-------------------|
| `content` | ✅ (score 0.5) | ✅ `embedding` | ❌ Only inside body (docstrings) |
| `smart_content` | ✅ (score 0.5) | ✅ `smart_content_embedding` | ❌ AI-generated, doesn't see leading comments |
| `signature` | ❌ | ❌ | ❌ First line only |
| `node_id` | ✅ (score 0.8-1.0) | ❌ | ❌ |
| `name` | ❌ (only via node_id) | ❌ | ❌ |

**Gap**: No field captures text above the node's byte range.

### Tree-Sitter APIs Available

```python
node.previous_sibling        # Previous sibling (includes anonymous)
node.prev_named_sibling      # Previous named sibling (skips punctuation)
node.parent                  # Parent node
node.start_byte / end_byte   # Byte range of THIS node only
```

These APIs exist but are **not used** in `ast_parser_impl.py`.

---

## Design Options

### Option A: New `leading_context` Field on CodeNode

Add a dedicated field that captures comments + decorators above the node.

```python
@dataclass(frozen=True)
class CodeNode:
    # ... existing fields ...
    
    # Leading context: comments and decorators above this node
    # Captured by walking previous siblings in tree-sitter AST.
    # None for file nodes and nodes without leading context.
    leading_context: str | None = None
```

**Capture logic** (in ast_parser_impl.py):

```python
def _extract_leading_context(self, node) -> str | None:
    """Walk backwards from node to capture comments and decorators."""
    parts = []
    current = node.prev_named_sibling
    
    while current is not None:
        if current.type == "comment":
            parts.append(source[current.start_byte:current.end_byte])
            current = current.prev_named_sibling
        elif current.type == "decorator":
            parts.append(source[current.start_byte:current.end_byte])
            current = current.prev_named_sibling
        else:
            break  # Stop at first non-comment, non-decorator
    
    if not parts:
        return None
    
    parts.reverse()  # Restore top-to-bottom order
    return "\n".join(parts)
```

**Search integration**:

```python
# In regex_matcher.py — add as 4th field to search
if node.leading_context:
    lc_match = self._search_with_timeout(compiled, node.leading_context)
    if lc_match:
        score = 0.5  # Same as content
        if best is None or score > best.score:
            best = FieldMatch("leading_context", lc_match, score)
```

**Embedding integration** — Three sub-options:

| Sub-option | Approach | Pros | Cons |
|-----------|----------|------|------|
| A1: Concatenate | Prepend `leading_context` to `content` before chunking | Simple, no new embedding field | Changes embedding values for all nodes with comments |
| A2: Separate embedding | New `leading_context_embedding` field | Clean separation, independent search | 3rd embedding field, more storage, more compute |
| A3: Include in smart_content prompt | Pass leading_context to LLM alongside content | Zero embedding overhead, LLM incorporates meaning | Depends on smart_content being enabled |

**Recommended: A1 + A3 combined** — Prepend to content for embedding, AND pass to LLM for richer summaries.

### Option B: Extend Node Byte Range

Instead of a new field, expand `start_byte` to include leading comments/decorators.

```python
def _adjust_byte_range(self, node, source):
    """Extend start_byte backwards to include leading comments."""
    adjusted_start = node.start_byte
    current = node.prev_named_sibling
    
    while current and current.type in ("comment", "decorator"):
        adjusted_start = current.start_byte
        current = current.prev_named_sibling
    
    return adjusted_start, node.end_byte
```

| Pros | Cons |
|------|------|
| Zero schema changes | Breaks `content_hash` — same code with different comments = different hash |
| Content naturally searched/embedded | `start_line` no longer matches `def` keyword — confuses tree/get_node |
| Simple implementation | Hard to distinguish "the code" from "the comments" |
| | File-level comments get absorbed into first function |
| | `signature` might include comments (ugly) |

**Verdict**: ❌ Too many side effects. The byte range should match tree-sitter's definition.

### Option C: Virtual Composite Content

Don't add a field — build a `searchable_text` property that concatenates fields at search/embed time.

```python
@property
def searchable_text(self) -> str:
    """Full searchable text including leading context."""
    parts = []
    if self.leading_context:
        parts.append(self.leading_context)
    parts.append(self.content)
    return "\n".join(parts)
```

| Pros | Cons |
|------|------|
| No schema migration | Requires `leading_context` field anyway (same as Option A) |
| Clean separation of concerns | Property on frozen dataclass = computed every time |
| Embedding uses composite | Doesn't save complexity vs Option A |

**Verdict**: Useful as an accessor ON TOP of Option A, not as a replacement.

---

## Recommended Design: Option A (New Field) + A1/A3 Embedding

### Schema Change

```python
# code_node.py — add after smart_content_hash
leading_context: str | None = None
```

**Why a separate field** (not extending content):
1. `content_hash` stays stable — same function code = same hash regardless of comment changes
2. `content` stays clean for tree/get_node display
3. Leading context can be independently searched and scored
4. LLM gets explicit "here are the developer's own comments" vs "here is the code"
5. Comment-only changes can trigger re-embedding without regenerating smart_content

### Capture Strategy by Language

| Language | Comment Types | Decorator Types |
|----------|--------------|-----------------|
| Python | `# comment`, `"""docstring"""` (above) | `@decorator` |
| JavaScript/TypeScript | `// comment`, `/* block */`, `/** JSDoc */` | `@decorator` (TS) |
| Rust | `// comment`, `/// doc comment`, `//! inner doc` | `#[attribute]` |
| Go | `// comment`, `/* block */` | — |
| Java | `// comment`, `/* block */`, `/** Javadoc */` | `@Annotation` |
| YAML/JSON/Markdown | `# comment` | — |

**Tree-sitter node types to capture** (language-agnostic):

```python
LEADING_CONTEXT_TYPES = {
    # Comments (most languages)
    "comment",
    "line_comment",
    "block_comment",
    "doc_comment",
    
    # Decorators / Attributes
    "decorator",           # Python, TypeScript
    "attribute_item",      # Rust #[...]
    "annotation",          # Java @Annotation
    "attribute",           # C# [Attribute]
}
```

### Capture Algorithm

```
┌─────────────────────────────────────────────────────────────┐
│ For each non-file node being created:                        │
│                                                              │
│ 1. Get tree-sitter node for this CodeNode                    │
│ 2. Walk prev_named_sibling chain                             │
│ 3. Collect comments + decorators (stop at code/blank line)   │
│ 4. Reverse to top-to-bottom order                            │
│ 5. Join with newlines → leading_context                      │
│                                                              │
│ Special cases:                                               │
│ - `decorated_definition` parent: decorators are CHILDREN,    │
│   not siblings. Must check parent type.                      │
│ - File-level module docstrings: captured as file node's      │
│   leading_context (walk first children, not siblings)        │
│ - Consecutive blank lines: stop walking (comment is for      │
│   something else, not this node)                             │
└─────────────────────────────────────────────────────────────┘
```

### Blank Line Gap Rule

```python
# These comments belong to calculate_tax:
# Important tax calculation
# Handles edge cases
def calculate_tax(): ...

# But this comment does NOT belong to helper():
# Important tax calculation

# ← blank line = gap
def helper(): ...
```

**Implementation**: Check byte range between comment.end_byte and next node's start_byte. If it contains `\n\n` (double newline), stop walking.

### Search Integration

**Text/Regex Search** — Add as 4th searched field:

```python
# regex_matcher.py — after smart_content search
if node.leading_context:
    lc_match = self._search_with_timeout(compiled, node.leading_context)
    if lc_match:
        score = 0.6  # Slightly higher than content — developer-authored context
        if best is None or score > best.score:
            best = FieldMatch("leading_context", lc_match, score)
```

**Why score 0.6?** Leading context is human-authored intent (comments, docs). It's more likely to contain what the user is searching for than raw code (0.5) but less precise than node_id (0.8-1.0).

### Embedding Integration

**Approach: Prepend to content for chunking**

```python
# embedding_service.py — in _chunk_content or caller
def _get_embeddable_text(self, node: CodeNode, is_smart_content: bool) -> str:
    if is_smart_content:
        return node.smart_content or ""
    
    parts = []
    if node.leading_context:
        parts.append(node.leading_context)
    parts.append(node.content)
    return "\n".join(parts)
```

This means the embedding vector captures the FULL semantic meaning including comments. No new embedding field needed — the existing `embedding` field covers it.

**Smart content prompt enrichment**:

```python
# smart_content_service.py — in _build_context
def _build_context(self, node: CodeNode, content: str) -> dict:
    context = {
        "name": node.name or "anonymous",
        "content": content,
        # ... existing fields ...
    }
    if node.leading_context:
        context["leading_context"] = node.leading_context
    return context
```

Template update: `{% if leading_context %}Developer comments:\n{{ leading_context }}\n\n{% endif %}Code:\n{{ content }}`

---

## Impact Assessment

### What Changes

| Component | Change | Risk |
|-----------|--------|------|
| `CodeNode` | +1 field (`leading_context: str \| None = None`) | LOW — default None, backward compatible |
| `ast_parser_impl.py` | Add `_extract_leading_context()`, call during node creation | MEDIUM — language-specific edge cases |
| `regex_matcher.py` | Search `leading_context` field (score 0.6) | LOW — additive, no existing behavior changes |
| `semantic_matcher.py` | No change (embedding already covers it via prepend) | NONE |
| `embedding_service.py` | Prepend `leading_context` to content before chunking | LOW — changes embedding values (expected) |
| `smart_content_service.py` | Pass `leading_context` to LLM prompt template | LOW — enriches AI summaries |
| `content_hash` | **Unchanged** — hash of `content` only, NOT leading_context | NONE — intentional |
| Graph size | ~5-15% increase (comments are small) | LOW |

### What Stays The Same

- `content` field — still tree-sitter's exact byte range
- `content_hash` — still based on code content only (comment changes don't invalidate hash)
- `start_line` / `end_line` — still match tree-sitter positions
- `signature` — still first line of code
- `embedding_hash` — **NEEDS CHANGE**: should factor in leading_context changes

### Hash Strategy

```
content_hash = SHA256(content)              # Code-only, stable across comment edits
embedding_hash = SHA256(content + leading_context)  # Re-embed when comments change
smart_content_hash = content_hash           # Keep current: re-summarize when code changes
```

**Rationale**: If you edit a comment above a function, the embedding should update (new semantic meaning) but smart_content regeneration can wait (code didn't change).

---

## Edge Cases

### 1. Python `decorated_definition`

Tree-sitter wraps decorators as children of `decorated_definition`, not siblings:

```
decorated_definition [2:0 - 5:37]
  ├─ decorator [2:0 - 2:10]     ← CHILD, not sibling
  ├─ decorator [3:0 - 3:15]     ← CHILD, not sibling
  └─ function_definition [4:0]  ← This is the node we're creating
```

**Fix**: When the node's parent is `decorated_definition`, extract decorators from parent's children (not siblings).

### 2. Stacked Comments for Different Nodes

```python
# Comment for ClassA
class ClassA:
    pass

# Comment for ClassB    ← Must NOT be captured as ClassA's trailing context
class ClassB:
    pass
```

**Fix**: Only walk BACKWARDS (prev_named_sibling), never forward. Each comment attaches to the node immediately below it.

### 3. File-Level Comments (Shebangs, License Headers)

```python
#!/usr/bin/env python3
# Copyright 2024 Acme Corp
# Licensed under MIT

"""Module docstring."""

import os
```

**Fix**: For file-level nodes, the first N comment/expression_statement children ARE the leading context. But license headers (long boilerplate) should probably be excluded. Heuristic: cap at 500 chars or 10 lines for file-level leading_context.

### 4. Inline Comments

```python
def foo():
    x = 1  # This is inline ← already in content, not leading
```

**Not a problem**: Inline comments are within the byte range, already in `content`.

### 5. Multi-Line Block Comments (JS/Java)

```javascript
/**
 * Calculates the total price including tax.
 * @param {number} price - Base price
 * @returns {number} Total with tax
 */
function calculateTotal(price) { ... }
```

**Single comment node**: Tree-sitter treats `/** ... */` as one `comment` node. Walking one prev_named_sibling captures the entire JSDoc block.

---

## Worked Example: Before & After

### Before (current)

```
Node: callable:src/tax.py:calculate_tax
  content: "def calculate_tax(amount, region):\n    return amount * get_rate(region)"
  smart_content: "Calculates tax for a given amount."
  leading_context: None
  
Search "cross-border" → ❌ NOT FOUND
Search "dataclass" → ❌ NOT FOUND
Semantic "tax calculation algorithm" → ⚠️ Weak match (code only)
```

### After (with leading_context)

```
Node: callable:src/tax.py:calculate_tax
  content: "def calculate_tax(amount, region):\n    return amount * get_rate(region)"
  smart_content: "Calculates tax based on region rules. Handles cross-border edge cases. Uses @dataclass and @validate_input decorators."
  leading_context: "# This is an important algorithm for calculating tax rates.\n# It handles edge cases for cross-border transactions.\n@dataclass\n@validate_input"
  
Search "cross-border" → ✅ FOUND (leading_context, score 0.6)
Search "dataclass" → ✅ FOUND (leading_context, score 0.6)
Semantic "tax calculation algorithm" → ✅ Strong match (comments in embedding)
```

---

## Open Questions

### Q1: Should `leading_context` changes trigger smart_content regeneration?

**PROPOSED: No** — `smart_content_hash` stays based on `content_hash` (code-only). Comment changes trigger re-embedding but not LLM re-summarization. This avoids expensive LLM calls for comment typo fixes. The LLM already doesn't see the comments (it sees `content`), so adding leading_context to the prompt is a net improvement but not a re-trigger condition.

**Counter-argument**: If someone adds a comment explaining a complex algorithm, the LLM should re-summarize using that new context. But this is a rare enough case that manual `--force` is acceptable.

### Q2: What about trailing comments?

```python
def foo():
    pass
# end of foo section ← trailing comment
```

**PROPOSED: Out of scope.** Trailing comments are rare and ambiguous (is it for `foo` or the next function?). Leading context covers 95%+ of the value.

### Q3: Should decorators be in `leading_context` or `signature`?

**PROPOSED: Both.** Decorators in `leading_context` for search. Also prepend to `signature` for display:
- Current: `signature: "def calculate_tax(amount, region):"`
- New: `signature: "@dataclass\n@validate_input\ndef calculate_tax(amount, region):"`

Actually, this might be a separate enhancement. Keep `signature` as-is for now.

### Q4: Maximum size for leading_context?

**PROPOSED: 2000 characters** — Enough for 40-50 lines of comments (generous). Truncate with `[TRUNCATED]` marker. Prevents pathological cases (1000-line license header above first function).

---

## Implementation Estimate

| Task | Complexity | Notes |
|------|-----------|-------|
| Add `leading_context` field to CodeNode | CS-1 | Default None, backward compatible |
| Implement `_extract_leading_context()` in AST parser | CS-3 | Language-specific edge cases, blank line gap rule |
| Add to text/regex search | CS-1 | One more field check |
| Prepend to embedding input | CS-1 | Modify `_chunk_content` or caller |
| Pass to smart_content prompt | CS-2 | Template change + context builder |
| Update `embedding_hash` to include leading_context | CS-2 | Hash change triggers re-embed |
| Tests | CS-3 | Multi-language comment patterns |
| **Total** | **CS-3** | Mostly parser work |

---

## Quick Reference

```
leading_context captures:
  ✅ # single-line comments above functions/classes
  ✅ """ docstrings above functions (not inside) """
  ✅ /* block comments */  /** JSDoc */
  ✅ @decorator / @Annotation / #[attribute]
  ❌ inline comments (already in content)
  ❌ trailing comments (ambiguous ownership)
  ❌ license headers (capped at 2000 chars)

Searched by:
  ✅ Text search (score 0.6)
  ✅ Regex search (score 0.6)
  ✅ Semantic search (prepended to content before embedding)
  ✅ Smart content (passed to LLM prompt for richer summaries)

Hash behavior:
  content_hash     = SHA256(content)                    # Stable across comment edits
  embedding_hash   = SHA256(content + leading_context)  # Re-embed when comments change
  smart_content_hash = content_hash                     # Re-summarize only when code changes
```
