# Research Report: fs2 Reports Feature

**Generated**: 2026-03-15T05:30:00Z
**Research Query**: "Create a new reports feature in fs2, with codebase graph as the first report. Must accept --graph-file. Later (OOS) some reports may take 2 graphs for comparisons."
**Mode**: Pre-Plan
**Location**: docs/plans/033-reports/exploration.md
**FlowSpace**: Not available (graph.pickle deleted during testing)
**Findings**: 63 across 8 subagents

## Executive Summary

### What It Does
fs2 currently has no report generation capability. This feature adds an `fs2 report` command group that generates self-contained HTML/JSON reports from the code graph. The first report type — `codebase-graph` — renders the full graph (nodes + containment + cross-file reference edges) as an interactive WebGL visualization using Sigma.js 2.

### Business Purpose
Agents and developers need visual exploration of large codebases — understanding structure, tracing call trees, and seeing dependency patterns at a glance. The graph data already exists (containment + reference edges); this feature makes it visually accessible.

### Key Insights
1. **Zero new dependencies needed** — Jinja2, networkx, Rich, Typer all already in pyproject.toml. Only vendored JS (Sigma.js ~150KB + Graphology ~80KB) added as static assets.
2. **All graph query APIs exist** — `get_all_nodes()`, `get_all_edges(edge_type)`, `get_edges()` are implemented and tested. Reports are pure read-only consumers.
3. **Template system proven** — SmartContent already uses Jinja2 + importlib.resources for wheel-safe template loading. Reports follow the identical pattern.
4. **Workshop 006 already designed the graph report** — Sigma.js 2 selected, treemap layout, LOD zoom, dark theme, self-contained HTML. Design decisions resolved.

### Quick Stats
- **New Files**: ~8 (CLI, service, templates, static assets, tests)
- **Modified Files**: ~3 (main.py, objects.py, pyproject.toml)
- **External Dependencies**: 0 (vendored JS only)
- **Prior Learnings**: 15 relevant discoveries from cross-file-rels implementation
- **Domains**: No domain registry; architecture is documentation-driven

## How It Would Work

### Entry Point

```bash
# Generate interactive HTML graph report
fs2 report codebase-graph --output report.html --open

# Use a specific graph file
fs2 --graph-file other.pickle report codebase-graph

# Future (OOS): comparison report taking 2 graphs
fs2 report diff --before v1.pickle --after v2.pickle
```

### Core Execution Flow

```
1. CLI parses args (report type, output path, options)
2. resolve_graph_from_context(ctx) → (config, graph_store)
3. graph_store.load(path) — lazy load on first access
4. ReportService.generate(report_type, options)
   a. get_all_nodes() → list[CodeNode]
   b. get_all_edges() → containment + reference edges
   c. compute_layout(nodes, edges) → positions
   d. build_graph_json(nodes, edges, positions) → JSON blob
5. TemplateService.render("codebase_graph.j2", context)
   → Self-contained HTML with embedded CSS + JS + JSON
6. safe_write_file(output_path, html)
7. Optional: open in browser
```

### Data Flow

```
GraphStore                ReportService              HTML Template
───────────               ─────────────              ─────────────
get_all_nodes()  ──────▶  extract_viz_data()  ─────▶  {{ graph_json }}
get_all_edges()  ──────▶  compute_layout()    ─────▶  {{ sigma_js }}
get_metadata()   ──────▶  build_metadata()    ─────▶  {{ metadata }}
```

## Architecture & Design

### Component Map

```
src/fs2/
├── cli/
│   └── report.py              # CLI entry: fs2 report <type>
├── core/
│   ├── services/
│   │   └── report_service.py  # Business logic: extract, layout, render
│   ├── templates/
│   │   └── reports/
│   │       └── codebase_graph.j2  # HTML template
│   └── static/
│       └── reports/
│           ├── sigma.min.js       # Vendored (~150KB)
│           ├── graphology.min.js  # Vendored (~80KB)
│           ├── graph-viewer.js    # Our interaction code (~20KB)
│           └── graph-viewer.css   # Dark theme styles (~5KB)
├── config/
│   └── objects.py             # Add ReportsConfig
```

### Clean Architecture Placement

| Layer | Component | Exists? |
|-------|-----------|---------|
| **CLI** | `report.py` — parse args, compose service, present output | CREATE |
| **Service** | `ReportService` — query graph, compute layout, render HTML | CREATE |
| **Adapter** | None needed — reports don't talk to external SDKs | — |
| **Repo** | GraphStore ABC — already exists, read-only consumption | REUSE |
| **Template** | Jinja2 `.j2` files — following SmartContent pattern | CREATE |
| **Static** | Vendored JS/CSS — loaded via importlib.resources | CREATE |
| **Config** | `ReportsConfig` — output_dir, theme, defaults | CREATE |

### Design Patterns Identified

