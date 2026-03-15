# fs2 Reports Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-03-15
**Spec**: [reports-spec.md](reports-spec.md)
**Status**: READY
**Mode**: Full

## Summary

fs2 has no report generation capability. This plan adds an `fs2 report` command group with `codebase-graph` as the first report type — a self-contained interactive HTML file that renders the full code graph (nodes + containment + cross-file reference edges) using Sigma.js 2 (WebGL). The report must look **gorgeous** — this is a flagship FlowSpace demo.

The implementation follows fs2's Clean Architecture: CLI command → ReportService → Jinja2 templates + vendored static assets. All graph data comes from the existing GraphStore ABC (read-only). Zero new Python dependencies. Layout is precomputed in Python (treemap), rendering happens client-side in WebGL.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| cli | existing | **modify** | Add `report` command group (Typer subapp, doctor pattern) |
| services | existing | **modify** | Add `ReportService` for data extraction + layout + rendering |
| templates | existing | **modify** | Add report HTML templates (Jinja2, SmartContent pattern) |
| config | existing | **modify** | Add `ReportsConfig` model |
| repos | existing | **consume** | Read from GraphStore ABC — no changes |
| static-assets | **NEW** | **create** | Vendored Sigma.js, Graphology, fonts for self-contained HTML |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/cli/report.py` | cli | internal | CLI command group entry point |
| `src/fs2/cli/main.py` | cli | internal | Register report command (1 line) |
| `src/fs2/core/services/report_service.py` | services | internal | Graph extraction + treemap layout + HTML rendering |
| `src/fs2/core/services/report_layout.py` | services | internal | Squarified treemap algorithm |
| `src/fs2/config/objects.py` | config | internal | Add ReportsConfig class |
| `src/fs2/core/templates/reports/codebase_graph.html.j2` | templates | internal | HTML template with Jinja2 placeholders |
| `src/fs2/core/static/reports/__init__.py` | static-assets | contract | Package marker for importlib.resources |
| `src/fs2/core/static/reports/sigma.min.js` | static-assets | internal | Vendored Sigma.js 2 |
| `src/fs2/core/static/reports/graphology.min.js` | static-assets | internal | Vendored Graphology |
| `src/fs2/core/static/reports/graphology-layout-forceatlas2.min.js` | static-assets | internal | Vendored ForceAtlas2 for runtime toggle |
| `src/fs2/core/static/reports/graph-viewer.js` | static-assets | internal | Our interaction code (search, sidebar, LOD, keyboard) |
| `src/fs2/core/static/reports/graph-viewer.css` | static-assets | internal | Cosmos dark theme styles |
| `src/fs2/core/static/reports/inter.woff2` | static-assets | internal | Embedded Inter font |
| `src/fs2/core/static/reports/jetbrains-mono.woff2` | static-assets | internal | Embedded JetBrains Mono font |
| `pyproject.toml` | config | cross-domain | Add static asset paths to wheel include |
| `README.md` | — | cross-domain | Add Reports section |
| `docs/how/user/reports-guide.md` | — | cross-domain | Detailed user guide |
| `tests/unit/cli/test_report_cli.py` | — | — | CLI tests |
| `tests/unit/services/test_report_service.py` | — | — | Service tests |
| `tests/unit/services/test_report_layout.py` | — | — | Layout algorithm tests |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `pyproject.toml` only includes `.j2`, `.yaml`, `.md` — vendored JS/CSS/fonts will be silently excluded from wheel builds | Add `.js`, `.css`, `.woff2` patterns to `[tool.hatch.build]` in Phase 1. Add validation test. |
| 02 | Critical | At 100K nodes, JSON blob is ~31MB — browsers choke parsing that in a `<script>` tag | Set `--max-nodes` default at 10,000. Cluster leaf nodes above threshold. Warn user in CLI output. |
| 03 | High | `webbrowser.open()` fails silently on headless/SSH — no precedent in codebase | Wrap in try/except, print file path as fallback. Document limitation. |
| 04 | High | TemplateService pattern from SmartContent is directly reusable — `importlib.resources` + `DictLoader` | Reuse pattern, don't reinvent. Load report templates separately from SmartContent templates. |
| 05 | High | Doctor command group (`doctor_app = typer.Typer()`) shows exact registration pattern needed | Follow doctor.py pattern for `reports_app`. |
| 06 | High | `safe_write_file()` + `validate_save_path()` already handle file output safely | Reuse directly — no new file I/O code needed. |

## Harness Strategy

Harness: Not applicable. No harness exists and the feature is a CLI-to-file-output pipeline with visual acceptance testing (open HTML in browser). Standard `CliRunner` tests suffice.

## Phases

### Phase Index

| Phase | Title | Primary Domain | Objective (1 line) | Depends On | CS |
|-------|-------|---------------|-------------------|------------|-----|
| 1 | Foundation — Config, CLI, Service skeleton | cli + config | Wire up `fs2 report codebase-graph` to produce a minimal HTML file with graph JSON data | None | CS-2 |
| 2 | Layout + Rendering — Treemap, Sigma.js, Cosmos theme | services + static-assets | Compute treemap layout in Python, embed Sigma.js rendering with Cosmos dark theme | Phase 1 | CS-3 |
| 3 | Interactions — Sidebar, search, keyboard, animations | static-assets | Add inspector sidebar, search bar, keyboard shortcuts, edge animations, LOD zoom | Phase 2 | CS-3 |
| 4 | Polish + Documentation | — | Visual refinement, clustering for large graphs, README, user guide, edge cases | Phase 3 | CS-2 |

---

### Phase 1: Foundation — Config, CLI, Service Skeleton

**Objective**: Wire up `fs2 report codebase-graph` end-to-end to produce a valid HTML file with graph data — even if it's not pretty yet.
**Domain**: cli, config, services, templates
**Delivers**:
- `ReportsConfig` model in config/objects.py
- `fs2 report codebase-graph` CLI command with `--output`, `--open`, `--no-smart-content` flags
- `ReportService` that extracts nodes/edges from GraphStore and renders a basic HTML file
- Minimal HTML template (just graph JSON in a `<pre>` tag or basic table — rendering comes in Phase 2)
- `pyproject.toml` updated with static asset paths
- Static assets package marker (`__init__.py`)
**Depends on**: None
**Key risks**: pyproject.toml wheel packaging (Finding 01)

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 1.1 | Add `ReportsConfig` to config/objects.py | config | Config loads from YAML `reports:` section with `output_dir`, `include_smart_content`, `max_nodes` fields. Validation passes. | Follow CrossFileRelsConfig pattern |
| 1.2 | Create `src/fs2/core/static/reports/__init__.py` and update `pyproject.toml` with static asset include patterns | static-assets | `importlib.resources.files('fs2.core.static.reports')` resolves after `pip install -e .`. Wheel includes `.js`, `.css`, `.woff2` patterns. | Finding 01 — critical |
| 1.3 | Create `ReportService` skeleton with `generate_codebase_graph()` method | services | Service accepts `ConfigurationService` + `GraphStore`, calls `get_all_nodes()` + `get_all_edges()`, returns `ReportResult` dataclass with HTML string + metadata | DI pattern per TreeService |
| 1.4 | Create minimal Jinja2 HTML template at `src/fs2/core/templates/reports/codebase_graph.html.j2` | templates | Template renders with `{{ graph_json }}` placeholder. Output is valid HTML with embedded JSON. | Follow SmartContent template_service.py pattern |
| 1.5 | Create `src/fs2/cli/report.py` with `reports_app` Typer group and `codebase-graph` subcommand | cli | `fs2 report codebase-graph` generates HTML file. `--output` works. `--open` wraps `webbrowser.open()` with try/except fallback. Error on missing graph. | Follow doctor.py pattern. Finding 03, 05, 06 |
| 1.6 | Register `reports_app` in `src/fs2/cli/main.py` | cli | `fs2 report --help` lists available report types. Command requires init. | Single line addition |
| 1.7 | Tests: ReportsConfig validation, ReportService extraction, CLI smoke tests | — | Config tests pass. Service returns HTML with all node_ids present. CLI exit codes correct (0 success, 1 missing graph). | Hybrid: TDD for config/service, lightweight for CLI |

### Acceptance Criteria (Phase 1)
- [x] AC1: `fs2 report codebase-graph` generates HTML file at default path
- [x] AC3: `--output custom/path.html` writes to specified path
- [x] AC4: `--open` opens browser (with graceful fallback on headless)
- [x] AC5: `--graph-file` works via global options
- [x] AC6: Missing graph produces clear error
- [x] AC27: `fs2 report --help` lists report types
- [x] AC28: `fs2 report codebase-graph --help` shows all options
- [x] AC29: ReportsConfig available in config.yaml
- [x] AC30: `--no-smart-content` excludes smart_content from output

### Risks (Phase 1)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| pyproject.toml static paths wrong | Medium | Assets missing from wheel | Validation test in T1.2 |
| Template loading fails in wheel | Low | Reports crash | Test with `pip install -e .` in T1.2 |

---

### Phase 2: Layout + Rendering — Treemap, Sigma.js, Cosmos Theme

**Objective**: Replace the skeleton HTML with a real interactive graph visualization using Sigma.js 2, treemap layout, and the Cosmos dark theme.
**Domain**: services (layout), static-assets (JS/CSS/fonts)
**Delivers**:
- Squarified treemap layout algorithm in Python
- Vendored Sigma.js 2 + Graphology + ForceAtlas2 JS
- Cosmos dark theme CSS (from Workshop 001)
- Graph rendering with category-colored nodes, sized by line count
- Reference edges as curved amber lines
- Loading screen with fade-reveal
- Embedded Inter + JetBrains Mono fonts
**Depends on**: Phase 1
**Key risks**: Sigma.js API learning curve. Layout correctness for nested hierarchy. JSON size for large graphs (Finding 02).

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 2.1 | Implement squarified treemap layout in `report_layout.py` | services | Given nodes grouped by directory, produces `(x, y, size)` positions. No overlaps. Deterministic. TDD: 5+ test cases including empty dirs, single-file dirs, deep nesting. | TDD — this is pure math |
| 2.2 | Node serialization: build Sigma.js-compatible JSON from CodeNode list | services | JSON contains `id`, `label`, `x`, `y`, `size`, `color`, `category`, `file`, `lines`, `signature`, `smart_content` per node. No embedding leak (per PL-03). | Explicit field selection, never asdict() |
| 2.3 | Edge serialization: containment + reference edges as Sigma.js edge JSON | services | Edges have `source`, `target`, `type` ("containment" or "references"), `color`. Reference edges get amber color. | |
| 2.4 | Vendor Sigma.js 2, Graphology, ForceAtlas2 into `src/fs2/core/static/reports/` | static-assets | Files exist, loadable via importlib.resources. Total ~300KB minified. | Download from npm/CDN, pin version |
| 2.5 | Create `graph-viewer.css` — Cosmos dark theme | static-assets | CSS implements color system from Workshop 001. Canvas `#0a0e1a`, chrome `#111827`, category colors, status bar, badge styles. | Per Workshop 001 visual-design-ux.md |
| 2.6 | Create `graph-viewer.js` — Sigma.js initialization + basic rendering | static-assets | JS loads graph JSON, creates Sigma renderer, renders nodes + edges on WebGL canvas. Zoom/pan works. | Core rendering — no interactions yet |
| 2.7 | Embed Inter + JetBrains Mono fonts as base64 woff2 in CSS | static-assets | Fonts render correctly in the report. No system font fallback visible. | ~200KB total |
| 2.8 | Loading screen with fade-reveal | static-assets | On open: show project name + node/edge counts on dark screen. After Sigma init, fade-reveal graph over 400ms. | Per clarification Q8 |
| 2.9 | Update HTML template to embed all JS/CSS/fonts + graph JSON | templates | Template inlines all vendored assets. Output is single self-contained HTML. Works offline. | Jinja2 `{{ sigma_js }}` etc. |
| 2.10 | Node clustering for `--max-nodes` threshold | services | When node count exceeds threshold (default 10,000), leaf callable nodes grouped by file into summary nodes. Warning printed to CLI. | Finding 02 — prevents 31MB JSON |

