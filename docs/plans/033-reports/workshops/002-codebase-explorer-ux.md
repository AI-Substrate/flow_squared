# Workshop: Codebase Explorer UX & View Modes

**Type**: UX Design + Integration Pattern
**Plan**: 033-reports
**Spec**: [reports-spec.md](../reports-spec.md)
**Created**: 2026-03-15
**Status**: Draft

**Related Documents**:
- [001-visual-design-ux.md](001-visual-design-ux.md) — Cosmos theme, colors, typography
- [006-codebase-graph-visualization.md](../../031-cross-file-rels/workshops/006-codebase-graph-visualization.md) — Library selection

**Domain Context**:
- **Primary Domain**: static-assets (graph-viewer.js, graph-viewer.css)
- **Related Domains**: services (report_service.py — computed fields), templates (HTML structure)

---

## Purpose

Redesign the codebase graph report from a "dump everything" renderer into an **interactive codebase explorer** with progressive disclosure, view modes, search/filter, and relationship walking. The current visualization puts all 5,710 nodes and 4,515 edges on screen simultaneously — creating an unusable dot-matrix with amber spaghetti. This workshop defines how users actually explore an unfamiliar codebase.

## Key Questions Addressed

- How do you orient yourself in an unfamiliar codebase?
- How do you find entry points and walk call trees?
- How should 5K+ nodes be presented without overwhelming the viewer?
- What view modes and filters make the graph usable, not just pretty?
- How do we leverage Sigma.js 2 / Graphology capabilities for zero-rebuild filtering?

---

## The Core Problem

Opening the current report shows this:

```
┌──────────────────────────────────────────────────────────┐
│ ●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●● │
│ ●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●● │
│ ●●●●●●●●●//////////●●●●●●●●●●●●●●●//////////●●●●●●●●● │
│ ●●●●●●●●●//////////●●●●●●●●●●●●●●●//////////●●●●●●●●● │
│ ●●●●●●●●●//////////●●●●●●●●●●●●●●●//////////●●●●●●●●● │
│ ●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●● │
│                                                          │
│  5,710 nodes  ·  4,515 edges  ·  UNUSABLE               │
└──────────────────────────────────────────────────────────┘
```

**Why it fails**: No hierarchy. No progressive disclosure. All edges visible. Grid layout with overlaps. No way to focus on anything.

**What it should feel like**: Google Maps for code. Start zoomed out on "continents" (directories). Zoom in to see "cities" (files). Click a "building" (function) to see its connections. Search to jump anywhere.

---

## Design Principles

1. **Progressive disclosure** — Show 10-20 things at a time, not 5,710
2. **Focus over fullness** — Hide everything except what the user is exploring
3. **Edges on demand** — Never show all edges. Show connections for the selected node only
4. **Multiple sizing strategies** — Size by code volume, by connections, or by category
5. **Filter, don't scroll** — Search and filter are primary navigation, not pan/zoom
6. **Zero rebuild** — All filtering uses Sigma.js reducers (instant, no graph reconstruction)

---

## View Modes

### Overview: Directory Regions (Default on Open)