| Pattern | Where Used | Application to Reports |
|---------|------------|----------------------|
| **Composition Root** | Every CLI command | `config, graph_store = resolve_graph_from_context(ctx)` |
| **Service DI** | TreeService, SearchService | `ReportService(config, graph_store)` |
| **Template Loading** | SmartContent TemplateService | `importlib.resources.files()` for wheel-safe access |
| **Safe File Write** | cli/utils.py | `validate_save_path()` + `safe_write_file()` |
| **Console Adapter** | All CLI commands | `stage_banner()`, `print_progress()`, `print_success()` |
| **Exit Codes** | All CLI commands | 0=success, 1=user error, 2=system error |

## Dependencies & Integration

### What Reports Depends On (All Existing)

| Dependency | Type | Method | Risk if Changed |
|-----------|------|--------|-----------------|
| GraphStore ABC | Required | `get_all_nodes()`, `get_all_edges()`, `get_metadata()` | Low — stable ABC |
| CodeNode | Required | 10 fields for viz (node_id, name, category, file_path, lines, signature, smart_content, language, parent_node_id) | Low — frozen dataclass |
| ConfigurationService | Required | `config.require(ReportsConfig)` | Low — standard pattern |
| Jinja2 | Required | Template rendering | Low — already v3.1+ |
| cli/utils.py | Required | `resolve_graph_from_context()`, `safe_write_file()` | Low — stable utilities |
| ConsoleAdapter | Required | Progress output | Low — stable ABC |

### External (Vendored) Dependencies

| Asset | Version | Size | Purpose |
|-------|---------|------|---------|
| Sigma.js 2 | Latest | ~150KB min | WebGL graph renderer |
| Graphology | Latest | ~80KB min | Graph data model for Sigma |

### What Would Depend On Reports

Nothing initially — reports are a leaf feature. Future consumers:
- MCP server could expose `generate_report` tool
- `fs2 watch` could auto-regenerate reports on change

## Graph Data Available for Reports

### Node Fields for Visualization

| Field | Use in Report | Example |
|-------|--------------|---------|
| `node_id` | Unique identifier | `type:src/fs2/core/repos/graph_store.py:GraphStore` |
| `name` | Display label | `GraphStore` |
| `category` | Color coding | `type` → purple, `callable` → cyan |
| `file_path` | Directory grouping | `src/fs2/core/repos/graph_store.py` |
| `start_line` / `end_line` | Node size | 21–225 (204 lines) |
| `signature` | Tooltip first line | `class GraphStore(ABC):` |
| `smart_content` | Tooltip summary | "Abstract base class for..." |
| `language` | Language badge | `python` |
| `parent_node_id` | Containment hierarchy | `file:src/fs2/core/repos/graph_store.py` |

### Edge Types

| Type | Attribute | Count (typical) | Visual |
|------|-----------|-----------------|--------|
| Containment | No `edge_type` key | ~4,800 | Implicit in treemap layout |
| References | `edge_type="references"` | ~70-500 | Amber curved lines |

### Query API

```python
# All nodes
nodes = graph_store.get_all_nodes()  # → list[CodeNode]

# All edges (both types)
all_edges = graph_store.get_all_edges()  # → [(src, tgt, data)]

# Reference edges only
ref_edges = graph_store.get_all_edges(edge_type="references")

# Per-node relationships
edges = graph_store.get_edges(node_id, direction="both", edge_type="references")

# Graph metadata
meta = graph_store.get_metadata()  # → {format_version, node_count, edge_count, ...}
```

## Prior Learnings (From Cross-File Rels Implementation)

### 📚 PL-01: Template Asset Loading Pattern
**Source**: Phase 2 SmartContent (008-smart-content)
**What**: `importlib.resources.files()` + `DictLoader` for wheel-safe Jinja2 templates. Validates all templates at init (fail-fast).
**Action**: Follow identical pattern for report templates. Create `src/fs2/core/templates/reports/`.

### 📚 PL-02: TreeService Filters Cross-File Edges
**Source**: Phase 3 cross-file-rels (tree ref count fix)
**What**: `_get_containment_children()` intentionally excludes `edge_type="references"` to prevent cycles in tree display.
**Action**: Reports must query edges directly via `get_all_edges()`, NOT through TreeService — TreeService hides reference edges by design.

### 📚 PL-03: Node Serialization Leak Risk
**Source**: Phase 3 cross-file-rels (CLI get-node fix)
**What**: `asdict(node)` leaked embedding vectors and content hashes. Fixed by explicit field selection.
**Action**: Never use `asdict()` for report data. Use explicit field list like MCP's `_code_node_to_dict()`.

### 📚 PL-04: GraphStore Format Version 1.1
**Source**: Phase 1 cross-file-rels
**What**: Version 1.1 = edges may carry attributes. Backward compatible with 1.0.
**Action**: No migration needed. Report can read any 1.0 or 1.1 graph.

