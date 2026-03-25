# Fix FX001: Unusable visualization — layout overlap, edge spaghetti, no progressive disclosure

**Created**: 2026-03-15
**Status**: Proposed
**Plan**: [reports-plan.md](../reports-plan.md)
**Source**: User feedback — screenshot shows dot-matrix grid, amber edge spaghetti, 5,710 nodes dumped simultaneously with no hierarchy. Report is unusable for codebase exploration.
**Domain(s)**: services (report_service.py, report_layout.py), static-assets (graph-viewer.js, graph-viewer.css), templates (codebase_graph.html.j2)

---

## Problem

The Phase 2 report visualization is unusable. Three compounding issues:
1. **Node overlap** — the grid layout in `_layout_local_nodes()` packs nodes into a uniform matrix with no spacing, creating a dot-matrix pattern where nodes overlap at any zoom level.
2. **Edge spaghetti** — all 4,515 reference edges render simultaneously as amber lines, creating an impenetrable tangle that obscures the graph structure.
3. **No progressive disclosure** — all 5,710 nodes are visible at the same zoom level with no hierarchy. There is no way to orient yourself, drill down, or focus on a specific area.

Per Workshop 002 (Codebase Explorer UX), these are the "Phase A: Fix the Basics" items that must be resolved before any interaction features make sense.

## Proposed Fix

Four surgical changes that transform the report from a data dump into a usable starting point:
1. **Fix layout spacing** — add padding between directory regions and minimum spacing between nodes in `report_layout.py` so nothing overlaps.
2. **Hide all edges by default** — change `graph-viewer.js` to start with edges hidden; only show edges for a clicked/focused node's direct connections.
3. **Add computed graph metrics** — serialize `in_degree`, `out_degree`, `depth`, `is_entry_point` on each node in `report_service.py` so JS can filter by topology.
4. **Default to file-level overview** — `graph-viewer.js` starts by showing only `category: "file"` nodes (via nodeReducer), hiding callables/types/blocks. Click a file to reveal its contents.

## Domain Impact

| Domain | Relationship | What Changes |
|--------|-------------|-------------|
| services | **modify** | `report_layout.py`: padding + spacing in `_layout_local_nodes()` and `_layout_rect()`. `report_service.py`: compute + serialize degree/depth fields. |
| static-assets | **modify** | `graph-viewer.js`: edgeReducer (hide by default, show on focus), nodeReducer (file-level overview), click-to-reveal. `graph-viewer.css`: minor style for focus state. |
| templates | **no change** | Template doesn't need changes — data contract is additive (new node fields). |

## Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [ ] | FX001-1 | Add padding + spacing to treemap layout | services | `src/fs2/core/services/report_layout.py` | Nodes don't overlap when rendered. Directory regions have visible gaps between them. Grid cells have minimum spacing proportional to node size. Tests still pass (update expected positions). | Current `_layout_local_nodes()` uses rigid grid with zero padding. Add `_CELL_PADDING = 0.1` fraction and `_MIN_NODE_SPACING` to prevent overlap. Also add padding in `_layout_rect()` between directory subdivisions. |
| [ ] | FX001-2 | Compute and serialize graph metrics | services | `src/fs2/core/services/report_service.py` | Each serialized node dict gains `in_degree`, `out_degree`, `degree`, `depth`, `is_entry_point` fields. Existing tests unbroken, new tests cover degree computation. | Iterate edges to build degree maps. Traverse `parent_node_id` chains for depth. `is_entry_point = in_degree == 0 and out_degree > 0 and category == "callable"`. Add `size_by_degree` alternative sizing field. |
| [ ] | FX001-3 | Hide edges by default, show on focus | static-assets | `src/fs2/core/static/reports/graph-viewer.js`, `src/fs2/core/static/reports/graph-viewer.css` | Report opens with zero edges visible. Clicking a node shows only that node's direct connections (callers + callees). Clicking canvas clears focus and hides edges again. | Use `renderer.setSetting('edgeReducer', ...)` — return null unless edge connects to `focusedNode`. Use `graph.inbound(id)` / `graph.outbound(id)` from Graphology. Add `clickNode` + `clickStage` event handlers. Dim non-neighbor nodes to 0.15 opacity via nodeReducer. |
| [ ] | FX001-4 | Default to file-level overview | static-assets | `src/fs2/core/static/reports/graph-viewer.js` | On open, only `category: "file"` nodes are visible (~500 nodes instead of 5,710). Clicking a file node reveals its children (classes, functions). Clicking canvas background returns to file-level overview. | nodeReducer returns null for non-file nodes in overview mode. On `clickNode` where `category === "file"`: switch to showing that file's children (nodes where `filePath` matches and `parentNodeId` starts with the file's `nodeId`). Track `viewMode: "overview" | "file-contents" | "focus"` state. |

## Workshops Consumed

- [002-codebase-explorer-ux.md](../workshops/002-codebase-explorer-ux.md) — Phase A: Fix the Basics

## Acceptance

- [ ] Report opens showing ~500 file nodes with no overlap
- [ ] No edges visible on initial load
- [ ] Clicking a file reveals its contents (classes, functions)
- [ ] Clicking a function shows only its direct callers/callees as edges
- [ ] Clicking empty canvas resets to file-level overview
- [ ] Existing tests pass (layout test positions updated if needed)
- [ ] New tests cover degree computation

## Discoveries & Learnings

_Populated during implementation._

| Date | Task | Type | Discovery | Resolution |
|------|------|------|-----------|------------|
