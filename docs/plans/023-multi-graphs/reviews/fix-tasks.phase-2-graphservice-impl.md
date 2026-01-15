# Fix Tasks: Phase 2 - GraphService Implementation

**Review**: [./review.phase-2-graphservice-impl.md](./review.phase-2-graphservice-impl.md)
**Verdict**: REQUEST_CHANGES
**Created**: 2026-01-13

---

## Priority: CRITICAL (Must Fix Before Merge)

### FIX-001: Sync Plan Task Statuses with Dossier

**Severity**: CRITICAL
**Effort**: Low (documentation update)
**Testing**: N/A (documentation)

**Issue**: Plan § 5 Phase 2 tasks table shows tasks 2.1-2.10 as `[ ]` pending, but all are complete in dossier.

**Fix**:
Run `/plan-6a-update-progress` to synchronize plan with dossier completion status.

Alternatively, manually update `/workspaces/flow_squared/docs/plans/023-multi-graphs/multi-graphs-plan.md` lines 394-405:

```diff
- | 2.1 | [ ] | Write tests for GraphService.get_graph() | 3 | ...
+ | 2.1 | [x] | Write tests for GraphService.get_graph() | 3 | ...
- | 2.2 | [ ] | Write tests for staleness detection | 2 | ...
+ | 2.2 | [x] | Write tests for staleness detection | 2 | ...
... (repeat for 2.3-2.10)
```

---

### FIX-002: Add Missing Plan Tasks for T000 and T011

**Severity**: HIGH
**Effort**: Low (documentation update)
**Testing**: N/A (documentation)

**Issue**: Tasks T000 (Add _source_dir) and T011 (Integration test) exist in dossier but not in plan.

**Fix**:
Add to plan § 5 Phase 2 tasks table:

```markdown
| 2.0 | [x] | Add _source_dir field to OtherGraph | 3 | Tests for source_dir tracking; field added; merge sets value | - | Prerequisite for DYK-02 |
```

```markdown
| 2.11 | [x] | Integration test with real config loading | 2 | End-to-end YAML→Service test passes | - | Validates DYK-04 |
```

---

## Priority: HIGH (Should Fix Before Merge)

### FIX-003: Update Footnote Node ID Prefixes

**Severity**: MEDIUM (multiple instances = HIGH aggregate)
**Effort**: Medium (13 node IDs to update)
**Testing**: Verify with `mcp__flowspace__get_node()` after update

**Issue**: Footnotes [^3], [^4], [^5] use incorrect node ID prefixes:
- `class:` should be `type:`
- `method:` should be `callable:`

**Fix in `/workspaces/flow_squared/docs/plans/023-multi-graphs/multi-graphs-plan.md` lines 937-957**:

#### [^3] Updates:
```diff
- - `class:src/fs2/config/objects.py:OtherGraph` (added _source_dir PrivateAttr)
+ - `type:src/fs2/config/objects.py:OtherGraph` (added _source_dir PrivateAttr)
- - `method:src/fs2/config/service.py:FS2ConfigurationService._concatenate_and_dedupe`
+ - `callable:src/fs2/config/service.py:FS2ConfigurationService._concatenate_and_dedupe`
- - `method:src/fs2/config/service.py:FS2ConfigurationService._create_other_graphs_config`
+ - `callable:src/fs2/config/service.py:FS2ConfigurationService._create_other_graphs_config`
```

#### [^4] Updates:
```diff
- - `class:src/fs2/core/services/graph_service.py:GraphServiceError`
+ - `type:src/fs2/core/services/graph_service.py:GraphServiceError`
- - `class:src/fs2/core/services/graph_service.py:UnknownGraphError`
+ - `type:src/fs2/core/services/graph_service.py:UnknownGraphError`
- - `class:src/fs2/core/services/graph_service.py:GraphFileNotFoundError`
+ - `type:src/fs2/core/services/graph_service.py:GraphFileNotFoundError`
- - `class:src/fs2/core/services/graph_service.py:GraphInfo`
+ - `type:src/fs2/core/services/graph_service.py:GraphInfo`
```

