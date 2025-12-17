# fs2 tree Command

**Created**: 2025-12-17
**Status**: Draft
**Mode**: Full

> 📚 This specification incorporates findings from in-session research (CLI architecture, graph store, CodeNode model, Rich Tree patterns, path matching, testing patterns).

---

## Summary

**WHAT**: A new CLI command `fs2 tree` that displays code structure from the persisted graph as a hierarchical tree, filtered by path or pattern, showing the file → class → method (or equivalent) relationships with line ranges and FlowSpace-compatible node IDs.

**WHY**: Users need to quickly visualize and navigate code structure without reading source files. This enables:
- Understanding unfamiliar codebases at a glance
- Verifying scan results match expectations
- Getting node IDs for use with FlowSpace MCP tools
- Exploring code hierarchy before making changes

---

## Goals

1. **Display code hierarchy**: Show file → type → callable relationships in tree format
2. **Filter by path/pattern**: Support glob patterns (`*.py`, `src/core/*`) and path prefixes
3. **Show node metadata**: Include line ranges `[start-end]` and node types (class, function, etc.)
4. **Expose node IDs**: Display FlowSpace-compatible node IDs for downstream tool usage
5. **Support multiple languages**: Work with any language the parser supports (Python, TypeScript, Dockerfile, Markdown, YAML, etc.)
6. **Configurable detail levels**: `--detail min` (essential) vs `--detail max` (everything) as standard options
7. **Clear data file messaging**: Show file-level only for YAML/JSON/TOML with guidance to use `jq`/`yq`

---

## Non-Goals

1. **Real-time file watching**: Tree shows graph state at invocation time, not live updates
2. **Code content display**: Tree shows structure, not source code (use `Read` for content)
3. **Graph modification**: Tree is read-only; cannot add/remove nodes
4. **Cross-file relationships**: Shows containment hierarchy only, not call graphs or imports
5. **Interactive navigation**: Output is static text, not a TUI browser
6. **Data file structure**: YAML/JSON/TOML internal structure not available (tree-sitter limitation); use `jq`/`yq` instead

---

## Complexity

**Score**: CS-2 (small)

**Breakdown**:
| Factor | Score | Rationale |
|--------|-------|-----------|
| Surface Area (S) | 1 | ~3 new files: `tree.py`, `test_tree_cli.py`, update `main.py` |
| Integration (I) | 0 | Uses existing graph store, no external deps |
| Data/State (D) | 0 | Read-only from existing graph, no schema changes |
| Novelty (N) | 0 | Well-specified from research, clear requirements |
| Non-Functional (F) | 0 | Standard CLI performance, no security concerns |
| Testing (T) | 1 | Unit + integration tests needed |

**Total**: P = 2 → **CS-2**

**Confidence**: 0.85

**Assumptions**:
- Graph store `get_all_nodes()` and `get_children()` perform adequately for typical codebases (<10K nodes)
- Rich Tree handles deep hierarchies without performance issues
- File type detection can use existing `language` field from CodeNode

**Dependencies**:
- Phase 6 CLI infrastructure (scan, init commands) - ✅ Complete
- NetworkXGraphStore with persistence - ✅ Complete
- CodeNode model with hierarchy support - ✅ Complete

**Risks**:
- Large codebases may produce overwhelming output → mitigate with `--depth` limit
- Some languages (YAML, JSON) have deep nesting unsuited for code tree → limit traversal
- Graph loading for large codebases (>10K nodes) may be slow → mitigate with loading feedback (AC16) and warning (AC17); consider filtered graph queries in future optimization

**Phases**:
1. Phase 1: Core tree command with path filtering
2. Phase 2: Detail levels and depth limiting
3. Phase 3: File-type-specific handling (data files)

---

## Acceptance Criteria

### AC1: Basic Tree Display
**Given** a scanned codebase with the graph persisted
**When** `fs2 tree` is run without arguments
**Then** display all files and their code structure in tree format

### AC2: Path Filtering
**Given** a scanned codebase
**When** `fs2 tree src/core` is run
**Then** display only nodes whose paths contain "src/core"

### AC3: Glob Pattern Filtering
**Given** a scanned codebase
**When** `fs2 tree "test_*.py"` is run
**Then** display only files matching the glob pattern and their contents

### AC4: Detail Level - Min (Default)
**Given** a scanned codebase
**When** `fs2 tree --detail min` (or default) is run
**Then** display: icon, name, type, line range
**Example output**:
```
📄 calculator.py
├── 📦 Calculator [15-45]
│   ├── ƒ add [20-25]
│   └── ƒ subtract [27-32]
```