### Acceptance Criteria (Phase 2)
- [x] AC2: HTML renders in Chrome/Firefox/Safari without external dependencies
- [x] AC7: All nodes positioned by treemap layout
- [x] AC8: Nodes colored by category
- [x] AC9: Node size scales with line count (log scale, 4-14px)
- [x] AC10: Reference edges render as curved amber lines with glow
- [x] AC19: 5K nodes renders in <2s, 60fps
- [x] AC20: 50K nodes renders in <5s, 30fps
- [x] AC21: Clustering above `--max-nodes`
- [x] AC22: Cosmos dark theme with correct colors
- [x] AC23: Embedded Inter + JetBrains Mono fonts

### Risks (Phase 2)

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Treemap produces overlapping nodes | Medium | Visual mess | TDD with edge cases in T2.1 |
| Sigma.js custom edge rendering (curved + glow) complex | Medium | Amber edges look flat | Fall back to straight amber edges, add glow in Phase 3 |
| 31MB JSON for 100K nodes | High | Browser OOM | T2.10 clustering mitigates. Default max 10K. |

---

### Phase 3: Interactions — Sidebar, Search, Keyboard, Animations

**Objective**: Add all interactive features that make the report feel premium — sidebar inspector, search, keyboard shortcuts, edge animations, LOD zoom.
**Domain**: static-assets (JS/CSS)
**Delivers**:
- Inspector sidebar (slide-in on node click)
- Reference browsing (click reference → navigate to node)
- Floating search bar (command-K style)
- Keyboard shortcuts (/, f, r, l, Esc, 1-4)
- Edge stagger animation on selection
- Node glow pulse on selection
- LOD zoom (category-based node filtering)
- Settings dropdown (⚙ — toggle refs, labels, layout mode)
- Hover tooltips (300ms delay, smart_content preview)
- Containment edges on selected node's ancestry
**Depends on**: Phase 2
**Key risks**: JS complexity. Sigma.js event API learning curve.

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 3.1 | Inspector sidebar — HTML structure + slide animation | static-assets | Click node → sidebar slides in (250ms) showing name, badge, file, lines, signature, smart_content, reference lists. Esc closes. | Per Workshop 001 layout spec |
| 3.2 | Reference navigation — click reference to navigate | static-assets | Click "scan.py → scan()" in sidebar → camera zooms to that node (400ms ease), selects it, updates sidebar. | AC13 — enables call tree browsing |
| 3.3 | Hover tooltips | static-assets | 300ms hover delay → tooltip with name, category badge, smart_content (3-line clamp). Positioned above node. | AC14 |
| 3.4 | Floating search bar | static-assets | `/` or `⌘K` → search bar appears (200ms slide-in). Type to filter nodes. Arrow keys to navigate results. Enter to zoom + select. | AC15 |
| 3.5 | Keyboard shortcuts | static-assets | `Esc` clears, `f` fits, `r` toggles refs, `l` toggles labels, `1-4` zoom presets. `?` shows overlay. | AC16-18 |
| 3.6 | Edge stagger animation | static-assets | On node select, reference edges animate in one-by-one (300ms each, 50ms stagger). Amber → bright. | AC25 |
| 3.7 | Node glow pulse | static-assets | Selected node gets pulsing glow (2s cycle, ease-in-out). Uses category color at 25% opacity. | AC24 |
| 3.8 | LOD zoom filtering | static-assets | Zoom out → hide callables, show only files/types. Zoom further → show only folders. Zoom in → show all. Smooth label transitions. | JS render-time per clarification Q7 |
| 3.9 | Settings dropdown (⚙) | static-assets | Toggle: reference edges, labels, containment edges. Layout switch: treemap ↔ force-directed (ForceAtlas2 runs client-side). | Per clarification Q6 |
| 3.10 | Containment edge display for selected node | static-assets | When a node is selected, show its file→class→method ancestry chain as faint edges. Hidden otherwise. | AC11 |
| 3.11 | Smooth camera animations | static-assets | zoom-to-node (400ms), fit-to-view (300ms), zoom presets (250ms). All use cubic-bezier easing. | AC26 |

