# Fix Tasks: Phase 3 - SolidLspAdapter Implementation

**Review**: [./review.phase-3-solidlspadapter-implementation.md](./review.phase-3-solidlspadapter-implementation.md)
**Created**: 2026-01-19

---

## Priority: HIGH (Blocking)

### FIX-001: Path Traversal Protection in _uri_to_relative()

**Severity**: MEDIUM (Security)
**File**: `src/fs2/core/adapters/lsp_adapter_solidlsp.py`
**Lines**: 575-599

**Issue**: URI handler lacks path traversal protection. A malicious LSP response with `file:///../../sensitive.py` could escape project_root boundary.

**Fix** (TDD: Write test first):

1. Add test to `tests/unit/adapters/test_lsp_type_translation.py`:
```python
def test_given_traversal_path_when_uri_to_relative_then_raises_or_sanitizes(self):
    """Security: Path traversal attempts should be blocked."""
    from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter
    
    # These should NOT escape project_root
    malicious_uris = [
        "file:///project/../../../etc/passwd",
        "file:///project/subdir/../../../sensitive.py",
    ]
    for uri in malicious_uris:
        result = SolidLspAdapter._uri_to_relative(uri, "/project")
        # Result should NOT contain ".." or should raise ValueError
        assert ".." not in result or result == "etc/passwd"  # Sanitized
```

2. Apply fix to `_uri_to_relative()`:
```python
@staticmethod
def _uri_to_relative(uri: str, project_root: str) -> str:
    """Convert file URI to relative path with traversal protection."""
    # Handle file:// URIs
    if uri.startswith("file://"):
        abs_path = uri[7:]
        # Handle Windows paths (file:///C:/...)
        if len(abs_path) > 2 and abs_path[2] == ":":
            abs_path = abs_path[1:]
    else:
        abs_path = uri

    # Make relative to project root WITH TRAVERSAL PROTECTION
    try:
        resolved_path = Path(abs_path).resolve()
        resolved_root = Path(project_root).resolve()
        rel_path = resolved_path.relative_to(resolved_root)
        return str(rel_path)
    except ValueError:
        # Path is not within project root - log warning and return basename only
        log.warning(f"Path {abs_path} outside project root, using basename")
        return Path(abs_path).name
```

---

### FIX-002: lstrip('/') Misuse in _source_to_node_id()

**Severity**: MEDIUM (Security)
**File**: `src/fs2/core/adapters/lsp_adapter_solidlsp.py`
**Lines**: 569-571

**Issue**: `lstrip('/')` removes ALL leading slashes. `///../../file.py` becomes `../file.py`.

**Fix**:
```python
# Before (line 569-571)
rel_path = source_file
if rel_path.startswith("/"):
    rel_path = rel_path.lstrip("/")

# After
rel_path = source_file
if rel_path.startswith("/"):
    rel_path = rel_path.removeprefix("/")  # Remove only ONE leading slash
# Add traversal check
if ".." in rel_path:
    log.warning(f"Suspicious path with traversal: {rel_path}")
    rel_path = Path(rel_path).name  # Use basename only
```

---

### FIX-003: Defensive Dict Access in _translate_reference()

**Severity**: HIGH (Correctness)
**File**: `src/fs2/core/adapters/lsp_adapter_solidlsp.py`
**Lines**: 457-460

**Issue**: `_translate_reference()` accesses `location['uri']` and `location['range']['start']['line']` without validation.

**Fix** (TDD: Write test first):

1. Add test:
```python
def test_given_malformed_location_when_translating_then_handles_gracefully(self):
    """Correctness: Malformed Location dicts should not crash."""
    from fs2.core.adapters.lsp_adapter_solidlsp import SolidLspAdapter
    
    malformed_location = {"uri": "file:///test.py"}  # Missing 'range'
    
    # Should either return valid edge or raise specific exception
    with pytest.raises((KeyError, LspAdapterError)):
        SolidLspAdapter._translate_reference(
            location=malformed_location,
            source_file="lib.py",
            source_line=10,
            project_root="/project",
        )
```