### AC5: Detail Level - Max
**Given** a scanned codebase
**When** `fs2 tree --detail max` is run
**Then** display: icon, name, line range, signature (inline), and node ID (on second line)
**Example output**:
```
📄 calculator.py [1-50]
        file:calculator.py
└── 📦 Calculator [15-45] class Calculator:
        type:calculator.py:Calculator
    ├── ƒ add [20-25] def add(self, a: int, b: int) -> int:
    │       callable:calculator.py:Calculator.add
    └── ƒ subtract [27-32] def subtract(self, a: int, b: int) -> int:
            callable:calculator.py:Calculator.subtract
```
**Format**: Main line shows `icon name [lines] signature`. Second line (dimmed, indented) shows the node ID for copy-paste use with FlowSpace tools.

### AC6: Depth Limiting
**Given** a scanned codebase with deep nesting
**When** `fs2 tree --depth 2` is run
**Then** display only 2 levels deep, with indicator for hidden children

### AC7: Missing Graph Error
**Given** no graph file exists (`.fs2/graph.pickle` missing)
**When** `fs2 tree` is run
**Then** exit code 1 with message "No graph found. Run `fs2 scan` first."

### AC8: Empty Results
**Given** a scanned codebase
**When** `fs2 tree "nonexistent_pattern"` is run
**Then** display "No nodes match pattern 'nonexistent_pattern'" and exit 0

### AC9: Summary Line with Freshness
**Given** any successful tree display
**When** output completes
**Then** show summary with scan age: `✓ Found N nodes in M files (scanned Xh ago)`
**Examples**:
- `✓ Found 12 nodes in 3 files (scanned 2h ago)`
- `✓ Found 5 nodes in 1 file matching "*.py" (scanned 15m ago)`
- `✓ Found 100 nodes in 20 files (scanned 3d ago)`

### AC10: Dockerfile Tree Display
**Given** a scanned Dockerfile
**When** `fs2 tree Dockerfile` is run
**Then** display Dockerfile structure with stages and instructions:
```
📄 Dockerfile [1-45]
├── 🏗️ FROM (base) [1-1]
├── 🏗️ WORKDIR [3-3]
├── 🏗️ COPY [5-6]
├── 🏗️ RUN [8-12]
└── 🏗️ CMD [14-14]
```

### AC11: Markdown/README Tree Display
**Given** a scanned README.md
**When** `fs2 tree README.md` is run
**Then** display document structure with headings:
```
📄 README.md [1-150]
├── 📝 Installation [5-25]
│   ├── 📝 Prerequisites [7-12]
│   └── 📝 Quick Start [14-25]
├── 📝 Usage [27-80]
│   ├── 📝 Basic Commands [29-45]
│   └── 📝 Configuration [47-80]
└── 📝 Contributing [82-150]
```

### AC12: Data Files Show File-Level Only
**Given** a scanned YAML, JSON, or TOML file
**When** `fs2 tree config.yaml` is run
**Then** display only the file node (no internal structure):
```
📄 config.yaml [1-50]

✓ Found 1 node in 1 file
```
**Note**: Tree-sitter grammars for data files (YAML, JSON, TOML) create only file-level nodes. Use `jq`, `yq`, or `tomlq` for internal structure exploration.

### AC13: Exit Codes
**Given** any invocation of `fs2 tree`
**Then** exit codes follow convention:
- 0: Success (tree displayed or empty results)
- 1: User error (missing graph, invalid pattern, missing config)
- 2: System error (graph corruption, I/O failure)

### AC14: Help Output
**Given** `fs2 tree --help` is run
**Then** display usage, arguments, options with examples

### AC15: Loading Feedback for Large Graphs
**Given** a graph that takes >200ms to load
**When** `fs2 tree` is run
**Then** display a loading spinner with "Loading graph..." message

### AC16: Large Graph Warning
**Given** a graph with >10,000 nodes
**When** `fs2 tree` is run
**Then** display warning: "Graph contains N nodes. Loading may take a moment..."
**And** continue to load and display tree normally

---

## CLI Interface

```
fs2 tree [PATTERN] [OPTIONS]

Arguments:
  PATTERN              Path prefix or glob pattern to filter
                       Examples: "src/", "*.py", "test_*.py"
                       Default: "." (all files)

Options:
  --detail TEXT        Output detail level: "min" (default) or "max"
  --depth, -d INT      Maximum tree depth to display (default: unlimited)
  --type TEXT          Filter by node category: file, type, callable, section
  --verbose, -v        Enable debug logging (system diagnostics)
  --help               Show this message and exit
```

