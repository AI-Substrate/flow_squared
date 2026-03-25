# fs2 Reports: Interactive Codebase Visualization

**Mode**: Full

📚 This specification incorporates findings from [exploration.md](exploration.md) and two authoritative workshops:
- [006-codebase-graph-visualization.md](../031-cross-file-rels/workshops/006-codebase-graph-visualization.md) — Technical architecture, library selection, data pipeline
- [001-visual-design-ux.md](workshops/001-visual-design-ux.md) — Visual design language, color system, interactions, animations

## Summary

Add an `fs2 report` command group that generates self-contained interactive HTML reports from the code graph. The first report — **codebase-graph** — renders the full graph as a gorgeous, interactive WebGL visualization. Users can explore the structure of their codebase visually: zoom into directories, click nodes to see details and cross-file references, search for symbols, and walk call trees by clicking through relationships.

This is a **flagship demo feature** for FlowSpace. Visual quality is a hard acceptance criterion — the report must look stunning, not merely functional.

Reports operate on any fs2 graph file (via the existing `--graph-file` / `--graph-name` global options), making them useful for analyzing any scanned project.

## Goals

- **Visual exploration at scale**: Render codebases of 5,000–100,000+ nodes interactively at 60fps in a browser, with smooth zoom, pan, and progressive level-of-detail
- **Cross-file relationship discovery**: Visualize reference edges so users can see what calls what, trace dependencies, and understand coupling — capabilities that were invisible before cross-file rels
- **Self-contained distribution**: Generate a single HTML file with all CSS, JS, fonts, and data embedded — no server, no CDN, works offline, shareable as a file attachment
- **Call tree browsing**: Click a function → see who calls it → click a caller → see who calls *that* — enabling interactive call tree walking via the sidebar
- **Gorgeous by default**: Dark theme with curated color palette, glow effects, smooth animations, crisp typography — designed to impress in demos and presentations
- **Extensible report framework**: Establish the `fs2 report` command group pattern so future reports (dependency analysis, change impact, comparison) slot in naturally

## Non-Goals

- **Live updating / watch mode**: The report is a static snapshot. Auto-regeneration with `fs2 watch` is deferred to a future iteration
- **Comparison reports**: Reports taking two graphs (diff, before/after) are out of scope. The architecture accommodates this future need but we don't build it now
- **Code editing**: The report is read-only visualization. No editing, no write-back to source
- **Server-backed rendering**: No backend server, no API, no WebSocket. Everything runs client-side in a single HTML file
- **Mobile optimization**: Desktop browser is the primary target. Basic responsiveness is nice but not required
- **Custom branding / white-labeling**: Single "Cosmos" theme. No theming API
- **Source code display**: The report shows signatures and smart_content summaries, not full source code. Users who want source can use `fs2 get-node`

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| cli | existing | **modify** | Add `report` command, register with main app |
| services | existing | **modify** | Add `ReportService` for graph extraction + layout + rendering |
| templates | existing | **modify** | Add report HTML templates (Jinja2, following SmartContent pattern) |
| config | existing | **modify** | Add `ReportsConfig` model |
| repos | existing | **consume** | Read from `GraphStore` ABC (no changes to repo layer) |
| static-assets | **NEW** | **create** | Vendored JS/CSS/fonts for self-contained HTML |

### New Domain Sketches

#### static-assets [NEW]
- **Purpose**: Store vendored third-party assets (Sigma.js, Graphology, fonts) that get embedded into generated reports
- **Boundary Owns**: Minified JS libraries, CSS files, base64-encoded fonts, asset loading via `importlib.resources`
- **Boundary Excludes**: Report business logic (belongs to services), CLI parsing (belongs to cli), template rendering (belongs to templates)

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=2, I=1, D=0, N=1, F=1, T=1 (Total: 6)
- **Confidence**: 0.85

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 2 | Touches CLI, service, templates, config, static assets, pyproject.toml — cross-cutting |
| Integration (I) | 1 | One external dep (Sigma.js/Graphology), vendored and stable |
| Data/State (D) | 0 | Pure read-only from existing graph. No schema changes, no persistence |
| Novelty (N) | 1 | Layout algorithm (treemap) needs implementation. Sigma.js API is new territory. Workshops reduce ambiguity significantly |
| Non-Functional (F) | 1 | Must handle 100K nodes at 60fps. Visual quality is a hard requirement. File size budget matters (~1MB target) |
| Testing (T) | 1 | Integration tests needed for HTML output. WebGL rendering not unit-testable — acceptance is visual |

