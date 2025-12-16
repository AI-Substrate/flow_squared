# Phase 4: Graph Storage Repository - Fix Tasks (Advisory)

**Review**: [./review.phase-4.md](./review.phase-4.md)
**Verdict**: APPROVE WITH ADVISORIES
**Priority**: These are recommended improvements, not blocking issues

---

## Advisory Fix Tasks

### FT-001: Add Node Existence Validation to FakeGraphStore.add_edge()

**Severity**: MEDIUM
**File**: `/workspaces/flow_squared/src/fs2/core/repos/graph_store_fake.py`
**Lines**: 105-127
**Finding**: CORR-001

**Issue**: FakeGraphStore.add_edge() does not validate that parent_id and child_id nodes exist before creating the edge, violating the GraphStore ABC contract.

**Current Code**:
```python
def add_edge(self, parent_id: str, child_id: str) -> None:
    self._call_history.append({
        "method": "add_edge",
        "args": (parent_id, child_id),
        "kwargs": {},
    })

    if "add_edge" in self.simulate_error_for:
        raise GraphStoreError("Simulated add_edge error")

    if parent_id not in self._edges:
        self._edges[parent_id] = set()
    self._edges[parent_id].add(child_id)
    self._reverse_edges[child_id] = parent_id
```

**Fix**: Add validation matching NetworkXGraphStore behavior:
```python
def add_edge(self, parent_id: str, child_id: str) -> None:
    self._call_history.append({
        "method": "add_edge",
        "args": (parent_id, child_id),
        "kwargs": {},
    })

    if "add_edge" in self.simulate_error_for:
        raise GraphStoreError("Simulated add_edge error")

    # Validate nodes exist (match ABC contract)
    if parent_id not in self._nodes:
        raise GraphStoreError(
            f"Parent node not found: {parent_id}. "
            f"Add the node before creating edges."
        )
    if child_id not in self._nodes:
        raise GraphStoreError(
            f"Child node not found: {child_id}. "
            f"Add the node before creating edges."
        )

    if parent_id not in self._edges:
        self._edges[parent_id] = set()
    self._edges[parent_id].add(child_id)
    self._reverse_edges[child_id] = parent_id
```

**Test**: Existing tests should still pass. Consider adding:
```python
def test_fake_graph_store_add_edge_raises_for_missing_parent():
    """Verify add_edge raises GraphStoreError for missing parent node."""
    config = FakeConfigurationService(ScanConfig())
    store = FakeGraphStore(config)
    child = make_file_node()
    store.add_node(child)

    with pytest.raises(GraphStoreError) as exc_info:
        store.add_edge("nonexistent", child.node_id)

    assert "Parent node not found" in str(exc_info.value)
```

---

### FT-002: Add Debug Logging to add_node()

**Severity**: HIGH
**File**: `/workspaces/flow_squared/src/fs2/core/repos/graph_store_impl.py`
**Lines**: 132-142
**Finding**: OBS-002

**Issue**: Node additions/updates are silent, making it impossible to audit graph construction.

**Current Code**:
```python
def add_node(self, node: CodeNode) -> None:
    # Store CodeNode directly as node data
    self._graph.add_node(node.node_id, data=node)
```

**Fix**:
```python
def add_node(self, node: CodeNode) -> None:
    # Store CodeNode directly as node data
    self._graph.add_node(node.node_id, data=node)
    logger.debug("Node added: %s (category=%s)", node.node_id, node.category)
```

---

### FT-003: Add Debug Logging to add_edge()

**Severity**: HIGH
**File**: `/workspaces/flow_squared/src/fs2/core/repos/graph_store_impl.py`
**Lines**: 144-169
**Finding**: OBS-001

**Issue**: Successful edge additions are silent.

**Fix**: Add after line 169:
```python
def add_edge(self, parent_id: str, child_id: str) -> None:
    # ... existing validation code ...

    self._graph.add_edge(parent_id, child_id)
    logger.debug("Edge added: %s -> %s", parent_id, child_id)  # NEW
```

---

### FT-004: Restrict NetworkX Whitelist (Optional)

**Severity**: MEDIUM
**File**: `/workspaces/flow_squared/src/fs2/core/repos/graph_store_impl.py`
**Lines**: 40-49
**Finding**: SEC-001

**Issue**: Broad 'networkx' entry allows any networkx submodule.

**Current Code**:
```python
ALLOWED_MODULES = frozenset({
    "builtins",
    "collections",
    "datetime",
    "pathlib",
    "networkx",  # Too broad
    "networkx.classes.digraph",
    "networkx.classes.reportviews",
    "fs2.core.models.code_node",
})
```

**Fix**: Remove broad entry, keep specific submodules:
```python
ALLOWED_MODULES = frozenset({
    "builtins",
    "collections",
    "datetime",
    "pathlib",
    # Specific networkx submodules only
    "networkx.classes.digraph",      # DiGraph type
    "networkx.classes.reportviews",  # Successor/predecessor views
    "networkx.classes.ordered",      # For older networkx versions
    "fs2.core.models.code_node",
})
```

**Test**: Run existing tests to verify no breakage. If tests fail, add the required networkx submodule to whitelist.

---

### FT-005: Optimize get_children() (Optional)

**Severity**: MEDIUM
**File**: `/workspaces/flow_squared/src/fs2/core/repos/graph_store_impl.py`
**Lines**: 184-201
**Finding**: PERF-001

**Issue**: N+1 pattern calls get_node() for each child.

**Current Code**:
```python
def get_children(self, node_id: str) -> list[CodeNode]:
    if node_id not in self._graph:
        return []

    children = []
    for child_id in self._graph.successors(node_id):
        node = self.get_node(child_id)  # N+1 calls
        if node is not None:
            children.append(node)
    return children
```

**Fix**: Direct dict access:
```python
def get_children(self, node_id: str) -> list[CodeNode]:
    if node_id not in self._graph:
        return []

    return [
        self._graph.nodes[child_id]["data"]
        for child_id in self._graph.successors(node_id)
        if child_id in self._graph and "data" in self._graph.nodes[child_id]
    ]
```

---

## Testing After Fixes

```bash
# Run Phase 4 tests after applying fixes
uv run pytest tests/unit/repos/test_graph_store*.py -v

# Run full suite to catch any regressions
uv run pytest tests/unit/ -v

# Lint check
uv run ruff check src/fs2/core/repos/
```

---

## Summary

| Fix | Severity | Estimated Effort | Impact |
|-----|----------|------------------|--------|
| FT-001 | MEDIUM | 5 min | LSP compliance |
| FT-002 | HIGH | 2 min | Observability |
| FT-003 | HIGH | 2 min | Observability |
| FT-004 | MEDIUM | 3 min | Security hardening |
| FT-005 | MEDIUM | 5 min | Performance |

**Total estimated effort**: ~17 minutes

These are advisory improvements. The phase may be merged without these fixes if time-constrained, but they are recommended for production readiness.

---

*Fix tasks generated by Claude Opus 4.5 on 2025-12-16*