---

## Output Examples

### Example 1: Python Project (min)
```bash
$ fs2 tree src/core
```
```
📁 src/core/
├── 📄 adapters/file_scanner.py
│   ├── 📦 FileScanner [15-45]
│   │   ├── ƒ scan [20-35]
│   │   └── ƒ _walk_directory [37-45]
│   └── 📦 FileScannerError [48-52]
├── 📄 models/code_node.py
│   ├── ƒ classify_node [21-84]
│   └── 📦 CodeNode [87-166]
│       ├── ƒ create_file [167-210]
│       └── ƒ create_callable [212-280]
└── 📄 services/scan_pipeline.py
    └── 📦 ScanPipeline [25-150]
        ├── ƒ __init__ [30-45]
        └── ƒ run [47-150]

✓ Found 12 nodes in 3 files (scanned 2h ago)
```

### Example 2: Python Project (max)
```bash
$ fs2 tree src/core/models --detail max
```
```
📁 src/core/models/
├── 📄 code_node.py [1-350]
│   │  node: file:src/core/models/code_node.py
│   ├── ƒ classify_node [21-84]
│   │   │  node: callable:src/core/models/code_node.py:classify_node
│   │   │  sig: def classify_node(ts_kind: str) -> str
│   └── 📦 CodeNode [87-166]
│       │  node: type:src/core/models/code_node.py:CodeNode
│       ├── ƒ create_file [167-210]
│       │   │  node: callable:src/core/models/code_node.py:CodeNode.create_file
│       │   │  sig: @classmethod def create_file(...)
│       └── ƒ create_callable [212-280]
│           │  node: callable:src/core/models/code_node.py:CodeNode.create_callable
└── 📄 scan_summary.py [1-50]
    │  node: file:src/core/models/scan_summary.py
    └── 📦 ScanSummary [17-50]
        │  node: type:src/core/models/scan_summary.py:ScanSummary

✓ Found 7 nodes in 2 files (scanned 2h ago)
```

### Example 3: Dockerfile
```bash
$ fs2 tree Dockerfile
```
```
📄 Dockerfile [1-32]
├── 🏗️ FROM python:3.12-slim AS base [1-1]
├── 🏗️ WORKDIR /app [3-3]
├── 🏗️ COPY requirements.txt . [5-5]
├── 🏗️ RUN pip install -r requirements.txt [7-7]
├── 🏗️ FROM base AS development [10-10]
├── 🏗️ COPY . . [12-12]
├── 🏗️ FROM base AS production [15-15]
├── 🏗️ COPY --from=development /app /app [17-17]
└── 🏗️ CMD ["python", "main.py"] [19-19]

✓ Found 9 nodes in 1 file (scanned 2h ago)
```

### Example 4: README.md
```bash
$ fs2 tree README.md --detail max
```
```
📄 README.md [1-200]
│  node: file:README.md
├── 📝 Flowspace2 (fs2) [1-3]
│   │  node: section:README.md:Flowspace2 (fs2)
├── 📝 Installation [5-35]
│   │  node: section:README.md:Installation
│   ├── 📝 Prerequisites [7-15]
│   │   │  node: section:README.md:Installation#Prerequisites
│   └── 📝 Quick Start [17-35]
│       │  node: section:README.md:Installation#Quick Start
├── 📝 Usage [37-120]
│   │  node: section:README.md:Usage
│   ├── 📝 Scanning [39-60]
│   │   │  node: section:README.md:Usage#Scanning
│   └── 📝 Configuration [62-120]
│       │  node: section:README.md:Usage#Configuration
└── 📝 Contributing [122-200]
    │  node: section:README.md:Contributing

✓ Found 8 nodes in 1 file (scanned 2h ago)
```

### Example 5: Data Files (YAML/JSON - File-Level Only)
```bash
$ fs2 tree docker-compose.yml
```
```
📄 docker-compose.yml [1-45]

✓ Found 1 node in 1 file (scanned 2h ago)
```
**Note**: Data files (YAML, JSON, TOML) show only the file node. Use `yq .services docker-compose.yml` or `jq .dependencies package.json` for internal structure.

