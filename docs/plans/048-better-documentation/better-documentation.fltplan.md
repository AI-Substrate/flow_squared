# ✈️ Flight Plan — Better Documentation

**Plan**: `048-better-documentation`
**Status**: Ready
**Complexity**: CS-2 (small)
**Spec**: [better-documentation-spec.md](better-documentation-spec.md)
**Plan**: [better-documentation-plan.md](better-documentation-plan.md)
**Workshop**: [001-selling-the-premise.md](workshops/001-selling-the-premise.md)
**Research**: [research-dossier.md](research-dossier.md)

---

## Mission

Rewrite the fs2 README so newcomers understand what fs2 does before they see an installation command.

## Before → After

### Before

```
README.md (457 lines)
├── Title + 1-line tagline              ← vague
├── Installation (63 lines)             ← too early
├── Guides table (6 entries)            ← incomplete
├── Quick Diagnostics (34 lines)       ← fine
├── MCP setup (134 lines)              ← over-detailed
├── Scanning (40 lines)                ← mechanics only
├── Embeddings (27 lines)              ← duplicates config guide
├── Cross-File Rels (58 lines)         ← duplicates guide
├── Language Support (24 lines)        ← good
├── Canonical Example (4 lines)        ← developer concern
└── Developer Setup (57 lines)         ← good
```

**Problem**: Value proposition is absent. Reader reaches line 6 and sees `## Installation` without knowing what they're installing.

### After

```
README.md (~352 lines — ~105 lines shorter)
├── Title + opening paragraph           ← what fs2 does (3-5 sentences)
├── Key Capabilities (5 blocks)         ← NEW: structural parsing, AI summaries,
│                                          semantic search, cross-file, multi-repo
├── How It Works (6-step pipeline)      ← NEW: scan → parse → summarize → embed → relate → store
├── When to Use fs2 (comparison table)  ← NEW: fs2 vs grep/ripgrep
├── Quick Start (63 lines)             ← MOVED DOWN, renamed from Installation
├── Guides table (9+ entries)          ← EXPANDED from 6
├── Quick Diagnostics (34 lines)       ← unchanged
├── MCP setup (~40 lines)             ← TRIMMED from 134
├── Scanning (~15 lines)              ← TRIMMED from 40
├── Language Support (24 lines)        ← unchanged
└── Developer Setup (~58 lines)        ← Canonical Example merged in
```

**Result**: Newcomer knows what fs2 does, why it's interesting, and when to use it — all before installation. README is ~100 lines shorter.

## Phases

| # | Phase | Tasks | Objective |
|---|-------|-------|-----------|
| 1 | Write New Sections | 5 tasks | Opening paragraph, Key Capabilities, How It Works (Scan→Parse→Relate→Summarize→Embed→Store), When to Use, semantic search example |
| 2 | Restructure & Trim | 9 tasks | Reorder, rename Installation, trim MCP/Scanning/Embeddings/Cross-File, expand Guides, line count check |

## Key Decisions (from Workshop 001)

- **Tone**: Senior engineer over coffee — confident, technical, no adjectives
- **Opening**: Option A (factual: "parses → enriches → searches")
- **Pipeline**: Numbered list (not Mermaid diagram)
- **Comparison**: Respects grep/ripgrep as complementary tools
- **Multi-repo**: Use cases first, not repo counts
- **Golden rule**: Remove all adjectives — if it still sounds impressive, it's correct

## Line Budget

| | Current | Target | Δ |
|--|---------|--------|---|
| New sections | 2 | 81 | +79 |
| Existing (trimmed) | 452 | 259 | -193 |
| Spacing | 3 | 12 | +9 |
| **Total** | **457** | **~352** | **~-105** |

## Flight Log

| Date | Event |
|------|-------|
| 2026-04-13 | Research dossier created (8 agents, 62 findings) |
| 2026-04-13 | Workshop 001 completed (tone, structure, content decisions) |
| 2026-04-13 | Spec created (12 acceptance criteria) |
| 2026-04-13 | Plan created (2 phases, 14 tasks) |
| 2026-04-14 | Validation: 4 HIGHs found & fixed (pipeline order, AC-06, section ordering) |
| 2026-04-14 | **Phase 1 complete**: 5 tasks, 7 ACs passed, ~60 lines of new content in README |