The landing view. Shows the codebase at the directory level — like looking at a floor plan of a building.

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│   ┌──────────────┐  ┌──────────────────────────────────┐   │
│   │  tests/      │  │  src/fs2/                        │   │
│   │  unit/       │  │                                  │   │
│   │              │  │  ┌────────┐ ┌──────┐ ┌────────┐  │   │
│   │  847 nodes   │  │  │cli/   │ │config│ │core/   │  │   │
│   │              │  │  │ 12    │ │  25  │ │        │  │   │
│   │              │  │  └────────┘ └──────┘ │ 1,200  │  │   │
│   │              │  │                      │        │  │   │
│   └──────────────┘  │                      └────────┘  │   │
│                      └──────────────────────────────────┘   │
│   ┌────────┐                                               │
│   │ docs/  │   No edges visible. Just regions + counts.    │
│   │  320   │                                               │
│   └────────┘                                               │
└────────────────────────────────────────────────────────────┘
```

**Implementation**: 
- Group nodes by top-level directory (from `file_path`)
- Render directory regions as large labeled rectangles using Sigma.js custom node renderer OR overlay HTML divs
- Node count shown as label inside each region
- **No edges visible** — clean orientation
- Click a region → drill into it (LOD zoom or filter)

**Alternative (simpler)**: Show only file-category nodes (`category: "file"`) at default zoom, hide everything else via nodeReducer. Files are already positioned by treemap.

### Drill-Down: Files → Classes → Functions

Click a directory region or zoom in to see its contents.

```
┌────────────────────────────────────────────────────────────┐
│  src/fs2/core/services/                                    │
│                                                            │
│  ┌──────────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ report_service.py│  │tree_     │  │scan_pipeline.py  │  │
│  │                  │  │service.py│  │                  │  │
│  │  ReportService   │  │          │  │  ScanPipeline    │  │
│  │  ReportResult    │  │ TreeSvc  │  │  PipelineCtx     │  │
│  │  _serialize_node │  │ TreeNode │  │  _run_stage      │  │
│  │  _serialize_edge │  │          │  │                  │  │
│  └──────────────────┘  └──────────┘  └──────────────────┘  │
│                                                            │
│  Still no edges. Just files and their contents.            │
└────────────────────────────────────────────────────────────┘
```

**Implementation**:
- nodeReducer: show only nodes where `file_path` starts with the selected directory prefix
- Within a file: show its children (nodes where `parent_node_id` matches the file)
- Labels become visible as node count decreases
- Still no edges until user clicks a specific node

### Focus: Selected Node + Neighborhood

Click any node to enter focus mode. Shows the selected node, its direct callers, and its direct callees. Everything else dims or hides.

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│                    ┌─────────────┐                         │
│   scan.py:main ───▶│ ReportService│──▶ GraphStore          │
│                    │ .generate() │                         │
│   cli/report.py ──▶│             │──▶ _serialize_node      │
│                    └─────────────┘──▶ _render_template      │
│                          │                                 │
│                          ▼                                 │
│                    compute_treemap                          │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ INSPECTOR                                           │   │
│  │ ReportService.generate_codebase_graph()             │   │
│  │ Category: callable  ·  Lines: 94-164                │   │
│  │ File: src/fs2/core/services/report_service.py       │   │
│  │                                                     │   │
│  │ Callers (2):  cli/report.py  ·  scan.py             │   │
│  │ Calls (4):    GraphStore  ·  _serialize_node  · ... │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

**Implementation**:
- `graph.neighbors(nodeId)` — O(degree) instant
- `graph.inNeighbors(nodeId)` — callers
- `graph.outNeighbors(nodeId)` — callees
- nodeReducer: full opacity for selected + neighbors, dim everything else to 0.1 opacity
- edgeReducer: show only edges connected to selected node
- Camera animates to center on selected node
- Inspector panel (HTML overlay) shows node details

### Walk: Follow the Call Chain

From focus mode, click a caller or callee to walk the chain. The view shifts to that node's neighborhood. Breadcrumb trail shows where you've been.

```
┌────────────────────────────────────────────────────────────┐
│  Breadcrumb: main() → ScanPipeline.run() → ReportService  │
│                                                            │
│  [Current neighborhood of ReportService shown]             │
│                                                            │
│  Click any neighbor to continue walking...                 │
│  Press Backspace/Esc to go back in the breadcrumb          │
└────────────────────────────────────────────────────────────┘
```

**Implementation**:
- Maintain a `walkHistory: string[]` stack of visited node IDs
- Each click: push current to history, focus on clicked neighbor
- Backspace/Esc: pop history, refocus on previous
- Breadcrumb bar at top shows trail (clickable to jump back)

### Isolate: Regex/Filter Subgraph

Type a pattern to see ONLY matching nodes and their connections. Everything else disappears.

```
┌────────────────────────────────────────────────────────────┐
│  Filter: [adapters/.*_impl                              ]  │
│  Showing 12 nodes, 8 edges (from 5,710 total)             │
│                                                            │
│  ● log_adapter_console.py                                  │
│  ● log_adapter_fake.py                                     │
│  ● embedding_adapter_azure.py ──▶ embedding_adapter.py     │
│  ● embedding_adapter_fake.py  ──▶ embedding_adapter.py     │
│  ● embedding_adapter_local.py ──▶ embedding_adapter.py     │
│  ● file_scanner_impl.py                                    │
│  ● ast_parser_impl.py                                      │
│  ...                                                       │
│                                                            │
│  Clean, focused view of just what you searched for.        │
└────────────────────────────────────────────────────────────┘
```

**Implementation**:
- Input field with regex support
- Match against: `node_id`, `name`, `file_path`, `signature`
- `graph.filterNodes((id, attrs) => regex.test(attrs.filePath) || regex.test(attrs.label))`
- nodeReducer hides non-matching nodes
- edgeReducer shows only edges between visible nodes
- Status shows: "12 of 5,710 nodes"
- Clear button (Esc) restores full view

### Entry Points: High-Level Navigation Aids

Show nodes that are "important" by graph topology — not just size.

```
┌────────────────────────────────────────────────────────────┐
│  View: Entry Points  ·  Showing 23 nodes                  │
│                                                            │
│  ████ scan_command (in: 0, out: 12)  ← CLI entry          │
│  ███  report_command (in: 0, out: 8)                       │
│  ███  tree_command (in: 0, out: 6)                         │
│  ██   init_command (in: 0, out: 4)                         │
│                                                            │
│  Hub Nodes:                                                │
│  ████ ConfigurationService (in: 34, out: 2) ← most used   │
│  ███  GraphStore (in: 28, out: 0) ← pure consumer         │
│  ███  CodeNode (in: 45, out: 0) ← data model              │
│                                                            │
│  Click any node to enter Focus mode.                       │
└────────────────────────────────────────────────────────────┘
```

**Implementation**:
- Compute at serialization time in Python:
  - `in_degree`: count of incoming reference edges
  - `out_degree`: count of outgoing reference edges
  - `is_entry_point`: `in_degree == 0 && out_degree > 0` (nothing calls it, but it calls things)
  - `is_hub`: `in_degree > threshold` (many things depend on it)
- Filter modes: "Entry Points", "Hubs", "Leaves", "Orphans"
- Size nodes by connection count in this view

---

## Node Sizing Strategies

The current formula (`max(4, min(14, 3 + log2(lines+1)*1.5))`) sizes by code volume. This is useful but not the only dimension users care about.

### Available Strategies

| Strategy | Formula | Shows | Best For |
|----------|---------|-------|----------|
| **By lines** (default) | `max(4, min(14, 3 + log2(lines+1)*1.5))` | Code volume | Understanding file/function sizes |
| **By connections** | `max(4, min(14, 4 + log2(degree+1)*2))` | Coupling | Finding hubs, entry points |
| **By in-degree** | `max(4, min(14, 4 + in_degree*0.5))` | Dependency | What gets used most |
| **Uniform** | `6` | Nothing (all equal) | Clean topology view |

### Sizing Toggle UI

```
┌─ Size by ──────────────────────┐
│  ● Lines (default)             │
│  ○ Connections                 │
│  ○ Incoming references         │
│  ○ Uniform                     │
└────────────────────────────────┘
```

**Implementation**: Store all sizing data on each node at serialization time (`size_by_lines`, `size_by_degree`, `size_by_in_degree`). Switching strategies just changes which field the nodeReducer reads for `size`.

---

## No-Overlap Layout

The current treemap grid creates massive node overlap. Two approaches:

### Option A: Spread Within Cells (Quick Fix)

Add jitter + minimum spacing to `_layout_local_nodes()`:

```python
# Current: rigid grid → dot matrix
nx = x + (col + 0.5) * cell_w
ny = y + (row + 0.5) * cell_h