- **Assumptions**: Sigma.js 2 + Graphology can be vendored as minified JS (~250KB total). Treemap layout can be computed in Python in <5s for 100K nodes. Inter + JetBrains Mono fonts can be base64-embedded at ~200KB.
- **Dependencies**: Working graph (from `fs2 scan`). Cross-file reference edges (from Serena, optional but enhances value).
- **Risks**: WebGL shader customization (glow/bloom) may be complex in Sigma.js 2's renderer API. Very large graphs (100K+) may need aggressive LOD/clustering to maintain performance.
- **Phases**: (1) CLI + service + basic HTML with graph data, (2) Sigma.js rendering + interactions, (3) Visual polish + animations + LOD, (4) Documentation + edge cases

## Acceptance Criteria

### Core Report Generation

- **AC1**: Running `fs2 report codebase-graph` generates a self-contained HTML file at `.fs2/reports/codebase-graph.html`
- **AC2**: The HTML file renders in Chrome/Firefox/Safari without external dependencies (no CDN, no server)
- **AC3**: Running `fs2 report codebase-graph --output custom/path.html` writes to the specified path
- **AC4**: Running `fs2 report codebase-graph --open` opens the report in the default browser after generation
- **AC5**: The report works with any graph: `fs2 --graph-file other.pickle report codebase-graph` renders the specified graph
- **AC6**: Running `fs2 report codebase-graph` without a graph produces a clear error: "No graph found. Run `fs2 scan` first"

### Graph Visualization

- **AC7**: All nodes from the graph appear in the visualization, positioned by treemap layout (directories as spatial regions, files within directories, types within files)
- **AC8**: Nodes are colored by category: cyan for callables, violet for types, slate for files, indigo for sections
- **AC9**: Node size scales with code size (line count), using logarithmic scaling from 4px to 14px
- **AC10**: Cross-file reference edges render as curved amber lines with subtle glow
- **AC11**: Containment edges are hidden by default, shown only for the selected node's ancestry chain

### Interaction

- **AC12**: Clicking a node opens an inspector sidebar (slides in from left, 320px wide) showing: name, category badge, file path, line range, signature, smart_content, and lists of incoming/outgoing references
- **AC13**: Clicking a reference in the sidebar navigates to that node (smooth camera zoom + selects it)
- **AC14**: Hovering a node shows a tooltip after 300ms with name, category, and smart_content preview (3-line clamp)
- **AC15**: Pressing `/` or `⌘K` opens a floating search bar. Typing filters nodes by name. Selecting a result zooms to it and selects it
- **AC16**: Pressing `Esc` clears selection and closes the sidebar
- **AC17**: Pressing `f` fits the entire graph in view
- **AC18**: Pressing `r` toggles reference edge visibility

### Scale & Performance

- **AC19**: A graph with 5,000 nodes renders in under 2 seconds and maintains 60fps during interaction
- **AC20**: A graph with 50,000 nodes renders in under 5 seconds and maintains 30fps during interaction
- **AC21**: For graphs exceeding `--max-nodes` threshold, leaf nodes (methods/functions) are clustered into summary nodes to stay within budget

### Visual Quality

- **AC22**: The report uses the "Cosmos" dark theme: deep blue-black canvas (`#0a0e1a`), curated Catppuccin-inspired palette, proper visual hierarchy
- **AC23**: Typography uses embedded Inter (UI) and JetBrains Mono (labels/code) fonts — not system fonts
- **AC24**: Selected nodes have a subtle pulsing glow animation
- **AC25**: Reference edges animate in with staggered timing when a node is selected
- **AC26**: Camera movements (zoom-to-node, fit-to-view) use smooth easing animations

### CLI & Config

- **AC27**: `fs2 report --help` lists available report types
- **AC28**: `fs2 report codebase-graph --help` shows all options with descriptions
- **AC29**: Report configuration is available via `.fs2/config.yaml` under `reports:` key (output directory, default theme, smart_content inclusion)
- **AC30**: `--no-smart-content` flag excludes smart_content from the report (smaller file, faster generation)

