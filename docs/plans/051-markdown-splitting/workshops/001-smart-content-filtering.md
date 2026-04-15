# Workshop: Smart Content Filtering for Markdown Sections

**Type**: Integration Pattern
**Plan**: 051-markdown-splitting
**Spec**: [markdown-splitting-spec.md](../markdown-splitting-spec.md)
**Created**: 2026-04-15
**Status**: Draft

**Related Documents**:
- [research-dossier.md](../research-dossier.md) — PL-03: 800 token doc chunks
- [FX001-e2e-regression-tests.md](../fixes/FX001-e2e-regression-tests.md) — AC-12 embedding tests

---

## Purpose

Markdown section nodes contain human-written prose that doesn't benefit from LLM summarization. Smart content generation would waste API tokens summarizing text that's already readable. This workshop explores how to skip smart content for markdown sections while preserving embedding generation.

## Key Questions Addressed

- Where in the pipeline should the filter go?
- What's the filtering mechanism — config, content_type, category, or language?
- What happens to nodes that skip smart content — do they still get embeddings?
- Should the raw content be copied to smart_content, or should it stay null?

---

## Current Pipeline Flow

```
Discovery → Parsing → CrossFileRels → SmartContent → Embedding → Storage
```

### SmartContent Stage Filter Chain (smart_content_stage.py:113-133)

```python
# Step 3: Filter nodes that need generation
needs_generation = [n for n in context.nodes if n.smart_content is None]

# Step 3b: Apply category filter if configured
if smart_content_config and getattr(smart_content_config, 'enabled_categories', None) is not None:
    enabled = set(smart_content_config.enabled_categories)
    needs_generation = [n for n in needs_generation if n.category in enabled]
```

### SmartContentService._should_skip (smart_content_service.py:183-194)

```python
def _should_skip(self, node: CodeNode) -> bool:
    """Skip if hash matches AND smart_content already exists."""
    return (
        node.smart_content_hash is not None
        and node.smart_content_hash == node.content_hash
        and node.smart_content is not None
    )
```

### Embedding Service Behavior (embedding_service.py:242-261)

```python
# Embeds EITHER smart_content OR raw content
if is_smart_content:
    text = node.smart_content    # Used for smart_content_embedding
else:
    text = node.content          # Used for primary embedding
```

**Key insight**: Embeddings work on raw `node.content` regardless of whether `smart_content` is set. The `smart_content_embedding` is a *separate* embedding field. So skipping smart content does NOT break primary embeddings.

---

## Design Options

### Option A: Content-Type Filter in SmartContent Stage

**Where**: `smart_content_stage.py:114`, add a filter before queueing.

```python
# Step 3: Filter nodes that need generation
needs_generation = [
    n for n in context.nodes
    if n.smart_content is None
    and not _is_self_documenting(n)  # NEW: skip markdown sections
]

def _is_self_documenting(node: CodeNode) -> bool:
    """Content nodes in human-readable languages don't need LLM summarization."""
    return (
        node.content_type == ContentType.CONTENT
        and node.category == "section"
        and node.language in ("markdown", "rst")
    )
```

| Aspect | Assessment |
|--------|-----------|
| **Precision** | ✅ Only skips markdown/rst sections — files, callables, types still get smart content |
| **Location** | ✅ Earliest filter point — nodes never enter the batch queue |
| **Config** | ❌ Not configurable — hardcoded |
| **Side effects** | `smart_content` stays None → no `smart_content_embedding` → search uses raw content embedding only |
| **Lines of code** | ~5 |

### Option B: Config-Driven `enabled_categories`

**Where**: `objects.py` SmartContentConfig + `smart_content_stage.py:116-133` (already exists!).

```yaml
# .fs2/config.yaml
smart_content:
  enabled_categories:
    - callable
    - type
    - file
    # section deliberately omitted → skipped
```

| Aspect | Assessment |
|--------|-----------|
| **Precision** | ⚠️ Skips ALL sections (rst too) — may be too broad if rst sections need summarization |
| **Location** | ✅ Uses existing filter infrastructure at line 116-133 |
| **Config** | ✅ Fully user-configurable |
| **Side effects** | Same as A — no smart_content_embedding |
| **Lines of code** | ~3 (just set default in config) |

**Problem**: The `enabled_categories` filter code already exists in the stage but `SmartContentConfig` doesn't actually have this field — it's dead code waiting for a config schema addition.

### Option C: Copy Content as Smart Content

**Where**: `smart_content_service.py:141-180`, before LLM call.

```python
async def generate_smart_content(self, node: CodeNode) -> CodeNode:
    if self._should_skip(node):
        return node

    # NEW: For self-documenting nodes, use raw content as smart_content
    if self._is_self_documenting(node):
        return dataclasses.replace(
            node,
            smart_content=node.content,
            smart_content_hash=node.content_hash,
        )

    # ... existing LLM path
```

| Aspect | Assessment |
|--------|-----------|
| **Precision** | ✅ Same as A |
| **Location** | ⚠️ Later in pipeline — nodes still enter batch queue, just skip the LLM call |
| **Config** | ❌ Not configurable |
| **Side effects** | `smart_content` IS set (= raw content) → `smart_content_embedding` gets generated (duplicate of raw embedding) |
| **Lines of code** | ~10 |

**Problem**: This wastes embedding tokens generating a `smart_content_embedding` that's identical to the raw content `embedding`. Doubles the embedding cost for no benefit.

### Option D: Hybrid — Stage Filter + Populate Smart Content

**Where**: `smart_content_stage.py:114`.

