# Phase 2: Virtual Folder Hierarchy - Execution Log

**Plan**: [../../tree-folder-navigation-plan.md](../../tree-folder-navigation-plan.md)
**Dossier**: [./tasks.md](./tasks.md)
**Started**: 2026-01-06

---

## Task T005: Implement _compute_folder_hierarchy() in TreeService
**Dossier Task**: T005 | **Plan Task**: T005
**Started**: 2026-01-06
**Status**: ✅ Complete

### What I Did

1. **RED Phase - Strengthened tests per DD2**:
   - Rewrote TestFolderHierarchyComputation class with 6 specific tests
   - Added `make_folder_node()` helper function for test assertions
   - Tests verify DD1-DD5: synthetic CodeNode with category="folder", node_id with trailing slash, folders sorted before files
   - All 6 tests failed as expected (0 passed)

2. **GREEN Phase - Implemented _compute_folder_hierarchy()**:
   - Added `_create_folder_node()` module-level helper function
   - Added `_compute_folder_hierarchy()` method to TreeService
   - Added `_build_folder_tree_nodes()` recursive helper for depth-limited traversal
   - Added `_count_folder_items()` helper for hidden children count (files only, per spec)
   - Modified `build_tree()` to call folder hierarchy when `pattern="."` and `max_depth > 0`

3. **Initial implementation counted folders + files in hidden_children_count**, but spec says `📁 src/ (89 files)` - corrected to count files only.

### Evidence

```
$ UV_CACHE_DIR=.uv_cache uv run pytest tests/unit/services/test_tree_service.py::TestFolderHierarchyComputation -v
============================== 6 passed in 0.59s ===============================

$ UV_CACHE_DIR=.uv_cache uv run pytest tests/unit/services/test_tree_service.py -v
============================== 32 passed in 0.65s ==============================
```

### Files Changed

- `/workspaces/flow_squared/src/fs2/core/services/tree_service.py`:
  - Added `_create_folder_node()` function (lines 44-79)
  - Added `_compute_folder_hierarchy()` method (lines 397-450)
  - Added `_build_folder_tree_nodes()` method (lines 452-525)
  - Added `_count_folder_items()` method (lines 527-541)
  - Modified `build_tree()` to call folder hierarchy (lines 188-191)

- `/workspaces/flow_squared/tests/unit/services/test_tree_service.py`:
  - Added `make_folder_node()` helper (lines 56-85)
  - Rewrote TestFolderHierarchyComputation with 6 strengthened tests (lines 596-786)

### Discoveries

- **gotcha**: Initial implementation counted folders in `hidden_children_count`, but spec shows `(89 files)` format. Corrected to count files only.
- **insight**: The key design is building a nested dict structure from file paths, then converting to TreeNodes with depth limiting. This cleanly separates folder computation from tree building.

### Additional Test Updates Required

The following tests needed updates to accommodate the new folder hierarchy behavior:

1. **`tests/mcp_tests/test_mcp_integration.py`**:
   - `test_mcp_subprocess_tree_returns_nodes`: Added `format="json"` and adapted to new response format
   - `test_mcp_subprocess_get_node`: Same update for tree call

2. **`tests/unit/cli/test_tree_cli.py`**:
   - `test_given_depth_one_when_tree_then_shows_files_only` → renamed to `test_given_depth_one_when_tree_then_shows_top_level_folders`
   - `test_given_depth_two_when_tree_then_shows_two_levels` → renamed to `test_given_depth_two_when_tree_then_shows_folders_and_files`
   - Both tests updated to expect folder icons (📁) instead of file icons (📄) per Phase 2 behavior

### Final Test Results
```
====================== 1671 passed, 20 skipped in 55.50s =======================
```

**Completed**: 2026-01-06

---

