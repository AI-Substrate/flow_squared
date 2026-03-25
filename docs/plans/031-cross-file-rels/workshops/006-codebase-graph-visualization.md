# Workshop: Codebase Graph Visualization Report

**Type**: Integration Pattern / CLI Flow
**Plan**: 031-cross-file-rels
**Spec**: [cross-file-rels-spec.md](../cross-file-rels-spec.md)
**Created**: 2026-03-15
**Status**: Draft

**Related Documents**:
- [001-edge-storage.md](001-edge-storage.md) — How edges are stored in the graph
- [002-serena-benchmarks.md](002-serena-benchmarks.md) — Serena performance data

---

## Purpose

Design an `fs2 report codebase-graph` command that generates a self-contained interactive HTML file visualizing the entire code graph — containment hierarchy + cross-file reference edges — at scales of 5,000–100,000+ nodes with smooth 60fps interaction.

This is the first in a planned `fs2 report` command group. Future reports might include dependency analysis, coverage maps, or change-impact visualizations.

## Key Questions Addressed

- Which JS library can handle 10K–100K nodes in the browser without freezing?
- How do we represent both containment hierarchy and cross-file references visually?
- How do we precompute layout in Python and embed it in a single HTML file?
- What interaction patterns matter for code exploration (zoom, filter, search)?
- How do we keep the HTML file self-contained (no server, no CDN)?

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  fs2 report codebase-graph                                      │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ GraphStore   │───▶│ Layout       │───▶│ HTML Generator   │   │
│  │ (read graph) │    │ (positions)  │    │ (template + data)│   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│        │                    │                      │             │
│        ▼                    ▼                      ▼             │
│  get_all_nodes()     Python layout          Single .html file   │
│  get_all_edges()     algorithm              with embedded:      │
│                      (hierarchical +         - CSS (dark theme) │
│                       force overlay)         - Sigma.js 2       │
│                                              - Graphology       │
│                                              - JSON graph data  │
│                                              - Layout positions │
└─────────────────────────────────────────────────────────────────┘
```

---

## Library Selection: Sigma.js 2 + Graphology

### Why Sigma.js 2

| Criterion | Sigma.js 2 | Runner-up (Cytoscape) | Why it matters |
|-----------|-----------|----------------------|----------------|
| Max nodes (interactive) | **100K+** | ~2K | We need 5K–100K |
| Rendering | **WebGL** | Canvas | 10–50x faster |
| Bundle size | ~300KB | ~500KB+ | Single-file embed |
| Node styling | Programmatic | CSS-like | Simpler for codegen |
| Edge rendering | GPU-accelerated | CPU per-frame | Critical at scale |

### Why Graphology

Sigma.js 2 requires Graphology as its graph data model. Graphology provides:
- Efficient in-memory graph representation
- Built-in layout algorithms (ForceAtlas2, circular, random)
- Attribute system for node/edge styling
- Serialization to/from JSON

### Why NOT other libraries

- **D3.js**: SVG-based, dies above 5K nodes. Canvas mode requires manual everything.
- **Cosmos.gl**: GPU-accelerated to 1M nodes but GLSL-only customization, no hierarchy.
- **vis.js**: Canvas-based, benchmarks show 10–20x slower than Sigma at scale.
- **Cytoscape.js**: Rich features but Canvas rendering limits to ~2K nodes interactively.
- **ELK.js**: Great layout algorithms but layout-only — no renderer, 500KB+ bundle.

---

## Data Pipeline

### Step 1: Extract Graph Data (Python)

```python
class GraphReportService:
    """Generates visualization data from the code graph."""
    
    def __init__(self, config: ConfigurationService, graph_store: GraphStore):
        self._config = config
        self._graph_store = graph_store
    
    def extract_visualization_data(self) -> VisualizationData:
        nodes = self._graph_store.get_all_nodes()
        containment_edges = self._graph_store.get_all_edges(edge_type=None)
        reference_edges = self._graph_store.get_all_edges(edge_type="references")
        
        # Filter: containment edges have no edge_type key
        containment_only = [
            (s, t, d) for s, t, d in containment_edges
            if "edge_type" not in d
        ]
        
        return VisualizationData(
            nodes=nodes,
            containment_edges=containment_only,
            reference_edges=reference_edges,
        )
```

### Step 2: Compute Layout (Python)

We precompute positions in Python because:
1. Layout for 100K nodes takes seconds — too slow for browser startup
2. Hierarchical layouts need containment knowledge that's cleaner in Python
3. The browser just renders precomputed positions instantly

**Layout Strategy: Hierarchical Treemap + Force-Directed Overlay**

```
Phase 1: Treemap layout for containment hierarchy
  - Files are rectangles grouped by directory
  - Classes/types are nested rectangles within files
  - Methods/functions are leaf rectangles within classes
  - Size based on line count (end_line - start_line)

