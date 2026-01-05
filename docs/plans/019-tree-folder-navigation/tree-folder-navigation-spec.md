# Hierarchical Tree Navigation with Virtual Folders

**Mode**: Simple

ℹ️ *Research conducted inline during workshop session. No formal research-dossier.md.*

## Summary

**WHAT**: Enable hierarchical codebase exploration through the `tree` command by computing virtual folder nodes from file paths and allowing drill-down navigation using folder paths or node IDs as starting points.

**WHY**: Agents currently get overwhelmed when exploring codebases. Running `tree --depth 1` produces 400KB+ of output because it shows all files grouped into deeply nested virtual folder hierarchies. Agents need a progressive disclosure pattern: see top-level folders first, then drill into specific areas, then into files, then into symbols. Each step should produce minimal, actionable output where every item is directly usable as input to the next command.

## Goals

1. **Top-level overview**: `tree --depth 1` shows only root-level folders (e.g., `docs/`, `src/`, `tests/`, `scripts/`)
2. **Folder drill-down**: `tree src/fs2/ --depth 1` shows immediate children (subfolders and files) of that path
3. **File drill-down**: `tree file:src/fs2/cli/tree.py --depth 1` shows symbols (functions, classes) in that file
4. **Symbol drill-down**: `tree class:...:TreeService --depth 1` shows methods of that class
5. **Copy-paste workflow**: Every real node displayed includes its full node_id, directly usable as input to `tree` or `get-node`
6. **Agent guidance**: MCP server docstrings updated to teach agents the exploration workflow
7. **Minimal output**: Each depth level produces compact, scannable output - no context explosion

## Non-Goals

- **Real folder nodes in graph**: Folders remain virtual (computed at display time), not persisted in the graph
- **Folder-level search**: Search continues to operate on real nodes (files, classes, callables) only
- **Backward compatibility**: Product not shipped; existing behavior can change freely
- **New CLI flags**: No new flags needed - existing `--depth` and pattern arguments suffice

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=2, I=0, D=0, N=1, F=0, T=1
  - S=2: Multiple files (tree.py display, tree_service.py filtering, MCP server.py docs, multiple test files)
  - I=0: Internal only, no external dependencies
  - D=0: No schema/data changes (folders are computed, not stored)
  - N=1: Some ambiguity in exact folder computation logic
  - F=0: Standard performance requirements
  - T=1: Integration tests needed for drill-down workflow
- **Confidence**: 0.85
- **Assumptions**:
  - Virtual folder computation from file paths is straightforward
  - Existing pattern matching can handle path prefixes
  - No performance issues with on-the-fly folder computation
- **Dependencies**: None
- **Risks**:
  - Edge cases with deeply nested paths
  - Root-level files (no parent folder) need handling
- **Phases**:
  1. Virtual folder computation and depth-limited display
  2. Path-based filtering for folder drill-down
  3. MCP documentation and agent workflow guidance

## Acceptance Criteria

### AC1: Top-Level Folder Overview
**Given** a scanned codebase with files in `docs/`, `src/`, `tests/`, `scripts/`
**When** running `fs2 tree --depth 1`
**Then** output shows only top-level folder names:
```
Code Structure
├── 📁 docs/
├── 📁 scripts/
├── 📁 src/
└── 📁 tests/
```

### AC2: Folder Drill-Down
**Given** folder `src/fs2/` contains subfolders `cli/`, `config/`, `core/`, `mcp/` and file `__init__.py`
**When** running `fs2 tree src/fs2/ --depth 1`
**Then** output shows immediate children with full node_ids for files:
```
src/fs2/
├── 📁 cli/
├── 📁 config/
├── 📁 core/
├── 📁 mcp/
└── 📄 file:src/fs2/__init__.py [1-3]
```

### AC3: File Drill-Down via Node ID
**Given** file `src/fs2/cli/tree.py` contains functions `tree`, `_display_tree`, etc.
**When** running `fs2 tree file:src/fs2/cli/tree.py --depth 1`
**Then** output shows symbols with full node_ids:
```
tree.py
├── ƒ callable:src/fs2/cli/tree.py:_tree_node_to_dict [50-98]
├── ƒ callable:src/fs2/cli/tree.py:tree [101-239]
├── ƒ callable:src/fs2/cli/tree.py:_display_tree [242-308]
└── ƒ callable:src/fs2/cli/tree.py:_add_tree_node_to_rich_tree [311-362]
```

### AC4: Class Drill-Down via Node ID
**Given** class `TreeService` contains methods `__init__`, `build_tree`, etc.
**When** running `fs2 tree class:src/fs2/core/services/tree_service.py:TreeService --depth 1`
**Then** output shows methods with full node_ids

### AC5: Depth 2 Shows Two Levels
**Given** folder `src/fs2/` with subfolders containing files
**When** running `fs2 tree src/fs2/ --depth 2`
**Then** output shows folders AND their immediate contents (files), with `hidden_children_count` for files with symbols

### AC6: Copy-Paste Workflow
**Given** any tree output
**When** user copies a displayed node_id (e.g., `file:src/fs2/cli/tree.py`)
**Then** that exact string works as input to `fs2 tree <node_id>` or `fs2 get-node <node_id>`

### AC7: MCP Documentation Guides Agents
**Given** an agent discovering the `tree` MCP tool
**When** reading the tool's docstring/description
**Then** it explains the drill-down workflow:
- Start with `tree(pattern=".", max_depth=1)` for overview
- Use folder paths to drill into directories
- Use node_ids to drill into files/classes
- Use `get_node()` to retrieve full source