### Example 6: Glob Pattern Matching
```bash
$ fs2 tree "test_*.py"
```
```
📁 tests/
├── 📄 unit/cli/test_scan_cli.py
│   ├── 📦 TestTyperAppStructure [21-60]
│   ├── 📦 TestScanCommandInvocation [100-141]
│   └── 📦 TestExitCodes [237-315]
├── 📄 unit/cli/test_init_cli.py
│   ├── 📦 TestInitCommand [13-87]
│   └── 📦 TestMissingConfigError [150-172]
└── 📄 integration/test_fs2_cli_integration.py
    ├── 📦 TestCLIEndToEnd [11-63]
    └── 📦 TestCLIWithRealProject [104-153]

✓ Found 14 nodes in 3 files matching "test_*.py" (scanned 15m ago)
```

---

## Icon Legend

| Icon | Category | Description |
|------|----------|-------------|
| 📁 | directory | Virtual grouping (not a node) |
| 📄 | file | Source file node |
| 📦 | type | Class, struct, interface, enum |
| ƒ | callable | Function, method, lambda |
| 📝 | section | Markdown/document heading |
| 🏗️ | block | Dockerfile instruction, IaC block |

**Note**: Data files (YAML, JSON, TOML) appear as 📄 file nodes only - tree-sitter does not parse their internal structure.

---

## Node ID Format (Stable API)

Node IDs displayed in `--detail max` output follow a **stable format** that will not change without a major version bump. Users and scripts MAY rely on this format.

**Format**: `{category}:{file_path}:{qualified_name}`

| Category | Format | Example |
|----------|--------|---------|
| File | `file:{path}` | `file:src/main.py` |
| Class/Type | `type:{path}:{name}` | `type:src/models.py:User` |
| Function | `callable:{path}:{name}` | `callable:src/utils.py:helper` |
| Method | `callable:{path}:{class}.{method}` | `callable:src/calc.py:Calculator.add` |
| Section | `section:{path}:{heading}` | `section:README.md:Installation` |
| Block | `block:{path}:{name}` | `block:Dockerfile:FROM` |

**Stability commitment**: This format is compatible with FlowSpace MCP tools and is considered a stable API. Breaking changes require a major version bump (e.g., fs2 2.0).

**Caveat - Anonymous Elements**: Some languages (notably Go) produce AST nodes without explicit names (e.g., anonymous struct/interface bodies, block statements). These appear as `@N` where N is the line number (e.g., `type:path:@16`). These `@N` identifiers are **not stable** - they change if lines are added/removed above them. Scripts should not rely on `@N`-based node IDs for long-term matching.

---

## File Type Handling

| File Type | Structure Shown | Rationale |
|-----------|-----------------|-----------|
| Python (.py) | Full hierarchy | Classes, functions, methods |
| TypeScript (.ts/.tsx) | Full hierarchy | Classes, functions, interfaces |
| JavaScript (.js/.jsx) | Full hierarchy | Classes, functions |
| Go (.go) | Full hierarchy | Structs, functions, methods |
| Rust (.rs) | Full hierarchy | Structs, impl blocks, functions |
| Markdown (.md) | Headings | Section hierarchy via `#` headings |
| Dockerfile | Instructions | FROM, RUN, COPY, etc. |
| YAML (.yaml/.yml) | File only | Tree-sitter creates no child nodes |
| JSON (.json) | File only | Tree-sitter creates no child nodes |
| TOML (.toml) | File only | Tree-sitter creates no child nodes |

**Why data files show file-only**: Tree-sitter grammars for data formats (YAML, JSON, TOML) are designed for syntax highlighting, not structural parsing. They don't create nodes for keys/values. Use `jq`, `yq`, or `tomlq` for data exploration.

---

## Risks & Assumptions

### Risks
1. **Large codebases**: Graph with >10K nodes may produce overwhelming output
   - Mitigation: `--depth` limiting, require pattern argument for large graphs
2. **Deep nesting**: Some files (generated code) may have very deep hierarchies
   - Mitigation: Automatic depth limit suggestion in output
3. **Performance**: Loading entire graph for small query may be slow
   - Mitigation: Lazy loading, caching in future versions

### Assumptions
1. Graph is pre-built via `fs2 scan` (no on-demand scanning)
2. Rich library available for tree rendering
3. CodeNode `language` field accurately identifies file type
4. Users understand glob pattern syntax

---

## Open Questions

1. **Q1**: Should `--detail` default to `min` or `max`?
   - Recommendation: `min` (less noise, faster comprehension)

2. **Q2**: Should we support `--output json` for scripting?
   - Recommendation: Yes, in Phase 2 (enables piping to jq)