Phase 2: Force overlay for reference edges
  - Run a few iterations of force-directed adjustment
  - Keeps nodes near their treemap position
  - Pulls referenced nodes slightly closer together
  - Strong spring back to treemap position prevents chaos
```

```python
@dataclass
class NodePosition:
    node_id: str
    x: float
    y: float
    size: float  # visual radius
    color: str   # hex color based on category
    label: str   # display name

def compute_layout(data: VisualizationData) -> list[NodePosition]:
    """Compute treemap positions for all nodes."""
    # Group by directory
    dir_groups = group_by_directory(data.nodes)
    
    # Treemap layout per directory
    positions = {}
    for dir_path, dir_nodes in dir_groups.items():
        area = sum(n.end_line - n.start_line for n in dir_nodes)
        # Squarified treemap algorithm
        rects = squarify(dir_nodes, area, ...)
        for node, rect in zip(dir_nodes, rects):
            positions[node.node_id] = NodePosition(
                node_id=node.node_id,
                x=rect.cx, y=rect.cy,
                size=max(2, math.log2(rect.area + 1)),
                color=CATEGORY_COLORS[node.category],
                label=node.name or node.qualified_name,
            )
    return list(positions.values())
```

**Color Scheme by Category**:

| Category | Color | Hex |
|----------|-------|-----|
| file | Slate blue | `#64748b` |
| type (class) | Purple | `#a855f7` |
| callable (function/method) | Cyan | `#06b6d4` |
| section | Gray | `#9ca3af` |
| folder | Dark gray | `#4b5563` |

**Reference Edge Styling**:

| Edge Type | Color | Style |
|-----------|-------|-------|
| Containment | `#334155` (very subtle) | Thin, low opacity |
| References | `#f59e0b` (amber) | Medium, curved |

### Step 3: Generate HTML (Python)

```python
def generate_report_html(
    positions: list[NodePosition],
    edges: list[EdgeData],
    metadata: dict,
) -> str:
    """Generate self-contained HTML with embedded data and libraries."""
    
    # Inline all JS/CSS — no external dependencies
    template = REPORT_TEMPLATE.format(
        graph_json=json.dumps(build_graph_json(positions, edges)),
        sigma_js=read_bundled_asset("sigma.min.js"),       # ~150KB
        graphology_js=read_bundled_asset("graphology.min.js"),  # ~80KB
        app_js=read_bundled_asset("graph-viewer.js"),      # ~20KB  
        app_css=read_bundled_asset("graph-viewer.css"),     # ~5KB
        metadata_json=json.dumps(metadata),
    )
    return template
```

---

## Graph JSON Format

The JSON blob embedded in the HTML carries all data needed for rendering:

```json
{
  "metadata": {
    "generated_at": "2026-03-15T05:00:00Z",
    "node_count": 5635,
    "edge_count": 4800,
    "ref_edge_count": 72,
    "scan_root": "/path/to/project"
  },
  "nodes": [
    {
      "id": "type:src/fs2/core/repos/graph_store.py:GraphStore",
      "label": "GraphStore",
      "x": 450.2,
      "y": 120.5,
      "size": 8,
      "color": "#a855f7",
      "category": "type",
      "file": "src/fs2/core/repos/graph_store.py",
      "lines": [21, 225],
      "smart_content": "Abstract base class for graph storage..."
    }
  ],
  "edges": [
    {
      "source": "file:src/fs2/core/repos/graph_store.py",
      "target": "type:src/fs2/core/repos/graph_store.py:GraphStore",
      "type": "containment"
    },
    {
      "source": "callable:src/fs2/cli/scan.py:scan",
      "target": "type:src/fs2/core/repos/graph_store.py:GraphStore",
      "type": "references"
    }
  ]
}
```

---

## Scaling Strategy: Level-of-Detail (LOD)

For graphs with 10K–100K nodes, we need progressive detail:

### Zoom Levels

```
Zoom 0 (full view):     Show directories as colored regions
                         Hide all nodes except folders
                         Hide all edges
                         Labels: directory names only

Zoom 1 (directory):      Show files as dots within directories
                         Show inter-file reference edges (aggregated)
                         Labels: filenames

Zoom 2 (file):           Show classes/types within files
                         Show reference edges between types
                         Labels: class/type names

Zoom 3 (detail):         Show all nodes (methods, functions)
                         Show all reference edges
                         Labels: full qualified names
                         Show smart_content on hover
```

### Implementation