```python
# Step 3: Separate self-documenting nodes
self_documenting = [
    n for n in context.nodes
    if n.smart_content is None and _is_self_documenting(n)
]
needs_generation = [
    n for n in context.nodes
    if n.smart_content is None and not _is_self_documenting(n)
]

# Set smart_content = content for self-documenting nodes (no LLM call)
for i, node in enumerate(context.nodes):
    if node in self_documenting:
        context.nodes[i] = dataclasses.replace(
            node,
            smart_content=node.content,
            smart_content_hash=node.content_hash,
        )
```

| Aspect | Assessment |
|--------|-----------|
| **Precision** | ✅ Only markdown/rst sections |
| **Location** | ✅ Earliest filter point |
| **Config** | ❌ Not configurable |
| **Side effects** | ⚠️ `smart_content` IS set → triggers `smart_content_embedding` in embedding stage (wasteful) |
| **Lines of code** | ~15 |

---

## Recommendation: Option A

**Option A is the simplest and most correct.**

### Why Option A

1. **Cheapest** — no LLM tokens, no extra embedding tokens
2. **Simplest** — 5 lines, one filter function, one location
3. **No side effects** — `smart_content` stays None, embedding service only generates raw content embedding (which is what we want for human-readable prose)
4. **Precise** — `content_type == CONTENT + category == "section" + language in ("markdown", "rst")` only catches documentation sections, not code sections or files

### What About `smart_content_embedding`?

When `smart_content` is None, the embedding service skips `smart_content_embedding`. This is **correct behavior** for markdown sections:
- The raw content **is** the human-readable text → the raw `embedding` captures it perfectly
- A `smart_content_embedding` would just be an LLM paraphrase of already-clear text → wasteful and potentially less accurate

### What About Search Quality?

Search uses `node.content` for text/regex matching and `node.embedding` for semantic matching. Neither depends on `smart_content`. The `smart_content` field is only used for:
1. Generating `smart_content_embedding` (a secondary search signal)
2. Display in `get_node --detail max`

For markdown sections, the raw content serves both purposes better than an LLM summary would.

---

## Implementation Sketch

### Where to Add the Filter

```python
# src/fs2/core/services/stages/smart_content_stage.py
# After line 114, before the enabled_categories filter

# Step 3: Filter nodes that need generation
needs_generation = [n for n in context.nodes if n.smart_content is None]

# Step 3a: Skip self-documenting content (no LLM summary needed)
pre_filter = len(needs_generation)
needs_generation = [n for n in needs_generation if not _is_self_documenting(n)]
skipped_self_doc = pre_filter - len(needs_generation)
if skipped_self_doc > 0:
    logger.info(
        "SmartContentStage: skipped %d self-documenting nodes "
        "(markdown/rst sections)",
        skipped_self_doc,
    )
```

### The Filter Function

```python
from fs2.core.models.content_type import ContentType

_SELF_DOCUMENTING_LANGUAGES = frozenset({"markdown", "rst"})

def _is_self_documenting(node: CodeNode) -> bool:
    """Content section nodes in human-readable languages don't need LLM summarization.

    Markdown and RST sections are already human-written prose — summarizing them
    with an LLM wastes tokens and produces inferior results compared to the
    original text.
    """
    return (
        node.content_type == ContentType.CONTENT
        and node.category == "section"
        and node.language in _SELF_DOCUMENTING_LANGUAGES
    )
```

### Test

```python
# tests/unit/services/stages/test_smart_content_stage.py (or inline)

def test_markdown_sections_skip_smart_content():
    """Markdown section nodes should not be sent for LLM summarization."""
    section = CodeNode.create_section(
        file_path="docs/plan.md",
        language="markdown",
        ts_kind="section",
        name="Testing Philosophy",
        qualified_name="Testing Philosophy",
        start_line=1, end_line=5,
        start_column=0, end_column=0,
        start_byte=0, end_byte=50,
        content="## Testing Philosophy\n\nUse fakes over mocks.\n",
        signature="## Testing Philosophy",
    )
    assert _is_self_documenting(section) is True
    assert section.smart_content is None  # stays None — no LLM call
```

---

## Decision Matrix

| Criterion | A (Stage Filter) | B (Config) | C (Copy Content) | D (Hybrid) |
|-----------|:-:|:-:|:-:|:-:|
| No LLM tokens wasted | ✅ | ✅ | ✅ | ✅ |
| No extra embedding tokens | ✅ | ✅ | ❌ | ❌ |
| Lines of code | 5 | 3 | 10 | 15 |
| User configurable | ❌ | ✅ | ❌ | ❌ |
| Uses existing infrastructure | ❌ | ✅ | ❌ | ❌ |
| Precise (md sections only) | ✅ | ⚠️ | ✅ | ✅ |
| Search quality preserved | ✅ | ✅ | ✅ | ✅ |

**Winner: Option A** — simplest, cheapest, most precise. Config (Option B) is a nice follow-up if we later want user control over which categories get smart content.

---

## Open Questions

### Q1: Should RST sections also be skipped?

**RESOLVED**: Yes — RST sections are also human-written documentation prose. The filter uses `language in ("markdown", "rst")` to cover both.

### Q2: Should file-level markdown nodes also skip smart content?

**OPEN**: Currently only `section` nodes are filtered. The `file:` node for a markdown file would still get smart content if smart content is enabled. This seems fine — a file-level summary of a large markdown document is actually useful (it's the whole-document summary vs individual section content). But worth confirming.

### Q3: Future — should `enabled_categories` in config be wired up?

**OPEN**: The stage code already has dead infrastructure for `enabled_categories` (line 116-133) but `SmartContentConfig` doesn't expose it. Could be wired up as a follow-up for user control over which categories get smart content.
