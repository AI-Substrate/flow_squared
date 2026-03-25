# Workshop: Report Visual Design & UX

**Type**: UX / Visual Design
**Plan**: 033-reports
**Spec**: (pending)
**Created**: 2026-03-15
**Status**: Draft

**Related Documents**:
- [006-codebase-graph-visualization.md](../../031-cross-file-rels/workshops/006-codebase-graph-visualization.md) — Technical architecture
- Research: Sigma.js 2, Catppuccin, Linear, Neo4j Bloom, Graphistry

**Constraint**: This report is a **flagship demo** for FlowSpace. It must look **gorgeous** — visual quality is a hard acceptance criterion, not a nice-to-have.

---

## Purpose

Define the exact visual language, color system, typography, animations, and interaction patterns for the codebase graph report. This document is the **implementation reference** for making it look stunning.

## Key Questions Addressed

- What color palette gives us a premium dark-mode look?
- How do nodes, edges, and labels render at different zoom levels?
- What micro-interactions make the tool feel polished?
- How does the sidebar/panel layout work?
- What does the report look like when you first open it?

---

## Design Language: "Cosmos"

Inspired by: **Linear** (clean UI), **Neo4j Bloom** (graph glow), **Catppuccin Mocha** (palette), **GitHub Copilot** (dark theme), **Obsidian** (graph view)

**Design principles:**
1. **Dark canvas, luminous data** — the graph floats in space, nodes glow
2. **Quiet chrome, loud content** — UI panels are subtle, the graph commands attention
3. **Progressive revelation** — zooming in reveals detail, zooming out shows structure
4. **Motion with purpose** — every animation communicates something

---

## Color System

### Foundation (Dark Canvas)

```css
:root {
  /* Canvas — deep blue-black, not pure black */
  --canvas: #0a0e1a;
  --canvas-elevated: #0f1422;
  --canvas-surface: #151b2b;

  /* Chrome — panels, sidebars */
  --chrome: #111827;
  --chrome-hover: #1c2539;
  --chrome-active: #253352;
  --chrome-border: #1e293b;

  /* Text */
  --text-primary: #e2e8f0;
  --text-secondary: #94a3b8;
  --text-tertiary: #64748b;
  --text-on-accent: #0f172a;
}
```

### Node Category Colors

Derived from **Catppuccin Mocha** — curated for harmony on dark backgrounds, WCAG AA accessible (≥4.5:1 contrast on `#0a0e1a`).

```css
:root {
  /* Node categories */
  --node-file: #94a3b8;        /* Slate — files are structural, not loud */
  --node-type: #c4b5fd;        /* Violet 300 — classes/types stand out */
  --node-callable: #67e8f9;    /* Cyan 300 — functions/methods are primary */
  --node-section: #a5b4fc;     /* Indigo 300 — sections are structural */
  --node-folder: #64748b;      /* Slate 500 — folders are background structure */

  /* Glow variants (30% opacity of base) */
  --glow-file: #94a3b84d;
  --glow-type: #c4b5fd4d;
  --glow-callable: #67e8f94d;
  --glow-section: #a5b4fc4d;
}
```

### Edge Colors

```css
:root {
  /* Containment edges — nearly invisible, spatial not visual */
  --edge-containment: #1e293b;
  --edge-containment-hover: #334155;

  /* Reference edges — the star of the show */
  --edge-reference: #f59e0b;          /* Amber 500 — warm, eye-catching */
  --edge-reference-glow: #f59e0b66;   /* Amber with 40% opacity */
  --edge-reference-hover: #fbbf24;    /* Amber 400 — brighter on hover */

  /* Selection state */
  --edge-selected: #38bdf8;           /* Sky 400 */
  --edge-dimmed: #0f172a;             /* Near-invisible when not relevant */
}
```

### Accent & Status

```css
:root {
  --accent: #38bdf8;          /* Sky 400 — primary interactive accent */
  --accent-glow: #38bdf833;
  --success: #4ade80;         /* Green 400 */
  --warning: #fbbf24;         /* Amber 400 */
  --error: #f87171;           /* Red 400 */
}
```

### Why These Colors

| Choice | Rationale |
|--------|-----------|
| Blue-black canvas `#0a0e1a` | Richer than pure black, reduces eye strain, makes colors pop |
| Cyan for callables | Functions are the most numerous — cyan is visible but not aggressive |
| Violet for types | Classes/types are structural landmarks — violet is distinctive but calm |
| Amber for references | Cross-file edges are the novel feature — warm amber draws the eye |
| Slate for files/folders | Structural elements should recede, not compete |