# Fixed: add spacing proportional to node size
padding = size * 1.5  # Node radius * safety margin
nx = x + padding + (col * (cell_w - padding)) / max(1, cols - 1)
```

### Option B: Force-Directed Within Treemap Cells (Better)

Use treemap for directory-level layout (macro positioning), then run a small force simulation within each cell to spread nodes apart. ForceAtlas2 is already vendored.

### Option C: Pure Force-Directed with Directory Clustering (Best Visual)

Abandon treemap positioning entirely. Use ForceAtlas2 for the whole graph with strong clustering by directory. Nodes in the same directory attract each other, different directories repel. This produces organic, readable layouts.

**RESOLVED**: Start with **Option A** (quick fix to stop overlap). Add **Option C** as a "Force Layout" toggle in a later phase. The ForceAtlas2 JS is already vendored.

---

## Search & Filter UX

### Search Bar

```
┌──────────────────────────────────────────────────────────┐
│  🔍 Search nodes...                          ⌘K or /    │
│                                                          │
│  Results:                                                │
│  ● ReportService          callable  report_service.py    │
│  ● ReportResult           type      report_service.py    │
│  ● ReportConfig           type      objects.py           │
│  ● _render_template       callable  report_service.py    │
│                                                          │
│  ↑↓ navigate  ·  Enter to focus  ·  Esc to close        │
└──────────────────────────────────────────────────────────┘
```

- Matches against: `name`, `node_id`, `file_path`, `signature`
- Fuzzy matching (substring, case-insensitive)
- Results grouped by file
- Enter → camera zooms to node + enters Focus mode
- Esc → close search, restore previous view

### Filter Panel

```
┌─ Filters ──────────────────────────────────────────────┐
│                                                        │
│  Categories:                                           │
│  [✓] callable (3,636)  [✓] type (1,060)               │
│  [✓] file (487)        [ ] block (168)                 │
│  [ ] section (23)      [ ] other (36)                  │
│                                                        │
│  Isolate: [                                    ] regex │
│                                                        │
│  Topology:                                             │
│  ○ All nodes                                           │
│  ○ Entry points (in=0, out>0)                          │
│  ○ Hubs (in>5)                                         │
│  ○ Orphans (degree=0)                                  │
│                                                        │
│  Showing: 4,696 of 5,710 nodes                         │
└────────────────────────────────────────────────────────┘
```

---

## Computed Fields (Python Serialization)

Add these to each node dict at serialization time in `report_service.py`:

```python
# After computing treemap positions, compute graph metrics
node_id_set = {n.node_id for n in nodes}
in_degree = {}   # node_id → count of incoming reference edges
out_degree = {}  # node_id → count of outgoing reference edges

