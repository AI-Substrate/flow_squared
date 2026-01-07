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

## Task T012 & T013: Full node_id display in text output
**Dossier Tasks**: T012, T013 | **Plan Tasks**: T012, T013
**Started**: 2026-01-07
**Status**: ✅ Complete

### What I Did

1. **T012 - RED Phase: Write failing tests**:
   - Added `TestTreeTextOutputNodeId` class in `tests/mcp_tests/test_tree_tool.py`
   - 3 tests verify full node_id in text output:
     - `test_text_output_shows_full_node_id_for_files` - expects `file:src/calculator.py`
     - `test_text_output_shows_full_node_id_for_classes` - expects `class:src/calculator.py:Calculator`
     - `test_text_output_shows_full_node_id_for_callables` - expects `callable:src/calculator.py:Calculator.add`
   - All 3 tests failed as expected (showed `📄 calculator.py` instead of `📄 file:src/calculator.py`)

2. **T013 - GREEN Phase: Implement full node_id display**:
   - Updated `_render_tree_as_text()` in `src/fs2/mcp/server.py`:
     - Line 206: Changed `name = node.get("name", "unknown")` to `node_id = node.get("node_id", "unknown")`
     - Line 211: Changed `f"{prefix}{icon} {name} [{start}-{end}]"` to use `node_id`
   - Updated `_add_tree_node_to_rich_tree()` in `src/fs2/cli/tree.py`:
     - Removed `name = node.name or node.qualified_name`
     - Changed labels to use `node.node_id` instead of `name`
   - Updated test `test_given_detail_max_when_tree_then_node_id_on_second_line` → renamed to `test_given_detail_max_when_tree_then_node_id_in_main_label`

### Evidence

```
$ UV_CACHE_DIR=.uv_cache uv run pytest tests/mcp_tests/test_tree_tool.py::TestTreeTextOutputNodeId -v
============================== 3 passed in 0.84s ===============================

$ UV_CACHE_DIR=.uv_cache uv run pytest
====================== 1674 passed, 20 skipped in 51.94s =======================
```

### Files Changed

- `/workspaces/flow_squared/src/fs2/mcp/server.py`:
  - `_render_tree_as_text()` (lines 159-227): Uses `node_id` instead of `name` in text output

- `/workspaces/flow_squared/src/fs2/cli/tree.py`:
  - `_add_tree_node_to_rich_tree()` (lines 338-347): Uses `node.node_id` in label

- `/workspaces/flow_squared/tests/mcp_tests/test_tree_tool.py`:
  - Added `TestTreeTextOutputNodeId` class (lines 802-885): 3 tests for full node_id

- `/workspaces/flow_squared/tests/unit/cli/test_tree_cli.py`:
  - Renamed test method to reflect new behavior (line 822)

### Output Format Change

**Before (just name):**
```
📄 calculator.py [1-50]
└── ○ Calculator [5-45]
    └── ƒ add [10-15]
```

**After (full node_id):**
```
📄 file:src/calculator.py [1-50]
└── ○ class:src/calculator.py:Calculator [5-45]
    └── ƒ callable:src/calculator.py:Calculator.add [10-15]
```

Agents can now copy-paste node_ids directly from text output for use with `get_node()`.

**Completed**: 2026-01-07

---

