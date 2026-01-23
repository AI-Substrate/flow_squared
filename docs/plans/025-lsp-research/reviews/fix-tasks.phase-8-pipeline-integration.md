# Phase 8: Pipeline Integration - Fix Tasks

**Review**: [review.phase-8-pipeline-integration.md](./review.phase-8-pipeline-integration.md)
**Priority**: MEDIUM (no blocking issues, but type safety and encapsulation violations)
**Testing Approach**: Full TDD (write/update tests first if needed)

---

## Fix Task 1: REL-001 - Add Missing Type Annotation

**Severity**: MEDIUM
**File**: `src/fs2/core/services/stages/relationship_extraction_stage.py`
**Lines**: 148

### Problem

The `node` parameter in `_extract_lsp_relationships()` lacks a type annotation, causing mypy --strict to fail.

### Current Code

```python
def _extract_lsp_relationships(self, node) -> list[CodeEdge]:
    """Extract relationships using LSP adapter.
    ...
    """
```

### Fix

1. Add `CodeNode` to the TYPE_CHECKING imports block (if not already present)
2. Add type annotation to the parameter

### Patch

```diff
--- a/src/fs2/core/services/stages/relationship_extraction_stage.py
+++ b/src/fs2/core/services/stages/relationship_extraction_stage.py
@@ -19,6 +19,7 @@ from fs2.core.services.relationship_extraction.text_reference_extractor import (
 )
 
 if TYPE_CHECKING:
+    from fs2.core.models.code_node import CodeNode
     from fs2.core.adapters.lsp_adapter import LspAdapter
     from fs2.core.services.pipeline_context import PipelineContext
 
@@ -145,7 +146,7 @@ class RelationshipExtractionStage:
 
         return context
 
-    def _extract_lsp_relationships(self, node) -> list[CodeEdge]:
+    def _extract_lsp_relationships(self, node: "CodeNode") -> list[CodeEdge]:
         """Extract relationships using LSP adapter.
 
         This is a placeholder for LSP-based extraction.
```

### Validation

```bash
# Verify mypy passes for this file
uv run mypy src/fs2/core/services/stages/relationship_extraction_stage.py --strict

# Verify tests still pass
uv run pytest tests/unit/services/stages/test_relationship_extraction_stage.py -v
```

---

## Fix Task 2: REL-002 - Encapsulation Violation with Private Method

**Severity**: MEDIUM
**File**: `src/fs2/core/services/stages/relationship_extraction_stage.py`
**Lines**: 134
**Also Affects**: `src/fs2/core/services/relationship_extraction/text_reference_extractor.py`

### Problem

The code accesses `self._text_extractor._deduplicate_edges(all_edges)`, which is a private method (leading underscore). This breaks encapsulation and creates fragile coupling.

### Current Code

```python
# Line 134 in relationship_extraction_stage.py
deduplicated = self._text_extractor._deduplicate_edges(all_edges)
```

### Fix Option A (Preferred): Make Method Public

Rename `_deduplicate_edges` to `deduplicate_edges` in TextReferenceExtractor.

### Patch Option A

```diff
--- a/src/fs2/core/services/relationship_extraction/text_reference_extractor.py
+++ b/src/fs2/core/services/relationship_extraction/text_reference_extractor.py
@@ -82,7 +82,7 @@ class TextReferenceExtractor:
 
         return self._deduplicate_edges(all_edges)
 
-    def _deduplicate_edges(self, edges: list[CodeEdge]) -> list[CodeEdge]:
+    def deduplicate_edges(self, edges: list[CodeEdge]) -> list[CodeEdge]:
         """Remove duplicate edges, keeping highest confidence for each source→target pair.
 
         Args:
@@ -105,3 +105,11 @@ class TextReferenceExtractor:
                 best[key] = edge
 
         return list(best.values())
+
+    # Keep internal alias for backward compatibility within this class
+    _deduplicate_edges = deduplicate_edges
```