2. Apply fix:
```python
@staticmethod
def _translate_reference(
    location: "Location",
    source_file: str,
    source_line: int,
    project_root: str,
) -> CodeEdge:
    """Translate single LSP Location to CodeEdge for reference."""
    # Defensive access to Location fields
    try:
        ref_file = location.get("relativePath") or SolidLspAdapter._uri_to_relative(
            location["uri"], project_root
        )
        ref_line = location["range"]["start"]["line"]
    except KeyError as e:
        raise LspAdapterError(f"Malformed LSP Location: missing {e}") from e
    
    # ... rest of method
```

---

### FIX-004: Defensive Dict Access in _location_to_node_id()

**Severity**: HIGH (Correctness)
**File**: `src/fs2/core/adapters/lsp_adapter_solidlsp.py`
**Lines**: 547-549

**Issue**: `_location_to_node_id()` accesses `location["uri"]` without validation.

**Fix**:
```python
@staticmethod
def _location_to_node_id(location: "Location", project_root: str) -> str:
    """Convert LSP Location to tree-sitter compatible node_id."""
    rel_path = location.get("relativePath")
    if not rel_path:
        uri = location.get("uri")
        if not uri:
            log.warning("Location missing both relativePath and uri")
            return "file:unknown"
        rel_path = SolidLspAdapter._uri_to_relative(uri, project_root)

    return f"file:{rel_path}"
```

---

### FIX-005: Sync Footnote Ledger

**Severity**: HIGH (Graph Integrity)
**File**: `docs/plans/025-lsp-research/lsp-integration-plan.md` OR `tasks/phase-3-solidlspadapter-implementation/tasks.md`

**Issue**: Dossier tasks.md references `[^14]` but plan only defines `[^13]` for Phase 3.

**Fix Options**:

A) **Add `[^14]` to plan** (recommended):
   - Edit plan's Change Footnotes Ledger section
   - Add entry after `[^13]`:
   ```markdown
   [^14]: Phase 3 - Implementation files (linked from dossier stubs)
     - `file:tests/integration/test_lsp_pyright.py`
     - `file:tests/unit/adapters/test_lsp_type_translation.py`
     - `class:src/fs2/core/adapters/lsp_adapter_solidlsp.py:SolidLspAdapter`
     - (methods listed in dossier stubs table)
   ```

B) **Update dossier to use `[^13]`**:
   - Edit tasks.md line 463
   - Change `[^14]` to `[^13]`

---

## Priority: MEDIUM (Non-Blocking)

### FIX-006: Remove Dead Code

**File**: `src/fs2/core/adapters/lsp_adapter_solidlsp.py`
**Lines**: 509-511

**Issue**: Lines assign to unused `_` variable.

**Fix**: Remove lines 509-511:
```python
# Remove these lines:
_ = location.get("relativePath") or SolidLspAdapter._uri_to_relative(
    location["uri"], project_root
)
```

---

### FIX-007: Replace Asserts with Explicit Checks

**File**: `src/fs2/core/adapters/lsp_adapter_solidlsp.py`
**Lines**: 253-254, 313-314

**Issue**: Assert statements are disabled with Python `-O` flag.

**Fix**:
```python
# Before (lines 253-254)
assert self._server is not None
assert self._project_root is not None

# After
if self._server is None or self._project_root is None:
    raise RuntimeError("Server not properly initialized after check")
```

---

## Testing Approach

Per **Full TDD** doctrine:
1. Write failing test for each fix (RED)
2. Implement fix (GREEN)
3. Refactor if needed (REFACTOR)

After all fixes, run:
```bash
uv run pytest tests/unit/adapters/test_lsp_type_translation.py \
  tests/integration/test_lsp_pyright.py -v
uv run ruff check src/fs2/core/adapters/lsp_adapter_solidlsp.py
uv run mypy src/fs2/core/adapters/lsp_adapter_solidlsp.py --strict
```

---

## Re-Review Command

After fixes applied:
```
/plan-7-code-review --phase "Phase 3: SolidLspAdapter Implementation" \
  --plan /workspaces/flow_squared/docs/plans/025-lsp-research/lsp-integration-plan.md
```