```javascript
// In graph-viewer.js
sigma.on("camera", ({ ratio }) => {
  const zoom = Math.log2(1 / ratio);
  
  // LOD: filter visible nodes by zoom level
  graph.forEachNode((id, attrs) => {
    if (zoom < 1 && attrs.category !== "folder") {
      sigma.setSetting("nodeReducer", hideNode);
    } else if (zoom < 2 && attrs.category === "callable") {
      sigma.setSetting("nodeReducer", hideNode);
    }
    // ... etc
  });
});
```

### Clustering for Extreme Scale (50K+ nodes)

For very large codebases, pre-cluster at the directory level:

```python
def cluster_by_directory(nodes, max_visible=5000):
    """If node count exceeds threshold, cluster leaf nodes."""
    if len(nodes) <= max_visible:
        return nodes  # No clustering needed
    
    # Replace methods/functions with a single "N methods" summary node
    clusters = {}
    for node in nodes:
        if node.category in ("callable",) and len(nodes) > max_visible:
            dir_key = os.path.dirname(node.file_path)
            clusters.setdefault(dir_key, []).append(node)
    
    # Replace clusters with summary nodes
    # User can click to expand
```

---

## Interactive Features

### Panel Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  fs2 Codebase Graph — project-name                    [⚙] [?] │
├──────────┬──────────────────────────────────────────────────────┤
│ FILTERS  │                                                      │
│          │              ┌──────┐                                │
│ □ Files  │         ┌────┤ type ├────┐                           │
│ ☑ Types  │         │    └──────┘    │                           │
│ ☑ Funcs  │    ┌────┴──┐        ┌───┴───┐                       │
│          │    │ func  │        │ func  │                        │
│ SEARCH   │    └───────┘        └───────┘                        │
│ [______] │                                                      │
│          │         Graph canvas (Sigma.js WebGL)                │
│ DETAILS  │                                                      │
│ ──────── │                                                      │
│ Name:    │                                                      │
│ File:    │                                                      │
│ Lines:   │                                                      │
│ Refs: 12 │                                                      │
│          │                                                      │
│ Incoming │                                                      │
│  • caller│                                                      │
│  • caller│                                                      │
│          │                                                      │
│ Outgoing │                                                      │
│  • dep   │                                                      │
│  • dep   │                                                      │
├──────────┴──────────────────────────────────────────────────────┤
│ 5,635 nodes │ 4,872 edges │ 72 references │ Zoom: 2.3x        │
└─────────────────────────────────────────────────────────────────┘
```

### Interactions

| Action | Behavior |
|--------|----------|
| **Click node** | Select node, show details in sidebar, highlight edges |
| **Hover node** | Show tooltip with name + smart_content preview |
| **Click edge** | Highlight source and target nodes |
| **Scroll wheel** | Zoom in/out with LOD transitions |
| **Drag canvas** | Pan |
| **Search box** | Filter nodes by name/path, auto-zoom to results |
| **Category toggles** | Show/hide node categories |
| **Reference toggle** | Show/hide cross-file reference edges |
| **Double-click node** | Zoom to fit node + its references |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `f` | Fit entire graph in view |
| `r` | Toggle reference edges |
| `/` | Focus search box |
| `Esc` | Clear selection |
| `1-4` | Set zoom level preset |

---

## CLI Interface

### Command

```
$ fs2 report codebase-graph [OPTIONS]

Options:
  --output PATH       Output HTML file path (default: .fs2/reports/codebase-graph.html)
  --open              Open in default browser after generation
  --no-smart-content  Exclude smart_content from node data (smaller file)
  --no-references     Exclude cross-file reference edges
  --max-nodes INT     Cluster nodes if graph exceeds this count (default: 10000)
  --theme TEXT        Color theme: "dark" (default) | "light"
```

### Output

```
$ fs2 report codebase-graph --open

──────────────────── REPORT: CODEBASE GRAPH ────────────────────

  Loading graph: 5,635 nodes, 4,872 edges
  Computing layout... done (1.2s)
  Cross-file references: 72 edges
  Generating HTML...

  ✓ Report saved to .fs2/reports/codebase-graph.html (2.4 MB)
  ✓ Opening in browser...