```diff
--- a/src/fs2/core/services/stages/relationship_extraction_stage.py
+++ b/src/fs2/core/services/stages/relationship_extraction_stage.py
@@ -131,7 +131,7 @@ class RelationshipExtractionStage:
                     # Don't add to errors - LSP failures are expected when servers unavailable
 
         # Deduplicate edges using existing algorithm (DYK-5)
-        deduplicated = self._text_extractor._deduplicate_edges(all_edges)
+        deduplicated = self._text_extractor.deduplicate_edges(all_edges)
 
         # Set context fields
         context.relationships = deduplicated
```

### Fix Option B (Alternative): Add Public Wrapper

Add a public method that wraps the private implementation.

### Patch Option B

```diff
--- a/src/fs2/core/services/relationship_extraction/text_reference_extractor.py
+++ b/src/fs2/core/services/relationship_extraction/text_reference_extractor.py
@@ -105,3 +105,17 @@ class TextReferenceExtractor:
                 best[key] = edge
 
         return list(best.values())
+
+    def deduplicate(self, edges: list[CodeEdge]) -> list[CodeEdge]:
+        """Public API: Remove duplicate edges, keeping highest confidence.
+
+        This is the public interface for edge deduplication, used by
+        RelationshipExtractionStage to combine edges from multiple sources.
+
+        Args:
+            edges: List of CodeEdge instances (may contain duplicates)
+
+        Returns:
+            Deduplicated list with highest confidence edge per source→target pair
+        """
+        return self._deduplicate_edges(edges)
```

Then update the caller:

```diff
--- a/src/fs2/core/services/stages/relationship_extraction_stage.py
+++ b/src/fs2/core/services/stages/relationship_extraction_stage.py
@@ -131,7 +131,7 @@ class RelationshipExtractionStage:
                     # Don't add to errors - LSP failures are expected when servers unavailable
 
         # Deduplicate edges using existing algorithm (DYK-5)
-        deduplicated = self._text_extractor._deduplicate_edges(all_edges)
+        deduplicated = self._text_extractor.deduplicate(all_edges)
 
         # Set context fields
         context.relationships = deduplicated
```

### TDD Approach

Before making any changes, add a test to verify the public API:

```python
# Add to tests/unit/services/test_text_reference_extractor.py

def test_given_duplicate_edges_when_calling_deduplicate_then_returns_unique_highest_confidence():
    """
    Purpose: Verify public deduplicate() API works correctly.
    Quality Contribution: Ensures encapsulation is respected.
    Acceptance Criteria: Duplicate removal with highest confidence preserved.
    """
    from fs2.core.models.code_edge import CodeEdge, EdgeType
    from fs2.core.services.relationship_extraction.text_reference_extractor import (
        TextReferenceExtractor,
    )

    extractor = TextReferenceExtractor()
    edges = [
        CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.REFERENCES,
            confidence=0.5,
            resolution_rule="filename:raw",
        ),
        CodeEdge(
            source_node_id="file:a.py",
            target_node_id="file:b.py",
            edge_type=EdgeType.REFERENCES,
            confidence=1.0,
            resolution_rule="nodeid:explicit",
        ),
    ]

    # Use public API (not _deduplicate_edges)
    result = extractor.deduplicate(edges)  # or deduplicate_edges

    assert len(result) == 1
    assert result[0].confidence == 1.0
```

### Validation

```bash
# Verify tests still pass after changes
uv run pytest tests/unit/services/test_text_reference_extractor.py -v
uv run pytest tests/unit/services/stages/test_relationship_extraction_stage.py -v

# Verify no ruff issues
uv run ruff check src/fs2/core/services/relationship_extraction/text_reference_extractor.py
```

---

## Fix Summary

| Fix ID | Task | Effort | Blocking |
|--------|------|--------|----------|
| REL-001 | Add type annotation | ~2 min | No |
| REL-002 | Make deduplicate method public | ~5 min | No |

**Total Estimated Time**: ~10 minutes

**After Fixes**:
1. Run full test suite: `uv run pytest tests/unit/services/ -v`
2. Run type check: `uv run mypy src/fs2/core/services/stages/relationship_extraction_stage.py --strict`
3. Re-run code review or request re-review