### Acceptance Criteria (Phase 3)
- [x] AC11: Containment edges for selected ancestry only
- [x] AC12: Inspector sidebar with all fields
- [x] AC13: Reference navigation
- [x] AC14: Hover tooltips
- [x] AC15: Search bar
- [x] AC16: Esc clears
- [x] AC17: `f` fits
- [x] AC18: `r` toggles references
- [x] AC24: Node glow pulse
- [x] AC25: Edge stagger animation
- [x] AC26: Smooth camera animations

---

### Phase 4: Polish + Documentation

**Objective**: Visual refinement, edge cases, documentation, final QA.
**Domain**: cross-domain
**Delivers**:
- Visual polish pass (spacing, colors, transitions reviewed)
- Edge case handling (empty graph, no references, no smart_content)
- README.md Reports section
- `docs/how/user/reports-guide.md` detailed user guide
- Final test pass
**Depends on**: Phase 3
**Key risks**: None — all technical work done.

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 4.1 | Edge case handling | services + static-assets | Empty graph shows "No nodes found" message. Graph with no reference edges shows info message. Missing smart_content gracefully hidden in tooltips/sidebar. | |
| 4.2 | Visual polish pass | static-assets | Review all colors against Workshop 001 spec. Check font rendering. Verify animation timings. Fix any spacing issues. | Visual acceptance |
| 4.3 | README.md — add Reports section | — | Quick-start section after "Cross-File Relationships": install, scan, generate, open. | Per clarification Q4 |
| 4.4 | `docs/how/user/reports-guide.md` | — | Detailed guide: all CLI options, config YAML, scale tips, troubleshooting, screenshots. | Per clarification Q4 |
| 4.5 | Full test suite pass | — | All existing tests pass. New report tests pass. Lint clean. | `uv run python -m pytest -q` + `uv run ruff check` |

### Acceptance Criteria (Phase 4)
- [x] All 30 acceptance criteria from spec verified
- [x] README updated
- [x] User guide published
- [x] Zero test regressions

## Testing Strategy

- **Approach**: Hybrid
- **TDD**: Layout algorithm (treemap — deterministic math), ReportsConfig (validation), ReportService (data extraction)
- **Lightweight**: CLI command wiring (CliRunner smoke tests), template rendering (string assertions)
- **Visual acceptance**: Sigma.js rendering, animations, theme — verified by opening report in browser
- **Mock usage**: FakeGraphStore for service tests. No mocks for browser/WebGL — visual acceptance only.
- **Fixtures**: Use `scanned_fixtures_graph` from conftest.py for CLI integration tests. Create small fixture graph for layout unit tests.