### AC8: Root-Level Files Handled
**Given** a file at repository root (e.g., `pyproject.toml`)
**When** running `fs2 tree --depth 1`
**Then** root-level files appear alongside top-level folders:
```
Code Structure
├── 📁 docs/
├── 📁 src/
├── 📄 file:pyproject.toml [1-150]
└── 📄 file:README.md [1-50]
```

### AC9: Empty Folders Not Shown
**Given** a path prefix with no files (e.g., empty `__pycache__/` excluded by scan)
**When** running `fs2 tree --depth 1`
**Then** that folder does not appear (folders are computed from actual file nodes)

### AC10: Nested Path Filtering
**Given** deeply nested structure `src/fs2/core/services/`
**When** running `fs2 tree src/fs2/core/ --depth 1`
**Then** output shows only immediate children of that path:
```
src/fs2/core/
├── 📁 adapters/
├── 📁 models/
├── 📁 repos/
├── 📁 services/
└── 📄 file:src/fs2/core/__init__.py [1-5]
```

## Risks & Assumptions

### Risks
1. **Performance with large codebases**: Computing folder hierarchy on-the-fly may be slow for very large graphs. Mitigation: Profile and optimize if needed; consider caching.
2. **Path edge cases**: Windows paths, symlinks, or unusual characters could cause issues. Mitigation: Normalize paths consistently.
3. **Ambiguous patterns**: User input `src/fs2` (no trailing slash) vs `src/fs2/` - should both work? Mitigation: Normalize trailing slashes.

### Assumptions
1. All file node_ids follow format `file:path/to/file.ext`
2. Folder hierarchy can be derived from file paths alone (no need for actual folder nodes)
3. Agents will adopt the drill-down workflow when guided by documentation
4. Existing `--depth` semantics (1=root only, 2=root+children) remain correct

## Testing Strategy

- **Approach**: Full TDD
- **Rationale**: Extensive tree tests already exist (102 tests); maintain comprehensive coverage through refactoring
- **Focus Areas**:
  - Virtual folder computation from file paths
  - Depth limiting with folder hierarchy
  - Path-based filtering for folder drill-down
  - Node ID display format in output
- **Excluded**: N/A - full coverage expected
- **Mock Usage**: Targeted fakes (per constitution P4 - "Fakes over Mocks")
  - Use existing `FakeGraphStore`, `FakeConfigurationService`
  - Use helper factories: `make_file_node()`, `make_class_node()`, `make_method_node()`
  - CLI integration tests use real filesystem via `scanned_project` fixture
  - No `unittest.mock` or patching

## Documentation Strategy

- **Location**: Hybrid (docs/how/user/ + src/fs2/docs/)
- **Rationale**: MCP tool changes require bundled doc updates per Rule R6.4; agents need exploration workflow guidance
- **Content Split**:
  - `docs/how/user/cli.md`: Add folder drill-down examples, depth workflow
  - `src/fs2/docs/agents.md`: Update exploration workflow with progressive disclosure pattern
  - `src/fs2/mcp/server.py`: Docstrings already accurate (depth 1 = root only)
  - `src/fs2/docs/` must mirror `docs/how/user/` changes (R6.4)
- **Target Audience**: AI agents (primary), CLI users (secondary)
- **Maintenance**: Bundled docs must sync when MCP tools change

## Open Questions

1. ~~**Trailing slash handling**~~: **RESOLVED** - `/` is REQUIRED for folder mode (no normalization)
2. ~~**Hidden children count for folders**~~: **RESOLVED** - Show item counts (e.g., `📁 src/ (89 files)`)
3. ~~**Input mode detection**~~: **RESOLVED** - Three modes based on syntax:

   | Input | Detection | Mode |
   |-------|-----------|------|
   | `src/` or `src/fs2/` | Contains `/` | Folder mode |
   | `file:...` or `class:...` | Category prefix `:` | Node ID mode |
   | `Calculator` or `src` | Otherwise | Pattern match |

   **Rule**: Slash (`/`) is required for folder mode. This is unambiguous and easy to implement.
   MCP documentation must be explicit: "Use trailing `/` for folder navigation, e.g., `src/fs2/`"

## ADR Seeds (Optional)

### Decision: Virtual vs Real Folder Nodes

**Decision Drivers**:
- Minimize graph storage and scan complexity
- Enable folder navigation without schema changes
- Keep folder display logic in presentation layer

**Candidate Alternatives**:
- A: Virtual folders (computed at display time from file paths)
- B: Real folder nodes persisted in graph during scan
- C: Hybrid (cache computed folders in memory)

**Recommendation**: Option A - simplest, no graph changes, sufficient for use case

---

## Clarifications

### Session 2026-01-04

| Q# | Topic | Answer |
|----|-------|--------|
| Q1 | Workflow Mode | **Simple** - Single-phase, quick implementation |
| Q2 | Testing Approach | **Full TDD** - Maintain comprehensive coverage through refactoring |
| Q3 | Mock Usage | **Targeted fakes** - Use existing FakeGraphStore, FakeConfigurationService per P4 |
| Q4 | Documentation | **Hybrid** - Update docs/how/user/ + src/fs2/docs/ per R6.4 |
| Q5 | Trailing slash | **Required** - `/` is required for folder mode |
| Q6 | Folder counts | **Show counts** - e.g., `📁 src/ (89 files)` |
| Q7 | Input modes | **Three modes**: `/` = folder, `:` = node ID, otherwise = pattern match |

**Coverage Summary**:
- **Resolved**: Mode, Testing, Mocks, Docs, Input detection, Folder display
- **Deferred**: None
- **Outstanding**: None

---

**Spec Location**: `docs/plans/019-tree-folder-navigation/tree-folder-navigation-spec.md`
**Branch**: main
**Next Step**: Run `/plan-3-architect` to generate implementation plan