for source, target, data in all_edges:
    if data.get("edge_type") == "references":
        out_degree[source] = out_degree.get(source, 0) + 1
        in_degree[target] = in_degree.get(target, 0) + 1

# Depth: count parent_node_id chain length
def compute_depth(node_id, node_map):
    depth = 0
    current = node_map.get(node_id)
    while current and current.parent_node_id:
        depth += 1
        current = node_map.get(current.parent_node_id)
    return depth

# Add to each serialized node dict
for nd in node_dicts:
    nid = nd["node_id"]
    nd["in_degree"] = in_degree.get(nid, 0)
    nd["out_degree"] = out_degree.get(nid, 0)
    nd["degree"] = nd["in_degree"] + nd["out_degree"]
    nd["depth"] = compute_depth(nid, node_map)
    nd["is_entry_point"] = nd["in_degree"] == 0 and nd["out_degree"] > 0
    nd["is_hub"] = nd["in_degree"] >= 5
    
    # Alternative sizing
    nd["size_by_lines"] = nd["size"]  # Keep original
    degree = nd["degree"]
    nd["size_by_degree"] = max(4, min(14, 4 + math.log2(degree + 1) * 2))
```

---

## Edge Display Strategy

### Current (Broken): All 4,515 edges visible

Creates amber spaghetti. Unusable.

### Proposed: Edges on Demand

| State | Edges Shown | How Many |
|-------|-------------|----------|
| **Overview** | None | 0 |
| **Drill-down** | None | 0 |
| **Focus** | Selected node's direct connections only | ~5-20 |
| **Walk** | Current + previous node connections | ~10-30 |
| **Isolate** | Edges between visible (filtered) nodes only | varies |
| **Entry points** | Optional: show outgoing edges from entry points | ~50-100 |

**Implementation** — edgeReducer:
```javascript
var focusedNode = null;
var focusedNeighbors = new Set();

