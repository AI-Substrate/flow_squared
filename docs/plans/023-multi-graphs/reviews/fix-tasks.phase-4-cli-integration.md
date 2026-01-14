# Phase 4: CLI Integration - Fix Tasks

**Review**: [./review.phase-4-cli-integration.md](./review.phase-4-cli-integration.md)
**Created**: 2026-01-14
**Verdict**: REQUEST_CHANGES

---

## Blocking Issues (Must Fix Before Merge)

### FIX-001: Stage Untracked Files [CRITICAL]

**Issue**: 4 files created during Phase 4 implementation are not tracked in git.

**Files**:
- `src/fs2/core/dependencies.py` - Shared DI container (moved from mcp)
- `tests/unit/cli/test_main.py` - Unit tests for Phase 4
- `tests/integration/test_cli_multi_graph.py` - Integration tests for Phase 4
- `tests/integration/conftest.py` - Shared fixtures for integration tests

**Fix Command**:
```bash
cd /workspaces/flow_squared
git add src/fs2/core/dependencies.py
git add tests/unit/cli/test_main.py
git add tests/integration/test_cli_multi_graph.py
git add tests/integration/conftest.py
git status  # Verify files are staged
```

**Validation**: Files appear in `git diff --cached --stat`

---

### FIX-002: Populate Phase Footnote Stubs [CRITICAL]

**Issue**: Phase Footnote Stubs section in tasks.md is empty.

**Location**: `/workspaces/flow_squared/docs/plans/023-multi-graphs/tasks/phase-4-cli-integration/tasks.md` lines 497-503

**Current**:
```markdown
## Phase Footnote Stubs

<!-- Populated by plan-6a-update-progress during implementation -->

| Footnote | Description | FlowSpace Node IDs |
|----------|-------------|-------------------|
| | | |
```

**Fix - Replace With**:
```markdown
## Phase Footnote Stubs

<!-- Populated by plan-6a-update-progress during implementation -->

| Footnote | Description | FlowSpace Node IDs |
|----------|-------------|-------------------|
| [^11] | Phase 4 CLI multi-graph integration | `file:src/fs2/cli/main.py` - Added --graph-name option, mutual exclusivity validation |
| [^11] | Phase 4 CLI multi-graph integration | `function:src/fs2/cli/utils.py:resolve_graph_from_context` - Graph resolution utility |
| [^11] | Phase 4 CLI multi-graph integration | `file:src/fs2/cli/tree.py` - Updated composition root |
| [^11] | Phase 4 CLI multi-graph integration | `file:src/fs2/cli/search.py` - Updated composition root |
| [^11] | Phase 4 CLI multi-graph integration | `file:src/fs2/cli/get_node.py` - Updated composition root |
| [^11] | Phase 4 CLI multi-graph integration | `file:src/fs2/core/dependencies.py` - Shared DI container (created) |
| [^11] | Phase 4 CLI multi-graph integration | `file:tests/unit/cli/test_main.py` - Unit tests (created) |
| [^11] | Phase 4 CLI multi-graph integration | `file:tests/integration/test_cli_multi_graph.py` - Integration tests (created) |
```

**Validation**: Run plan-6a-update-progress or manually verify the table is populated.

---

## Advisory Issues (Recommended But Not Blocking)

### FIX-003: Add Log Anchors to Notes Column [MEDIUM]

**Issue**: Tasks T000-T006 are missing log anchors in the Notes column.

**Location**: `/workspaces/flow_squared/docs/plans/023-multi-graphs/tasks/phase-4-cli-integration/tasks.md` lines 175-182

**Fix**: Add `log#task-tNNN` references to Notes column for tasks T000-T006:

| Task | Current Notes | Add to Notes |
|------|---------------|--------------|
| T000 | Per DYK-02, DYK-05 | `log#task-t000` |
| T001 | RED: 4 tests written, all fail | `log#task-t001` |
| T002 | RED: 4 tests written, 1 fails | `log#task-t002` |
| T003 | RED: 5 tests written, all fail | `log#task-t003` |
| T004 | RED: 4 tests written, all fail | `log#task-t004` |
| T005 | RED: 4 tests written, 1 passes | `log#task-t005` |
| T006 | GREEN: 4/4 tests pass | `log#task-t006` |

---

### FIX-004: Address Scope Creep [MEDIUM]

**Issue**: 2 files were modified that are unrelated to Phase 4 multi-graphs feature.

**Files**:
- `src/fs2/core/adapters/ast_parser_impl.py` - AST parser anonymous node ID improvements
- `src/fs2/core/services/embedding/embedding_service.py` - Smart content placeholder detection fix

**Options**:

1. **Split into separate branch** (Recommended):
   ```bash
   # Create new branch for unrelated changes
   git checkout -b fix/ast-parser-node-ids
   git cherry-pick <commit-with-ast-changes>

   git checkout -b fix/embedding-placeholder-detection
   git cherry-pick <commit-with-embedding-changes>
   ```

2. **Document as incidental fixes** in commit message:
   ```
   feat(cli): Add --graph-name option for multi-graph CLI support

   Phase 4 of multi-graphs feature:
   - Add --graph-name CLI option with mutual exclusivity validation
   - Create resolve_graph_from_context() utility
   - Update tree/search/get-node composition roots

   Incidental fixes (discovered during implementation):
   - Fix AST parser anonymous node ID generation
   - Fix embedding service placeholder detection
   ```

---

### FIX-005: Strengthen Test Assertions [LOW]

**Issue**: Some Phase 4 tests use existence/callable checks instead of behavioral assertions.

**Location**: `tests/unit/cli/test_main.py::TestResolveGraphFromContext`

**Current Pattern**:
```python
def test_resolve_with_graph_name_uses_graphservice(self):
    # ... setup ...
    assert callable(resolve_graph_from_context)  # Existence check
```

**Improved Pattern**:
```python
def test_resolve_with_graph_name_uses_graphservice(self):
    # ... setup ...
    config, store = resolve_graph_from_context(ctx)
    assert isinstance(config, ConfigurationService)
    assert isinstance(store, GraphStore)
    assert store.get_all_nodes()  # Actually has content
```

**Note**: This is a quality improvement, not a correctness issue. Tests currently pass.

---

## Validation Checklist

After applying fixes, run:

```bash
# Verify git status
git status  # Should show staged files, no untracked Phase 4 files

# Run Phase 4 tests
uv run pytest tests/unit/cli/test_main.py tests/integration/test_cli_multi_graph.py -v

# Run regression tests
uv run pytest tests/mcp_tests/ -v

# Verify imports
uv run python -c "from fs2.core.dependencies import get_graph_service; print('OK')"
```

---

*Generated by plan-7-code-review on 2026-01-14*