#### [^5] Updates:
```diff
- - `class:src/fs2/core/services/graph_service.py:GraphService`
+ - `type:src/fs2/core/services/graph_service.py:GraphService`
- - `method:src/fs2/core/services/graph_service.py:GraphService._resolve_path`
+ - `callable:src/fs2/core/services/graph_service.py:GraphService._resolve_path`
- - `method:src/fs2/core/services/graph_service.py:GraphService.get_graph`
+ - `callable:src/fs2/core/services/graph_service.py:GraphService.get_graph`
- - `method:src/fs2/core/services/graph_service.py:GraphService.list_graphs`
+ - `callable:src/fs2/core/services/graph_service.py:GraphService.list_graphs`
- - `method:src/fs2/core/services/graph_service.py:GraphService._is_stale`
+ - `callable:src/fs2/core/services/graph_service.py:GraphService._is_stale`
- - `method:src/fs2/core/services/graph_service.py:GraphService._load_graph`
+ - `callable:src/fs2/core/services/graph_service.py:GraphService._load_graph`
```

---

## Priority: MEDIUM (Recommended Improvements)

### FIX-004: Use dict.get() in _is_stale for TOCTOU Safety

**Severity**: MEDIUM
**Effort**: Low (single method change)
**Testing**: Run `pytest tests/unit/services/test_graph_service.py -v`

**File**: `/workspaces/flow_squared/src/fs2/core/services/graph_service.py`
**Lines**: 255-278

**Current**:
```python
def _is_stale(self, name: str, path: Path) -> bool:
    if name not in self._cache:
        return True

    entry = self._cache[name]  # Potential KeyError if evicted
    try:
        stat = path.stat()
        return stat.st_mtime != entry.mtime or stat.st_size != entry.size
    except OSError:
        return True
```

**Recommended**:
```python
def _is_stale(self, name: str, path: Path) -> bool:
    entry = self._cache.get(name)  # Atomic read
    if entry is None:
        return True

    try:
        stat = path.stat()
        return stat.st_mtime != entry.mtime or stat.st_size != entry.size
    except OSError:
        return True
```

---

### FIX-005: Remove Production Dependency on FakeConfigurationService

**Severity**: MEDIUM
**Effort**: Medium (requires refactoring)
**Testing**: Run full test suite after change

**File**: `/workspaces/flow_squared/src/fs2/core/services/graph_service.py`
**Lines**: 294-308

**Issue**: Production code imports `FakeConfigurationService` - architectural smell.

**Option A: Create Minimal ConfigurationService**
```python
# In graph_service.py or new file
class GraphStoreConfig(ConfigurationService):
    """Minimal config service for GraphStore instantiation."""
    def __init__(self, graph_path: str):
        self._store: dict[type, Any] = {}
        self.set(ScanConfig(scan_paths=["."]))
        self.set(GraphConfig(graph_path=graph_path))
    # ... implement get/set/require
```

**Option B: Refactor NetworkXGraphStore Constructor**
Accept config values directly instead of ConfigurationService.

---

## Priority: LOW (Optional Enhancements)

### FIX-006: Add Path Boundary Validation

**Severity**: MEDIUM (security)
**Effort**: Medium
**Testing**: Add test for path traversal rejection

**File**: `/workspaces/flow_squared/src/fs2/core/services/graph_service.py`
**Lines**: 197-229

**Add after path resolution**:
```python
def _resolve_path(self, graph: OtherGraph) -> Path:
    # ... existing code ...
    resolved = path.resolve()

    # Security: Validate path is within allowed directories
    allowed_prefixes = [
        Path.home(),
        Path.cwd(),
    ]
    if not any(str(resolved).startswith(str(p.resolve())) for p in allowed_prefixes):
        raise GraphServiceError(
            f"Graph path '{resolved}' is outside allowed directories"
        )
    return resolved
```

---

## Execution Order

1. **FIX-001** (CRITICAL) - Run `plan-6a-update-progress`
2. **FIX-002** (HIGH) - Add T000/T011 to plan tasks
3. **FIX-003** (HIGH) - Update 13 footnote node IDs
4. **Verify** - Re-run `/plan-7-code-review` to confirm fixes
5. **Optional** - FIX-004, FIX-005, FIX-006 for code quality

---

## Post-Fix Validation

After completing fixes 1-3:

```bash
# Verify tests still pass
uv run pytest tests/unit/services/test_graph_service.py tests/unit/config/test_other_graphs_config.py -v

# Re-run code review
# /plan-7-code-review /workspaces/flow_squared/docs/plans/023-multi-graphs/tasks/phase-2-graphservice-impl/tasks.md
```

Expected result: **APPROVE** verdict with no CRITICAL/HIGH findings.

---

**Fix Tasks Complete**: 2026-01-13