renderer.setSetting('edgeReducer', function(edge, data) {
  if (!focusedNode) return null;  // No focus → no edges
  
  var source = graph.source(edge);
  var target = graph.target(edge);
  
  // Show edge only if it connects to focused node
  if (source === focusedNode || target === focusedNode) {
    return Object.assign({}, data, { hidden: false, size: 1.5 });
  }
  return null;  // Hide
});
```

---

## UI Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  [🔍 Search... ⌘K]                [View: Overview ▾] [Size: Lines ▾] │
├──────────────────────┬─────────────────────────────────────────────┤
│                      │                                             │
│  INSPECTOR           │                                             │
│  (slides in on       │          SIGMA.JS CANVAS                    │
│   node click)        │                                             │
│                      │          (full viewport)                    │
│  Name: ...           │                                             │
│  Category: ...       │                                             │
│  File: ...           │                                             │
│  Signature: ...      │                                             │
│                      │                                             │
│  ── Callers ──       │                                             │
│  • func_a            │                                             │
│  • func_b            │                                             │
│                      │                                             │
│  ── Calls ──         │                                             │
│  • func_c            │                                             │
│  • func_d            │                                             │
│                      │                                             │
│  ── Smart Content ── │                                             │
│  AI summary...       │                                             │
│                      │                                             │
├──────────────────────┴─────────────────────────────────────────────┤
│  Breadcrumb: main() → ScanPipeline → ReportService                │
├────────────────────────────────────────────────────────────────────┤
│  5,710 nodes · 4,515 refs · Showing 12 · fs2 0.1.0               │
└────────────────────────────────────────────────────────────────────┘
```

### UI Elements

| Element | Position | Behavior |
|---------|----------|----------|
| **Search bar** | Top center | `⌘K` or `/` to open, fuzzy match, Enter to focus |
| **View dropdown** | Top right | Overview, Drill-down, Entry Points, Hubs |
| **Size dropdown** | Top right | By Lines, By Connections, Uniform |
| **Inspector panel** | Left, 320px | Slides in on click, shows node details + connections |
| **Breadcrumb bar** | Bottom above status | Shows walk history, clickable to jump back |
| **Status bar** | Bottom | Node count, edge count, filter status |
| **Category legend** | Top right (existing) | Clickable to toggle categories |

---

## Keyboard Shortcuts

| Key | Action | Mode |
|-----|--------|------|
| `/` or `⌘K` | Open search | Any |
| `Esc` | Close panel / clear focus / exit mode | Any |
| `Backspace` | Go back in walk history | Walk |
| `f` | Fit graph in view | Any |
| `r` | Toggle reference edge visibility | Any |
| `1-4` | Zoom presets (25%, 50%, 100%, 200%) | Any |
| `e` | Show entry points | Any |
| `Tab` | Cycle through neighbors of focused node | Focus |

---

## Implementation Phases

This workshop informs a redesign. The implementation should be phased:

### Phase A: Fix the Basics (Critical)
1. **No-overlap layout** — add spacing to `_layout_local_nodes()`
2. **Hide all edges by default** — edgeReducer returns null unless focused
3. **Add computed fields** — in_degree, out_degree, depth, is_entry_point to serialized nodes
4. **Default view shows files only** — nodeReducer hides non-file nodes at default zoom