```

### File Size Budget

| Component | Size | Notes |
|-----------|------|-------|
| Sigma.js 2 (minified) | ~150KB | WebGL renderer |
| Graphology (minified) | ~80KB | Graph data model |
| graph-viewer.js | ~20KB | Our interaction code |
| graph-viewer.css | ~5KB | Dark theme styles |
| Graph JSON (5K nodes) | ~500KB | Positions + metadata |
| Graph JSON (50K nodes) | ~5MB | With clustering |
| **Total (5K nodes)** | **~800KB** | |
| **Total (50K nodes)** | **~6MB** | |

---

## Bundling Strategy

All JS/CSS must be self-contained in the HTML. Two options:

### Option A: Vendor bundle at build time (Recommended)

```
src/fs2/
├── report/
│   ├── assets/
│   │   ├── sigma.min.js         # Vendored, version-pinned
│   │   ├── graphology.min.js    # Vendored
│   │   ├── graph-viewer.js      # Our code
│   │   └── graph-viewer.css     # Our styles
│   ├── templates/
│   │   └── codebase-graph.html  # Jinja2 template
│   ├── layout.py                # Treemap + force layout
│   └── report_service.py        # Orchestrator
```

The HTML template uses Jinja2 `{{ }}` blocks to inline everything:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>fs2 — {{ project_name }}</title>
  <style>{{ css }}</style>
</head>
<body>
  <div id="app">...</div>
  <script>{{ sigma_js }}</script>
  <script>{{ graphology_js }}</script>
  <script>
    const GRAPH_DATA = {{ graph_json }};
    const METADATA = {{ metadata_json }};
  </script>
  <script>{{ app_js }}</script>
</body>
</html>
```

### Option B: Download at report time

Download Sigma.js/Graphology from CDN on first `fs2 report`, cache in `.fs2/cache/report-assets/`. Avoids bloating the fs2 package but requires internet on first run.

**Recommendation**: Option A. Vendor the ~250KB of minified JS. It's a small price for offline reliability. Update vendored files when upgrading fs2.

---

## CSS Theme: Dark Mode (Default)

```css
:root {
  --bg-primary: #0f172a;       /* Slate 900 */
  --bg-secondary: #1e293b;     /* Slate 800 */
  --bg-panel: #1e293b;
  --text-primary: #f1f5f9;     /* Slate 100 */
  --text-secondary: #94a3b8;   /* Slate 400 */
  --accent: #06b6d4;           /* Cyan 500 */
  --border: #334155;           /* Slate 700 */
  --ref-edge: #f59e0b;         /* Amber 500 */
  --containment-edge: #1e293b; /* Very subtle */
}

body {
  margin: 0;
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, sans-serif;
}

#sigma-container {
  width: 100%;
  height: 100vh;
  background: var(--bg-primary);
}

.sidebar {
  position: fixed;
  left: 0; top: 0; bottom: 0;
  width: 280px;
  background: var(--bg-panel);
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 16px;
}

.node-detail h2 {
  color: var(--accent);
  font-size: 14px;
  font-weight: 600;
}

.status-bar {
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: 28px;
  background: var(--bg-secondary);
  border-top: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  font-size: 12px;
  color: var(--text-secondary);
}
```

---

## Open Questions

### Q1: Should containment edges be visible by default?

**RESOLVED → C**: Show containment edges only for the selected node's ancestry chain. The treemap layout already implies containment spatially, so full containment edges would just clutter the view. When a node is selected, its file→class→method lineage illuminates contextually.

### Q2: Should we support a `--watch` mode that auto-regenerates?

**OPEN**: Could pair with `fs2 watch` to regenerate the HTML on each scan. The browser would need to auto-reload (could inject a simple polling script). Defer to future iteration.

### Q3: Treemap vs Force-directed for initial layout?

**RESOLVED → Treemap primary with force-directed as toggle**. Treemap is the default layout — deterministic, space-efficient, scales to 100K+ nodes without iterative computation. Force-directed (ForceAtlas2) available as an interactive toggle for organic connectivity-based clustering.

### Q4: How to handle non-Python files?

**RESOLVED**: The graph already contains nodes for all scanned languages (Python, JS, Rust, etc.). The visualization should show all languages. Category colors are language-agnostic. Reference edges only exist for languages with LSP resolution, but containment is universal.

### Q5: Should node data include source code snippets?

**RESOLVED → Both signature + smart_content**. Hover tooltips show the declaration signature (`class GraphStore(ABC):`) plus the AI-generated smart_content summary. Adds ~300KB for a 5K node graph (total ~1.1MB) — acceptable for the richness it provides.

---

## Implementation Phases (Rough)

| Phase | Scope | Effort |
|-------|-------|--------|
| **1** | Basic report: treemap layout, all nodes, containment edges, single HTML file | Medium |
| **2** | Reference edges, click-to-inspect sidebar, search | Medium |
| **3** | LOD zoom levels, clustering for 50K+ nodes | High |
| **4** | `fs2 report` command group scaffold, theme options | Low |

---

## Quick Reference

```bash
# Generate report (after scan)
fs2 report codebase-graph --open

# Generate without smart content (smaller file)
fs2 report codebase-graph --no-smart-content

# Generate with custom output path
fs2 report codebase-graph --output ./my-report.html

# Cluster large graphs
fs2 report codebase-graph --max-nodes 5000
```