---

## Typography

### Font Stack

```css
/* UI text — clean, modern, professional */
--font-ui: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;

/* Graph labels — monospace feels like code */
--font-mono: "JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", monospace;

/* Sizes — 4px scale */
--text-2xs: 10px;    /* Zoomed-out labels, metadata */
--text-xs: 11px;     /* Node labels at default zoom */
--text-sm: 12px;     /* Sidebar metadata */
--text-base: 13px;   /* Sidebar body text */
--text-lg: 14px;     /* Sidebar headings */
--text-xl: 16px;     /* Panel titles */
--text-2xl: 20px;    /* Report header */
--text-3xl: 24px;    /* Hero title (unused in MVP) */
```

### Label Rendering Rules

| Zoom Level | Show Labels For | Font Size | Max Label Width |
|------------|----------------|-----------|-----------------|
| < 0.1 (galaxy) | Nothing | — | — |
| 0.1–0.3 (overview) | Folders only | 10px | 80px |
| 0.3–0.7 (directory) | Files + types | 11px | 120px |
| 0.7–1.5 (file) | All nodes | 12px | 160px |
| > 1.5 (detail) | All + qualified names | 13px | 240px |

### Font Loading (Self-Contained)

Embed Inter (400, 500, 600) and JetBrains Mono (400, 500) as base64 `@font-face` in the HTML. Total ~200KB — acceptable for offline-first, gorgeous rendering.

---

## Node Rendering

### Visual Hierarchy

```
┌─ ZOOM OUT ──────────────────── ZOOM IN ─┐

  ●  Dot only          ●  Dot + label
  5px                   8px + "GraphStore"

                        ◉  Dot + glow halo
                        10px + halo + "GraphStore"
                        + signature on hover

                             ◎  Full node
                             12px + glow + label
                             + smart_content tooltip
                             + edge connections visible
└─────────────────────────────────────────┘
```

### Node Sizes

Size scales with **line count** (code significance):

```javascript
function nodeSize(startLine, endLine) {
  const lines = endLine - startLine;
  // Log scale: 1-line function = 4px, 200-line class = 12px
  return Math.max(4, Math.min(14, 3 + Math.log2(lines + 1) * 1.5));
}
```

| Lines | Size | Example |
|-------|------|---------|
| 1–5 | 4px | Simple variable, short function |
| 6–20 | 6px | Typical method |
| 21–50 | 8px | Medium class method |
| 51–100 | 10px | Large function |
| 100–200 | 12px | Class with methods |
| 200+ | 14px | Major module/file |

### Node Glow Effect (WebGL)

Selected and hovered nodes get a soft **bloom glow**:

```javascript
// Sigma.js 2 custom node program (simplified)
// Outer glow ring — 1.5x node radius, 30% opacity of node color
// Renders as a radial gradient circle behind the node

const hoverGlow = {
  radius: nodeSize * 2.5,
  color: categoryColor,
  opacity: 0.15,
  blur: 8,
};

const selectedGlow = {
  radius: nodeSize * 3,
  color: '--accent',  // #38bdf8
  opacity: 0.25,
  blur: 12,
  // Subtle pulse animation
  animation: 'pulse 2s ease-in-out infinite',
};
```

### Selected Node Pulse

```css
@keyframes nodePulse {
  0%, 100% { opacity: 0.2; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(1.08); }
}
```

---

## Edge Rendering

### Reference Edges — The Hero Visual

Cross-file reference edges are the star. They should look like **energy connections** between nodes:

```
Source ● ─────────── curved ────────────── ● Target
         warm amber, slight glow,
         opacity 0.6, width 1.5px
```

**Properties:**
- **Color**: `#f59e0b` (amber) with 60% opacity
- **Width**: 1.5px default, 2.5px on hover
- **Curve**: Quadratic bezier, control point perpendicular to midpoint
- **Glow**: 4px amber blur behind the line (CSS filter or WebGL)
- **Direction indicator**: Subtle arrow at target end (triangle, 6px)

### Containment Edges — Invisible by Default

Per Workshop 006: only shown for selected node's ancestry. When visible:
- **Color**: `#1e293b` — barely visible
- **Width**: 0.5px
- **Style**: Straight line, no glow
- **Opacity**: 0.3