## Risks & Assumptions

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Sigma.js 2 custom shader API may be limited for glow/bloom effects | Visual quality reduced | Fall back to CSS box-shadow overlay on a canvas layer above WebGL |
| Treemap layout for 100K nodes may take >5s in Python | Slow report generation | Cache layout positions, only recompute on graph change |
| Embedded fonts + JS + graph data may exceed 5MB for large graphs | Slow page load | Compress JSON with gzip-compatible encoding; lazy-load fonts |
| WebGL not available in some environments (SSH, headless, old browsers) | Report won't render | Show graceful fallback message: "WebGL required" |
| Sigma.js API may change between versions | Vendored version becomes stale | Pin exact version, update deliberately |

**Assumptions**:
- Users have a modern browser (Chrome 90+, Firefox 90+, Safari 15+)
- The graph has been scanned (`fs2 scan` completed at least once)
- Smart_content is optional — report works without it, just less informative tooltips
- The report is generated from the CLI, not from the MCP server (MCP integration deferred)

## Open Questions

All resolved — see Clarifications session 2026-03-15.

## Testing Strategy

- **Approach**: Hybrid
- **Rationale**: Three distinct layers need different testing approaches:
  - **TDD**: Layout algorithm (treemap computation — deterministic math), ReportService (graph extraction, JSON building), ReportsConfig (validation)
  - **Lightweight**: CLI command wiring (CliRunner smoke tests), template rendering (string assertions on HTML output), file I/O
  - **Visual acceptance**: Sigma.js rendering, animations, glow effects — verified by opening the report in a browser. Not unit-testable.
- **Focus Areas**: Layout correctness (positions, sizes, no overlaps), graph data completeness (all nodes/edges serialized), error handling (missing graph, bad config)
- **Excluded**: WebGL shader behavior, browser-specific rendering differences, animation timing precision
- **Mock Usage**: Allow targeted mocks — fakes for GraphStore (per fs2 convention with FakeGraphStore), mock only browser/WebGL boundaries if needed

## Documentation Strategy

- **Location**: Hybrid — README.md section + docs/how/user/reports-guide.md
- **README**: Add "Reports" section after "Cross-File Relationships" with quick-start: install, scan, generate, open
- **User Guide**: Detailed guide covering all options, customization, troubleshooting, scale tips

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| ~~Codebase Graph Architecture~~ | ~~Integration Pattern~~ | ~~Already completed~~ | [006-codebase-graph-visualization.md](../031-cross-file-rels/workshops/006-codebase-graph-visualization.md) ✅ |
| ~~Visual Design & UX~~ | ~~UX / Visual Design~~ | ~~Already completed~~ | [001-visual-design-ux.md](workshops/001-visual-design-ux.md) ✅ |
| Treemap Layout Algorithm | Data Model | Squarified treemap implementation in Python — strip vs. squarify, handling nested hierarchy (directory→file→class→method), edge case for empty directories | How deep does nesting go? What minimum cell size before collapsing? |

## Clarifications

### Session 2026-03-15

**Q1: Workflow Mode** → **Full Mode**. Multi-phase plan, required dossiers, all gates. CS-3 complexity warrants full planning.

**Q2: Testing Strategy** → **Hybrid**. TDD for layout algorithm + service logic (deterministic, testable). Lightweight for CLI/template wiring. Visual acceptance for rendering (browser-verified, not unit-testable).

**Q3: Mock Usage** → **Allow targeted mocks**. Fakes for GraphStore (per fs2 convention). Mock only browser/WebGL boundaries if needed.

**Q4: Documentation Strategy** → **Hybrid**. README.md section for quick-start + `docs/how/user/reports-guide.md` for detailed guide.

**Q5: Domain Review** → **Approved as-is**. `static-assets` proceeds as a new domain area at `src/fs2/core/static/reports/`. Existing domains (cli, services, templates, config) modified. Repos consumed read-only. No boundary concerns.

**Q6: OQ1 — Layout Toggle** → **Runtime toggle in ⚙ settings dropdown**. Users can switch between treemap and force-directed (ForceAtlas2) in the browser without regenerating. Requires embedding ForceAtlas2 JS (~50KB extra). Both layout positions precomputed would be too expensive; force-directed runs client-side on toggle.

**Q7: OQ2 — LOD Computation** → **JS render-time**. Python pipeline stays simple (emit all nodes with category metadata). JS filters visible nodes based on zoom ratio + category. ~20 lines of JS, no generation-time bucketing needed.

**Q8: OQ3 — Loading Animation** → **Loading screen with reveal**. Show project name + node/edge stats on a dark screen, then fade-reveal the graph. Creates a polished first impression for demo scenarios. Always shown (not just for large graphs) — consistent UX.
