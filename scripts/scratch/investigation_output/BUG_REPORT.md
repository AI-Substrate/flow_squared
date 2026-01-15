# Bug Report: fs2 scan Enrichment Reprocessing Issues

**Date**: 2026-01-14
**Investigated by**: Claude Code
**Severity**: HIGH

## Executive Summary

Running `fs2 scan` repeatedly on an unchanged codebase detects files needing enrichment and produces duplicate output. Investigation identified **TWO CRITICAL BUGS**:

| Bug | Impact | Nodes Affected |
|-----|--------|----------------|
| #1: Node ID Collisions | Non-deterministic parsing - same node_id maps to different content | 9+ nodes per scan |
| #2: Placeholder Skip Logic | Nodes with placeholder smart_content are re-processed forever | 177 nodes |

---

## Bug #1: Non-Deterministic Node ID Collisions

### Symptoms
Between consecutive scans on unchanged code, 9 nodes have **different content and content_hash**:

```
type:tests/fixtures/samples/rust/lib.rs:Cacheable
  Scan 1: "pub trait Cacheable: Clone + Send + Sync + 'static {}"  (line 85)
  Scan 2: "impl<T: Clone + Send + Sync + 'static> Cacheable for T {}"  (line 87)
```

### Root Cause
The parser creates **duplicate node_ids** when:
1. A trait and its impl block share the same name (e.g., `Cacheable`)
2. Multiple anonymous nodes exist with the same parent

The file `tests/fixtures/samples/rust/lib.rs` has:
- Line 85: `pub trait Cacheable...` → `type:...Cacheable`
- Line 87: `impl<T:...> Cacheable for T {}` → `type:...Cacheable` (SAME ID!)

Whichever node is added to the graph **last** overwrites the previous one.

### Affected Files
| File | Collision |
|------|-----------|
| `rust/lib.rs` | trait vs impl for `Cacheable` |
| `c/main.cpp` | Multiple `ListenerId` methods at different lines |
| `c/algorithm.c` | Multiple `SortStats` definitions |
| `javascript/app.ts` | `Application` class vs extends clause |
| `typescript/class_generics.ts` | Generic type parameters |

### Code Location
- **Parser**: `src/fs2/core/adapters/ast_parser_impl.py:685-695`
- **Name extraction**: `_extract_name()` returns same name for trait and impl
- **Graph store**: Silent overwrite at `src/fs2/core/repos/graph_store_impl.py:137-147`

### Proposed Fix
Option A: Add suffix to distinguish impl blocks
```python
# For impl blocks, add @impl suffix
if node_type == "impl_item":
    name = f"{name}@impl"
```

Option B: Use line number when multiple same-named nodes exist
```python
# If node_id already exists with different content, add line number
if graph.has_node(node_id):
    node_id = f"{category}:{file_path}:{name}@{start_line}"
```

---

## Bug #2: Placeholder Smart Content Skip Logic Mismatch

### Symptoms
177 nodes are detected as needing enrichment every scan, even though they were already processed:

```
file:src/fs2/cli/__init__.py
  - has_smart_content_but_no_smart_content_embedding

callable:tests/unit/services/test_scan_pipeline.py:...CustomStage.name
  - has_smart_content_but_no_smart_content_embedding
```

### Root Cause
**Inconsistency between embedding generation and skip logic:**

1. **Embedding Generation** (lines 596-600) intentionally skips placeholder content:
   ```python
   if node.smart_content and not node.smart_content.startswith("[Empty content"):
       smart_chunks = self._chunk_content(node, is_smart_content=True)
   ```

2. **Skip Logic** (lines 487-493) requires `smart_content_embedding` if `smart_content` exists:
   ```python
   return not (
       node.smart_content is not None
       and (node.smart_content_embedding is None or len(node.smart_content_embedding) == 0)
   )
   ```

3. **Result**: Nodes with placeholder smart_content:
   - Get `smart_content = "[Empty content - no summary generated...]"`
   - Never get `smart_content_embedding` (intentionally skipped)
   - Always fail `_should_skip()` check
   - Are re-processed **every single scan**

### Affected Nodes
- All `__init__.py` files (empty/trivial content)
- Property accessors like `.name` properties
- Anonymous Go blocks
- Other trivial code nodes