### 📚 PL-05: RestrictedUnpickler Allowlist
**Source**: Phase 4 cross-file-rels (AdjacencyView crash)
**What**: New networkx types need to be in the allowlist. `networkx.classes.coreviews` was added after a crash.
**Action**: If reports add new data types to the graph (they shouldn't — read-only), ensure pickle compatibility.

## Modification Considerations

### ✅ Safe to Build

1. **CLI command** (`report.py`): New file, no existing code touched
2. **Service** (`report_service.py`): New file, clean DI pattern
3. **Templates** (`reports/*.j2`): New directory, following SmartContent pattern
4. **Static assets** (`static/reports/`): New directory for vendored JS

### ⚠️ Modify with Caution

1. **`pyproject.toml`**: Must add template/static paths to `[tool.setuptools.package-data]`
2. **`config/objects.py`**: Add `ReportsConfig` — follow existing pattern exactly
3. **`cli/main.py`**: Register new command — single line addition

### Extension Points

- **New report types**: Add method to `ReportService` + template + optional static assets
- **Output formats**: Template system supports HTML, Markdown, JSON via different `.j2` files
- **Comparison reports (OOS)**: Service accepts 2 GraphStore instances, diff logic in service layer

## --graph-file Support

Already built into fs2's global options system:

```python
# main.py callback already handles this:
@app.callback()
def main(ctx: typer.Context,
         graph_file: str = typer.Option(None, "--graph-file"),
         graph_name: str = typer.Option(None, "--graph-name")):
    ctx.obj = CLIContext(graph_file=graph_file, graph_name=graph_name)

# In report.py, just use:
config, graph_store = resolve_graph_from_context(ctx)
# graph_store is already loaded from the specified file
```

No additional work needed — the `--graph-file` flag is inherited by all commands automatically.

## Future: Comparison Reports (OOS but Designed For)

The architecture should accommodate this future pattern:

```python
# Future CLI
@app.command()
def diff(
    ctx: typer.Context,
    before: Path = typer.Option(..., help="Baseline graph"),
    after: Path = typer.Option(..., help="Updated graph"),
):
    store_before = NetworkXGraphStore(config)
    store_before.load(before)
    store_after = NetworkXGraphStore(config)
    store_after.load(after)
    
    report = report_service.generate_diff(store_before, store_after)
```

The key design decision: `ReportService` methods accept `GraphStore` as a parameter (not just from constructor), enabling multi-graph reports without changing the DI pattern.

## Recommendations

### Implementation Approach

| Phase | Scope | Effort |
|-------|-------|--------|
| **1** | CLI scaffold + ReportsConfig + ReportService skeleton + `--output` | Small |
| **2** | Graph data extraction + treemap layout algorithm in Python | Medium |
| **3** | Sigma.js vendoring + HTML template + interactive viewer JS | Medium |
| **4** | LOD zoom, clustering for 50K+ nodes, polish | Medium |

### Key Design Decisions Already Made (Workshop 006)

- **Renderer**: Sigma.js 2 + Graphology (WebGL, 100K+ nodes)
- **Layout**: Treemap primary, force-directed as interactive toggle
- **Containment edges**: Show only for selected node's ancestry
- **Tooltips**: Both signature + smart_content
- **Bundle**: Vendored JS (no CDN), single self-contained HTML
- **Theme**: Dark mode default (Tailwind Slate palette)

## Files Inventory

### To Create

| File | Purpose | Est. Lines |
|------|---------|-----------|
| `src/fs2/cli/report.py` | CLI command group | ~100 |
| `src/fs2/core/services/report_service.py` | Service: extract + layout + render | ~300 |
| `src/fs2/core/templates/reports/codebase_graph.j2` | HTML template | ~100 |
| `src/fs2/core/static/reports/sigma.min.js` | Vendored Sigma.js 2 | ~150KB |
| `src/fs2/core/static/reports/graphology.min.js` | Vendored Graphology | ~80KB |
| `src/fs2/core/static/reports/graph-viewer.js` | Interaction code | ~200 |
| `src/fs2/core/static/reports/graph-viewer.css` | Dark theme styles | ~80 |
| `src/fs2/config/objects.py` | Add ReportsConfig | ~20 |
| `tests/unit/cli/test_report_cli.py` | CLI tests | ~100 |
| `tests/unit/services/test_report_service.py` | Service tests | ~150 |

### To Modify

| File | Change |
|------|--------|
| `src/fs2/cli/main.py` | Register `report` command |
| `pyproject.toml` | Add template/static data paths |

## Next Steps

- **Proceed to specification**: Run `/plan-1b-specify` to create the feature specification
- **No external research needed**: All technology decisions already made in Workshop 006

---

**Research Complete**: 2026-03-15T05:35:00Z
**Report Location**: docs/plans/033-reports/exploration.md