3. **Q3**: Should directory nodes be real graph nodes or virtual groupings?
   - Recommendation: Virtual groupings (directories aren't in the graph today)

4. **Q4**: How should we handle very large results (>100 files)?
   - Recommendation: Paginate or require `--depth` / more specific pattern

---

## ADR Seeds (Optional)

### Decision Drivers
- User experience: Quick visual understanding of code structure
- Consistency: Align with existing CLI patterns (`fs2 scan`, `fs2 init`)
- Extensibility: Standard `--detail` levels to apply across all commands

### Candidate Alternatives
- **A**: Tree as standalone command (recommended)
- **B**: Tree as subcommand of query (`fs2 query tree`)
- **C**: Tree as flag on scan (`fs2 scan --tree`)

### Stakeholders
- fs2 users exploring codebases
- FlowSpace MCP consumers needing node IDs
- Developers debugging scan results

---

## Standard Options (Convention)

Per [R9.1 CLI Standards](../../../docs/rules-idioms-architecture/rules.md#r91-standard-option-naming), when a command needs these capabilities, it MUST use these standard names:

| Capability | Option | Values | Description |
|------------|--------|--------|-------------|
| Detail level | `--detail` | `min`, `max` | Output detail level (when applicable) |
| Debug output | `--verbose`, `-v` | flag | System-level debug logging |
| Help | `--help` | flag | Show command help (Typer default) |

**Key distinction**: `--detail` controls user-facing output richness. `--verbose` enables system diagnostics. Not every command needs `--detail` - only those with varying output levels.

---

## Testing Strategy

**Approach**: Full TDD
**Rationale**: Core CLI command with user-facing output requires comprehensive test coverage to ensure correct behavior across all acceptance criteria.

**Focus Areas**:
- CLI invocation and exit codes (AC7, AC8, AC13)
- Output format verification (AC1, AC4, AC5, AC9)
- Pattern matching (AC2, AC3)
- Error handling (AC7, AC13)
- File-type-specific display (AC10, AC11, AC12)

**Excluded**:
- Performance benchmarking (deferred to optimization phase)
- Visual appearance testing (manual verification sufficient)

**Mock Usage**: Avoid mocks entirely
- Per Constitution P4 (Fakes over Mocks), use `FakeGraphStore` ABC implementation for unit tests
- Use real `NetworkXGraphStore` for integration tests
- Monkeypatch allowed for file system and environment variables only

---

## Documentation Strategy

**Location**: README.md only
**Rationale**: The `fs2 tree` command is self-documenting via `--help` output (AC14). README provides quick-start command examples.

**Content**:
- Brief mention of `fs2 tree` in README command list
- One or two usage examples
- Link to `fs2 tree --help` for full details

**Target Audience**: fs2 users exploring codebases
**Maintenance**: Update README when new major features added to tree command

---

**Specification Status**: Ready for architecture
**Next Step**: Run `/plan-3-architect` to create implementation plan

---

## Clarifications

### Session 2025-12-17

| Q# | Question | Answer | Spec Section Updated |
|----|----------|--------|---------------------|
| Q1 | Workflow Mode | **Full Mode** - Multi-phase plan with comprehensive gates | Header (Mode: Full) |
| Q2 | Testing Approach | **Full TDD** - Comprehensive unit/integration tests, write tests first | Testing Strategy |
| Q3 | Mock Usage | **Avoid mocks entirely** - Use FakeGraphStore ABC impl, monkeypatch for filesystem | Testing Strategy (Mock Usage) |
| Q4 | Documentation Location | **README.md only** - Brief mention with examples, --help for details | Documentation Strategy |

**Coverage Summary**:
- **Resolved**: 4 (Mode, Testing, Mocks, Documentation)
- **Deferred**: 0
- **Outstanding**: 0

---

## Critical Insights Discussion

**Session**: 2025-12-17
**Context**: fs2 tree Command Specification v1.0
**Analyst**: AI Clarity Agent
**Reviewer**: Development Team
**Format**: Water Cooler Conversation (5 Critical Insights)

### Insight 1: Graph Loading Performance Cliff

**Did you know**: Loading the entire graph for a small query creates a performance cliff where the command goes from instant to slow with no warning.

**Implications**:
- Users querying one file still load 50K+ nodes
- No feedback during load makes it seem broken
- Large graphs (>10K nodes) cause multi-second delays

**Options Considered**:
- Option A: Add loading spinner (quick fix)
- Option B: Lazy graph loading (optimize)
- Option C: Graph size warning (inform)
- Option D: Combine A + C (belt and suspenders)

**AI Recommendation**: Option D
- Reasoning: Best UX for current architecture without scope creep

**Decision**: Option D - Graph size warning + loading spinner

**Action Items**:
- [x] Added AC15: Loading spinner for >200ms loads
- [x] Added AC16: Warning for graphs >10K nodes

**Affects**: Acceptance Criteria, Risks section

---

### Insight 2: YAML/JSON Depth Limiting Is Automatic

**Did you know**: Tree-sitter's YAML/JSON grammars only create file-level nodes, so our "depth limiting" feature was solving a non-existent problem.

**Implications**:
- YAML files show only: `📄 config.yaml [1-50]` (no children)
- JSON files show only: `📄 package.json [1-80]` (no children)
- Spec examples were misleading users about capabilities

**Options Considered**:
- Option A: Remove AC12/AC13 and misleading examples
- Option B: Keep as "future enhancement"
- Option C: Accept file-only as the behavior

**AI Recommendation**: Option A
- Reasoning: Spec should reflect reality, not assumptions

**Decision**: Option A - Remove misleading examples, document reality

**Action Items**:
- [x] Merged AC12+AC13 into single "Data Files Show File-Level Only"
- [x] Removed Examples 5, 6, 7 (replaced with honest example)
- [x] Updated File Type Handling table
- [x] Updated Non-Goals section

**Affects**: AC12, Examples, File Type Handling, Non-Goals

---

### Insight 3: --detail Becomes a Naming Convention

**Did you know**: By introducing `--detail`, we're creating a naming convention that future commands should follow when they need detail levels.

**Implications**:
- Convention, not mandate (not every command needs it)
- `--verbose` reserved for system debug output
- Consistent vocabulary across CLI

**Options Considered**:
- Option A: Tree-only, defer standardization
- Option B: Define standard, implement later
- Option C: Implement across all commands now
- Option D: Use different name for tree

**AI Recommendation**: Initially A, clarified to naming convention

**Decision**: `--detail min|max` as naming convention (per R9.1)

**Action Items**:
- [x] Added Section 9 (CLI Standards) to rules.md
- [x] Changed slim/full → min/max throughout spec
- [x] Updated Standard Options section to reference rules.md

**Affects**: rules.md (new R9), spec (all detail level references)

---

### Insight 4: Node IDs Become User-Facing API

**Did you know**: By showing node IDs in output, we create an implicit API contract that users may script against.

**Implications**:
- Format changes would break user scripts
- FlowSpace MCP already depends on this format
- Users need stability guarantees

**Options Considered**:
- Option A: Document as stable API
- Option B: Document as internal (may change)
- Option C: Hide behind --show-ids flag

**AI Recommendation**: Option A
- Reasoning: Format is simple, logical, and already in use

**Decision**: Option A - Document node ID format as stable API

**Action Items**:
- [x] Added "Node ID Format (Stable API)" section
- [x] Documented format with examples
- [x] Added stability commitment statement

**Affects**: New spec section, API stability commitment

---

### Insight 5: Tree Shows Stale Data Without Warning

**Did you know**: Users have no way to know if tree output matches current files since it shows graph state from last scan.

**Implications**:
- Graph could be hours/days old
- New code won't appear until re-scan
- Users might share outdated information

**Options Considered**:
- Option A: Show "Last Scanned" timestamp footer
- Option B: Warn if graph >24h old
- Option C: Add --check-fresh flag
- Option D: Include timestamp in summary line

**AI Recommendation**: Option D
- Reasoning: Always visible but not intrusive, no magic thresholds

**Decision**: Option D - Timestamp in summary line

**Action Items**:
- [x] Updated AC9 to include scan freshness
- [x] Updated all output examples with `(scanned Xh ago)`

**Affects**: AC9, all output examples

---

## Session Summary

**Insights Surfaced**: 5 critical insights identified and discussed
**Decisions Made**: 5 decisions reached through collaborative discussion
**Action Items Created**: 0 remaining (all completed during session)
**Files Updated**:
- `docs/plans/004-tree-command/tree-command-spec.md` (this file)
- `docs/rules-idioms-architecture/rules.md` (new Section 9)

**Shared Understanding Achieved**: ✓

**Confidence Level**: High - All major concerns addressed, spec reflects reality

**Next Steps**:
1. Run `/plan-3-architect` to create implementation plan
2. Implementation is straightforward CS-2 with clear requirements