### Edge Hover & Selection States

```
DEFAULT:     ─── amber 60% opacity, 1.5px ───
HOVER:       ━━━ amber 100% opacity, 2.5px, glow ━━━
SELECTED:    ━━━ sky blue, 2.5px, animate in ━━━
DIMMED:      --- near invisible, 0.3px, 10% opacity ---
```

### Edge Animation on Node Selection

When a node is selected, its reference edges **animate in** with a stagger:

```javascript
// Each edge draws in from source to target over 300ms
// Staggered: 1st edge at 0ms, 2nd at 50ms, 3rd at 100ms...
const EDGE_STAGGER = 50;  // ms between each edge
const EDGE_DURATION = 300; // ms per edge animation
```

---

## Panel Layout

### First Open — Full Screen Graph

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│                                                                  │
│                      ┌──────────────────┐                        │
│                 ●────┤  ●     ●         │                        │
│            ●──●      │     ●──●──●      │                        │
│         ●      ●     └────────│─────────┘                        │
│      ●──●──●         ●───●───●                                   │
│         ●               ●                                        │
│                                                                  │
│                         Full-bleed graph canvas                  │
│                         No sidebar on first load                 │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│ fs2 · project-name · 5,635 nodes · 72 references │ ⚙ ▢ ?       │
└──────────────────────────────────────────────────────────────────┘
```

### After Clicking a Node — Sidebar Slides In

```
┌───────────────┬──────────────────────────────────────────────────┐
│               │                                                  │
│  INSPECTOR    │                                                  │
│  ───────────  │        Graph canvas (resizes smoothly)           │
│               │                                                  │
│  GraphStore   │           ●────●                                 │
│  type · 204L  │      ●──◉──────●──●                             │
│               │           ●────●                                 │
│  src/fs2/core │                                                  │
│  /repos/      │                                                  │
│  graph_store  │                                                  │
│  .py:21-225   │                                                  │
│               │                                                  │
│  ┌──────────┐ │                                                  │
│  │signature │ │                                                  │
│  │class     │ │                                                  │
│  │GraphStore│ │                                                  │
│  │(ABC):    │ │                                                  │
│  └──────────┘ │                                                  │
│               │                                                  │
│  Abstract base│                                                  │
│  class that   │                                                  │
│  defines the  │                                                  │
│  contract for │                                                  │
│  graph...     │                                                  │
│               │                                                  │
│  REFERENCED   │                                                  │
│  BY (4)       │                                                  │
│  ─────────    │                                                  │
│  ● scan.py    │                                                  │
│  ● tree.py    │                                                  │
│  ● search.py  │                                                  │
│  ● mcp.py     │                                                  │
│               │                                                  │
│  REFERENCES   │                                                  │
│  (0)          │                                                  │
│               │                                                  │
├───────────────┼──────────────────────────────────────────────────┤
│ fs2 · project │ 5,635 nodes · 72 refs │ Zoom 2.3x │ ⚙ ▢ ?     │
└───────────────┴──────────────────────────────────────────────────┘
```

### Sidebar Specs

| Property | Value |
|----------|-------|
| Width | 320px |
| Background | `--chrome` (#111827) |
| Border | 1px `--chrome-border` (#1e293b) right edge |
| Animation | Slide in from left, 250ms, `cubic-bezier(0.16, 1, 0.3, 1)` |
| Close | Click canvas or press `Esc` |
| Scrolling | Vertical scroll, thin custom scrollbar |
| Padding | 20px |

### Inspector Panel Content

```
┌─ INSPECTOR ────────────────────────────┐
│                                         │
│  ● GraphStore                    [×]    │   ← Name + close button
│  type · python · 204 lines              │   ← Category badge + language + size
│                                         │
│  src/fs2/core/repos/graph_store.py      │   ← File path (clickable? link?)
│  Lines 21–225                           │   ← Location
│                                         │
│  ┌─────────────────────────────────┐    │
│  │ class GraphStore(ABC):          │    │   ← Signature in monospace
│  └─────────────────────────────────┘    │
│                                         │
│  Abstract base class that defines the   │   ← smart_content (prose)
│  contract for persisting a code-        │
│  structure graph...                     │
│                                         │
│  ─── REFERENCED BY (4) ───────────      │   ← Incoming reference edges
│                                         │
│  ● scan.py → scan()                     │   ← Each is clickable
│  ● tree.py → TreeService.__init__       │     (navigates to that node)
│  ● search.py → SearchService.__init__   │
│  ● server.py → _get_node()             │
│                                         │
│  ─── REFERENCES (0) ──────────────      │   ← Outgoing reference edges
│                                         │
│  (none)                                 │
│                                         │
└─────────────────────────────────────────┘
```

### Category Badges

Small colored pills next to the node name:

```css
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.badge-type     { background: #c4b5fd33; color: #c4b5fd; }
.badge-callable { background: #67e8f933; color: #67e8f9; }
.badge-file     { background: #94a3b833; color: #94a3b8; }
.badge-section  { background: #a5b4fc33; color: #a5b4fc; }
```

---

## Status Bar

Fixed to bottom. Minimal, informational.

```
┌──────────────────────────────────────────────────────────────────┐
│ fs2 · project-name │ 5,635 nodes · 72 refs │ Zoom 2.3x │ ⚙ ▢ ?│
└──────────────────────────────────────────────────────────────────┘
```

```css
.status-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 32px;
  background: var(--chrome);
  border-top: 1px solid var(--chrome-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-ui);
  z-index: 100;
}

.status-bar .separator {
  color: var(--chrome-border);
  margin: 0 12px;
}
```

### Status Bar Icons (Right Side)

| Icon | Action |
|------|--------|
| ⚙ | Settings dropdown: toggle references, toggle labels, switch layout |
| ▢ | Fit graph to view |
| ? | Keyboard shortcuts overlay |

---

## Search

### Search Bar (Top Center, Floating)

Appears on `/` keypress. Floating above the graph, not in a sidebar.

```
                    ┌──────────────────────────────────┐
                    │ 🔍 Search nodes...          ⌘K  │
                    └──────────────────────────────────┘
```

```css
.search-bar {
  position: fixed;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  width: 420px;
  height: 44px;
  background: var(--chrome);
  border: 1px solid var(--chrome-border);
  border-radius: 10px;
  padding: 0 16px;
  font-size: 14px;
  color: var(--text-primary);
  font-family: var(--font-ui);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4),
              0 0 0 1px rgba(56, 189, 248, 0.1);
  backdrop-filter: blur(12px);
  z-index: 200;
  /* Animate in */
  animation: searchSlideIn 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

@keyframes searchSlideIn {
  from { opacity: 0; transform: translateX(-50%) translateY(-8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
```

### Search Results (Dropdown)

```
┌──────────────────────────────────────┐
│ 🔍 GraphStore                       │
├──────────────────────────────────────┤
│ ● GraphStore                   type │  ← Highlighted match
│   src/fs2/core/repos/graph_store.py │
│                                      │
│ ● GraphStoreError             type  │
│   src/fs2/core/adapters/exceptions  │
│                                      │
│ ● FakeGraphStore              type  │
│   src/fs2/core/repos/graph_store_f  │
│                                      │
│ ● NetworkXGraphStore          type  │
│   src/fs2/core/repos/graph_store_i  │
└──────────────────────────────────────┘
```

Selecting a result:
1. Closes search
2. Zooms camera smoothly to that node (300ms ease-out)
3. Selects the node (opens inspector)
4. Highlights its reference edges

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` or `⌘K` | Open search |
| `Esc` | Close search / deselect / close sidebar |
| `f` | Fit entire graph in view |
| `r` | Toggle reference edges visibility |
| `l` | Toggle labels |
| `1` | Zoom to overview level |
| `2` | Zoom to directory level |
| `3` | Zoom to file level |
| `4` | Zoom to detail level |
| `+` / `-` | Zoom in / out |

### Shortcuts Overlay (? key)

```
┌────────────────────────────────────────┐
│          KEYBOARD SHORTCUTS            │
│                                        │
│  Navigation                            │
│  ──────────                            │
│  / or ⌘K    Search nodes               │
│  f          Fit to view                │
│  1-4        Zoom presets               │
│  + / -      Zoom in / out              │
│                                        │
│  Display                               │
│  ──────────                            │
│  r          Toggle references          │
│  l          Toggle labels              │
│  Esc        Clear selection            │
│                                        │
│              Press any key to dismiss  │
└────────────────────────────────────────┘
```

---

## Animation Timing Reference

| Animation | Duration | Easing | Trigger |
|-----------|----------|--------|---------|
| Sidebar slide in | 250ms | `cubic-bezier(0.16, 1, 0.3, 1)` | Node click |
| Sidebar slide out | 200ms | `ease-in` | Esc / canvas click |
| Camera zoom to node | 400ms | `cubic-bezier(0.4, 0, 0.2, 1)` | Search result / dbl-click |
| Edge reveal (per edge) | 300ms | `ease-out` | Node selection |
| Edge reveal stagger | 50ms | — | Between edges |
| Node glow pulse | 2000ms | `ease-in-out` | Selected state (loop) |
| Search bar appear | 200ms | `cubic-bezier(0.16, 1, 0.3, 1)` | `/` keypress |
| Tooltip appear | 150ms | `ease-out` | Hover (after 300ms delay) |
| Label fade (LOD) | 200ms | `ease-in-out` | Zoom level change |

---

## Hover Tooltip

Appears after 300ms hover delay, positioned above/below node:

```
          ┌────────────────────────────────┐
          │ GraphStore                      │
          │ type · python · 204 lines      │
          │                                │
          │ Abstract base class that       │
          │ defines the contract for       │
          │ persisting a code-structure    │
          │ graph...                       │
          └────────────────────────────────┘
                     ▼
                     ●  ← node
```

```css
.tooltip {
  position: absolute;
  background: var(--chrome);
  border: 1px solid var(--chrome-border);
  border-radius: 8px;
  padding: 12px 16px;
  max-width: 320px;
  font-size: 12px;
  color: var(--text-primary);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  pointer-events: none;
  z-index: 300;
  animation: tooltipFadeIn 150ms ease-out;
}

.tooltip .name {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
  color: var(--accent);
  margin-bottom: 4px;
}

.tooltip .meta {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-bottom: 8px;
}

.tooltip .smart-content {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  /* Clamp to 3 lines */
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@keyframes tooltipFadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
```

---

## Settings Dropdown (⚙ icon)

```
              ┌──────────────────────────┐
              │ DISPLAY                  │
              │                          │
              │ ☑ Reference edges        │
              │ ☑ Node labels            │
              │ □ Containment edges      │
              │                          │
              │ LAYOUT                   │
              │                          │
              │ ◉ Treemap                │
              │ ○ Force-directed         │
              │                          │
              │ FILTER                   │
              │                          │
              │ ☑ Files                  │
              │ ☑ Types (classes)        │
              │ ☑ Callables (functions)  │
              │ ☑ Sections               │
              │ □ Folders                │
              └──────────────────────────┘
```

---

## Open Questions

### Q1: Should we embed fonts as base64?

**RESOLVED → Yes**. Inter (400, 500, 600) + JetBrains Mono (400, 500) add ~200KB but guarantee gorgeous text rendering regardless of the user's system fonts. For a demo piece this is non-negotiable.

### Q2: Should the graph have a loading animation?

**OPEN**: For large graphs (50K+ nodes), initial render might take 1-2s. Options:
- **A**: Show the graph immediately even if layout is computing (nodes appear, then settle)
- **B**: Show a minimal loading screen with project name + node count, then reveal graph

### Q3: Should clicking a reference in the sidebar navigate the graph?

**RESOLVED → Yes**. Clicking "scan.py → scan()" in the "REFERENCED BY" list should:
1. Smooth-zoom camera to that node (400ms)
2. Select that node (open its inspector)
3. Highlight its edges

This creates a **browsing flow** — you can walk the call graph by clicking references.

---

## Implementation Checklist

- [ ] Font embedding (Inter + JetBrains Mono as base64)
- [ ] Color system CSS variables
- [ ] Node rendering with category colors + size scaling
- [ ] Node glow/bloom effect (WebGL shader or canvas overlay)
- [ ] Edge rendering (amber curved bezier for references)
- [ ] Sidebar inspector (slide in/out animation)
- [ ] Search bar (floating, command-K style)
- [ ] Status bar (fixed bottom)
- [ ] Hover tooltips (300ms delay, smart_content preview)
- [ ] Keyboard shortcuts (/, f, r, l, 1-4, Esc)
- [ ] Settings dropdown (⚙ icon)
- [ ] Camera animations (zoom-to-node, fit-to-view)
- [ ] Edge stagger animation on selection
- [ ] LOD label rendering (zoom-dependent)
- [ ] Category badge pills
- [ ] Custom scrollbar styling (thin, subtle)