### Phase B: Focus + Inspector
5. **Click node → focus mode** — show neighborhood, dim everything else
6. **Inspector panel** — HTML sidebar with node details + connection lists
7. **Camera animate** — smooth zoom to focused node
8. **Edge display for focused node only** — callers/callees visible

### Phase C: Search + Filter
9. **Search bar** — `⌘K` / `/`, fuzzy match, zoom to result
10. **Category toggles** — clickable legend badges to filter
11. **Isolate by regex** — filter input, show matching subgraph

### Phase D: Walk + Advanced
12. **Walk mode** — click neighbors to traverse, breadcrumb trail
13. **Entry point / hub views** — topology-aware presets
14. **Size-by toggle** — switch between lines/connections/uniform
15. **Keyboard shortcuts**

---

## Technical Constraints

### Sigma.js 2 + Graphology (Already Vendored)

| Capability | Available | Performance |
|------------|-----------|-------------|
| nodeReducer (filter/hide) | ✅ | Instant (no rebuild) |
| edgeReducer (filter/hide) | ✅ | Instant (no rebuild) |
| camera.animate (zoom) | ✅ | 200-800ms |
| graph.neighbors() | ✅ | O(degree) |
| graph.inDegree() / outDegree() | ✅ | O(1) |
| graph.filterNodes() | ✅ | O(n) |
| setSetting() at runtime | ✅ | Instant + refresh |
| Dynamic label show/hide | ✅ | Via nodeReducer label:'' |

### What We Cannot Do (Phase 2 Stack)

| Feature | Limitation | Workaround |
|---------|-----------|------------|
| Curved edges | Needs `@sigma/edge-curve` | Straight arrows (fine for explorer) |
| Node glow/bloom | Custom WebGL shader | CSS box-shadow on HTML overlay |
| Force-directed layout | ForceAtlas2 vendored but no toggle UI | Use treemap with spacing; add FA2 later |
| HTML inside nodes | Sigma renders WebGL only | Inspector panel as HTML overlay |

---

## Open Questions

### Q1: Should Overview show directory rectangles or just file nodes?

**RESOLVED**: Start with **file nodes only** (via nodeReducer hiding non-file categories). This is simpler to implement and still provides orientation. Directory rectangles can be added later as a custom Sigma node type.

### Q2: Where does the inspector panel go?

**RESOLVED**: **Left side, 320px wide**, sliding in on node click. This matches VS Code's sidebar pattern. Closes on Esc or clicking empty canvas.

### Q3: Should we keep the treemap or switch to force-directed?

**RESOLVED**: **Keep treemap as default**, add spacing to fix overlaps. Offer force-directed as a future toggle. The treemap provides spatial coherence (same-directory nodes near each other) which is valuable for exploration.

### Q4: How to handle graphs with 50K+ nodes?

**RESOLVED**: Clustering (already implemented) reduces to `max_nodes` threshold. Plus: the Overview mode only shows ~500 file nodes regardless of total count. Focus mode shows ~5-20 neighbors. The explorer naturally caps visible elements.

---

## Quick Reference

```
VIEW MODES:
  Overview    → File nodes only, no edges, directory regions
  Drill-down  → Click directory → show its contents  
  Focus       → Click node → neighborhood + inspector
  Walk        → Click neighbor → traverse + breadcrumb
  Isolate     → Regex → matching subgraph only
  Entry Pts   → Topology filter → nodes with in_degree=0

SIZING:
  Lines       → log2(end_line - start_line + 1) * 1.5 + 3
  Connections → log2(in_degree + out_degree + 1) * 2 + 4
  Uniform     → 6

EDGES:
  Default     → HIDDEN (no spaghetti)
  Focus mode  → Show only for selected node
  Isolate     → Show between visible nodes

KEYBOARD:
  ⌘K / /     → Search
  Esc         → Clear / Back
  f           → Fit to view
  e           → Entry points
  r           → Toggle edges
```
