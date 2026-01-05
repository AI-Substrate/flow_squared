# Hierarchical Tree Navigation with Virtual Folders - Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-01-04
**Spec**: [./tree-folder-navigation-spec.md](./tree-folder-navigation-spec.md)
**Status**: READY

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Critical Research Findings](#critical-research-findings)
3. [Implementation](#implementation)
4. [Change Footnotes Ledger](#change-footnotes-ledger)

## Executive Summary

**Problem**: Agents get overwhelmed exploring codebases. `tree --depth 1` produces 400KB+ output because it shows all files grouped into deeply nested folder hierarchies instead of showing only top-level folders.

**Solution**: Implement hierarchical folder navigation with three input modes:
- **Folder mode** (contains `/`): Show virtual folder contents at specified depth
- **Node ID mode** (has `:` prefix): Show children of specific node
- **Pattern match** (otherwise): Search node_ids as before

**Expected Outcome**: Progressive disclosure pattern where each command produces minimal, actionable output. Agents can drill down: folders → files → symbols → methods.

## Critical Research Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | **Virtual folder grouping exists** in `_display_tree()` (lines 258-273) but groups ALL files by parent path, not hierarchically | Refactor to compute folder hierarchy with depth limiting |
| 02 | Critical | **Pattern matching priority**: exact → glob → substring. No folder mode detection | Add folder mode detection: if pattern contains `/`, treat as folder filter |
| 03 | Critical | **TreeService uses parent-child edges**, not folder hierarchy. Folders must be virtual (presentation layer only) | Compute folders in `_display_tree()`, not in TreeService |
| 04 | Critical | **Node ID format**: `{category}:{file_path}:{qualified_name}`. Extract file_path for folder computation | Parse node_id to extract path, then compute parent folders |
| 05 | High | **Folder extraction functions exist** in `search_result_meta.py` (lines 27-116): `extract_folder()`, `_extract_second_level_folder()` | Reuse or adapt these for tree folder computation |
| 06 | High | **MCP and CLI share TreeService** but have duplicated `_tree_node_to_dict()` functions | Keep duplication (per architecture); ensure both updated consistently |
| 07 | High | **Depth semantics fixed**: `max_depth=1` = root only, `max_depth=2` = root + children | Depth limiting already correct; apply to virtual folders |
| 08 | High | **TreeNode is immutable** (frozen dataclass with tuple children). Cannot mutate in place | Build new folder hierarchy structure before rendering |
| 09 | High | **Root bucket algorithm** removes children when ancestor matches pattern | Folder filtering must work with root bucket logic |
| 10 | Medium | **CATEGORY_ICONS** mapping exists (lines 37-47). Need "folder" → "📁" | Add folder icon to mapping |
| 11 | Medium | **hidden_children_count** field shows depth-limited children. Use for folder counts | Folders should show item counts like `📁 src/ (89 files)` |
| 12 | Medium | **Test fixtures** use `FakeGraphStore` with `make_file_node()`, `make_class_node()` helpers | Follow same pattern for folder navigation tests |
| 13 | Medium | **Documentation gap**: CLI help and MCP docstrings not unified | Update both to document folder navigation workflow |
| 14 | Low | **Empty graph handling**: returns [] immediately, no error | No change needed; behavior correct |
| 15 | Low | **Root-level files**: `parent_node_id=None` makes them root candidates | Handle in folder computation (files at root level) |

## Implementation

**Objective**: Enable hierarchical folder navigation with virtual folders, three input modes, and progressive disclosure.

**Testing Approach**: Full TDD
**Mock Usage**: Targeted fakes (FakeGraphStore, FakeConfigurationService per P4)

### Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Notes |
|--------|-----|------|----|------|--------------|------------------|------------|-------|
| [ ] | T001 | Add folder icon to CATEGORY_ICONS | 1 | Setup | -- | /workspaces/flow_squared/src/fs2/cli/tree.py | Icon "📁" mapped to "folder" category | Line ~40 |
| [ ] | T002 | Write tests for input mode detection (folder/node_id/pattern) | 2 | Test | -- | /workspaces/flow_squared/tests/unit/cli/test_tree_cli.py | Tests cover: `src/` → folder, `file:...` → node_id, `Calculator` → pattern | New test class TestInputModeDetection |
| [ ] | T003 | Implement `_detect_input_mode()` function | 2 | Core | T002 | /workspaces/flow_squared/src/fs2/cli/tree.py | Returns "folder" if contains `/`, "node_id" if contains `:`, else "pattern" | Add helper function |
| [ ] | T004 | Write tests for folder hierarchy computation | 3 | Test | T001 | /workspaces/flow_squared/tests/unit/cli/test_tree_cli.py | Tests: compute top-level folders from file paths, nested folders, root files | New test class TestFolderComputation |
| [ ] | T005 | Implement `_compute_folder_hierarchy()` function | 3 | Core | T004 | /workspaces/flow_squared/src/fs2/cli/tree.py | Given file nodes, returns folder tree with depth limiting and item counts | Core algorithm |
| [ ] | T006 | Write tests for folder filtering (path prefix mode) | 2 | Test | T003 | /workspaces/flow_squared/tests/unit/cli/test_tree_cli.py | Tests: `src/fs2/` filters to files in that folder only | Test folder drill-down |
| [ ] | T007 | Modify TreeService pattern matching for folder mode | 2 | Core | T006 | /workspaces/flow_squared/src/fs2/core/services/tree_service.py | Folder patterns (with `/`) match file paths as prefix filter | Modify `_filter_nodes()` |
| [ ] | T008 | Write tests for depth-limited folder display | 2 | Test | T005 | /workspaces/flow_squared/tests/unit/cli/test_tree_cli.py | Tests: depth=1 shows folders only, depth=2 shows folders+files | Verify AC1, AC2 |
| [ ] | T009 | Refactor `_display_tree()` to use folder hierarchy | 3 | Core | T005,T007 | /workspaces/flow_squared/src/fs2/cli/tree.py | Replace flat grouping with hierarchical folder tree | Major refactor of display logic |
| [ ] | T010 | Write tests for folder item counts display | 2 | Test | T009 | /workspaces/flow_squared/tests/unit/cli/test_tree_cli.py | Tests: folders show `(N files)` count | Verify AC6 folder counts |
| [ ] | T011 | Implement folder item counts in display | 2 | Core | T010 | /workspaces/flow_squared/src/fs2/cli/tree.py | Show `📁 src/ (89 files)` format | In `_add_tree_node_to_rich_tree()` |
| [ ] | T012 | Write tests for full node_id display | 2 | Test | T009 | /workspaces/flow_squared/tests/unit/cli/test_tree_cli.py | Tests: files show `file:path/to/file.py [1-50]` | Verify AC6 copy-paste |
| [ ] | T013 | Ensure node_ids displayed for all real nodes | 2 | Core | T012 | /workspaces/flow_squared/src/fs2/cli/tree.py | Files, classes, callables show full node_id | Modify node label formatting |
| [ ] | T014 | Write MCP tree tool tests for folder mode | 2 | Test | T007 | /workspaces/flow_squared/tests/mcp_tests/test_tree_tool.py | Tests: folder patterns work via MCP, JSON output correct | New test class TestFolderModeViaMap |
| [ ] | T015 | Update MCP tree() docstring with folder workflow | 2 | Docs | T009 | /workspaces/flow_squared/src/fs2/mcp/server.py | Docstring explains: use `/` for folders, drill-down workflow | Lines 206-254 |
| [ ] | T016 | Update `_tree_node_to_dict()` for folder nodes in MCP | 2 | Core | T015 | /workspaces/flow_squared/src/fs2/mcp/server.py | Handle folder nodes (virtual) in JSON conversion if needed | May not need changes if folders are display-only |
| [ ] | T017 | Update docs/how/user/cli.md with folder examples | 2 | Docs | T009 | /workspaces/flow_squared/docs/how/user/cli.md | Add section on folder drill-down workflow | Lines 140-233 tree section |
| [ ] | T018 | Update src/fs2/docs/agents.md with exploration workflow | 2 | Docs | T015 | /workspaces/flow_squared/src/fs2/docs/agents.md | Add progressive disclosure pattern examples | Agent guidance |
| [ ] | T019 | Run full test suite and verify all 10 ACs | 2 | Test | T001-T018 | All test files | All 102+ tree tests pass, new tests pass, ACs verified | Final validation |
| [ ] | T020 | Verify CLI and MCP produce consistent output | 2 | Test | T019 | Manual testing | Same folder structure shown via CLI and MCP | Integration check |

### Acceptance Criteria

- [ ] **AC1**: `tree --depth 1` shows only top-level folders (docs/, src/, tests/, scripts/)
- [ ] **AC2**: `tree src/fs2/ --depth 1` shows immediate children (subfolders + files with node_ids)
- [ ] **AC3**: `tree file:src/fs2/cli/tree.py --depth 1` shows symbols with full node_ids
- [ ] **AC4**: `tree class:...:TreeService --depth 1` shows methods with full node_ids
- [ ] **AC5**: `tree src/fs2/ --depth 2` shows folders AND their contents
- [ ] **AC6**: Every real node displays full node_id (copy-paste workflow works)
- [ ] **AC7**: MCP tree tool docstring explains drill-down workflow
- [ ] **AC8**: Root-level files appear alongside top-level folders at depth 1
- [ ] **AC9**: Empty folders (no files) not shown
- [ ] **AC10**: `tree src/fs2/core/ --depth 1` shows only immediate children of that path

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Display refactor breaks existing tests | Medium | High | Run tests after each change, fix incrementally |
| Performance with large codebases | Low | Medium | Folder computation is O(n) where n=files; acceptable |
| MCP/CLI output inconsistency | Low | Medium | Test both paths with same inputs |
| Edge cases with unusual paths | Low | Low | Normalize paths consistently |

## Change Footnotes Ledger

[^1]: [To be added during implementation via plan-6a]
[^2]: [To be added during implementation via plan-6a]

---

**Next steps:**
- **Ready to implement**: `/plan-6-implement-phase --plan "docs/plans/019-tree-folder-navigation/tree-folder-navigation-plan.md"`
- **Optional validation**: `/plan-4-complete-the-plan` (recommended for CS-3 tasks)
- **Optional task expansion**: `/plan-5-phase-tasks-and-brief` (if you want a separate dossier)