### Code Location
- **Skip Logic**: `src/fs2/core/services/embedding/embedding_service.py:445-493`
- **Skip Placeholder**: `src/fs2/core/services/embedding/embedding_service.py:596-600`

### Proposed Fix
Update `_should_skip()` to recognize placeholder content:

```python
# Check smart_content embedding (if smart_content exists)
# Skip this check if smart_content is a placeholder (intentionally not embedded)
is_placeholder = (
    node.smart_content is not None
    and node.smart_content.startswith("[Empty content")
)

if is_placeholder:
    # Placeholder content is intentionally not embedded - that's OK
    return True  # Skip this node

# Has real smart_content - must have smart_content_embedding
return not (
    node.smart_content is not None
    and (
        node.smart_content_embedding is None
        or len(node.smart_content_embedding) == 0
    )
)
```

---

## Bug #3 (Minor): Duplicate CLI Output

### Symptoms
The scan output shows enrichment metrics twice with different labels:

```
✓ Enriched: 11 nodes        ← Smart Content
→ Preserved: 4386 nodes     ← Smart Content
✓ Enriched: 12 nodes        ← Embeddings
→ Preserved: 4374 nodes     ← Embeddings
```

### Root Cause
This is **NOT a bug** - it's showing two different enrichment types (Smart Content vs Embeddings). However, the output could be clearer.

### Proposed Fix
Improve output clarity:
```python
console.print_success(f"Smart Content: Enriched {enriched} nodes")
console.print_success(f"Embeddings: Enriched {enriched} nodes")
```

---

## Verification

### Test Case for Bug #1
```python
def test_impl_and_trait_have_different_node_ids():
    """Trait and impl block should not collide."""
    parser = TreeSitterParser(config)
    nodes = parser.parse(Path("fixtures/samples/rust/lib.rs"))

    # Find Cacheable nodes
    cacheable_nodes = [n for n in nodes if "Cacheable" in n.node_id and n.name == "Cacheable"]

    # Should have at least 2 (trait + impl)
    assert len(cacheable_nodes) >= 2

    # They should have different node_ids
    node_ids = [n.node_id for n in cacheable_nodes]
    assert len(node_ids) == len(set(node_ids)), "Node ID collision detected!"
```

### Test Case for Bug #2
```python
def test_placeholder_smart_content_is_skipped():
    """Nodes with placeholder smart_content should be skipped."""
    node = CodeNode(
        node_id="file:__init__.py",
        smart_content="[Empty content - no summary generated for file '__init__.py']",
        smart_content_hash="abc123",
        smart_content_embedding=None,  # Intentionally None
        embedding=((0.1, 0.2),),
        embedding_hash="abc123",
        content_hash="abc123",
        ...
    )

    service = EmbeddingService(config, adapter)

    # Should skip - placeholder content is intentionally not embedded
    assert service._should_skip(node) is True
```

---

## Impact Assessment

| Bug | Scans Affected | Performance Impact | Data Quality Impact |
|-----|----------------|-------------------|---------------------|
| #1 Node Collisions | Every scan | Low | HIGH - wrong content in graph |
| #2 Placeholder Skip | Every scan | MEDIUM - 177 unnecessary API calls | Low |
| #3 Duplicate Output | Every scan | None | Low - cosmetic only |

---

## Files to Modify

| File | Change |
|------|--------|
| `src/fs2/core/adapters/ast_parser_impl.py` | Disambiguate trait vs impl node_ids |
| `src/fs2/core/services/embedding/embedding_service.py` | Fix `_should_skip()` for placeholders |
| `src/fs2/cli/scan.py` (optional) | Clarify output labels |

---

## Evidence Files

- `scripts/scratch/investigation_output/scan_1_output.txt` - First scan verbose output
- `scripts/scratch/investigation_output/scan_2_output.txt` - Second scan verbose output
- `scripts/scratch/investigation_output/investigation_report.md` - Detailed node comparison
- `scripts/scratch/investigate_embedding_reprocessing.py` - Investigation script

---

## Recommendations

1. **Immediate**: Fix Bug #2 (placeholder skip logic) - easy fix, high impact
2. **Short-term**: Fix Bug #1 (node ID collisions) - requires careful parser changes
3. **Optional**: Improve CLI output clarity

