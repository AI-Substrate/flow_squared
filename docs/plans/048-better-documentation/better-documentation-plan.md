# Better Documentation — Implementation Plan

**Plan Version**: 1.0.0
**Created**: 2026-04-13
**Spec**: [better-documentation-spec.md](better-documentation-spec.md)
**Workshop**: [001-selling-the-premise.md](workshops/001-selling-the-premise.md)
**Research**: [research-dossier.md](research-dossier.md)
**Status**: DRAFT

---

## Summary

The fs2 README opens with a vague one-liner then jumps to installation on line 6 — it never explains what fs2 does, why it exists, or what makes it interesting. This plan restructures `README.md` into a value-first document: opening paragraph → key capabilities → pipeline explanation → comparison table → installation → reference material. New sections are written following the tone and content decisions from Workshop 001 ("senior engineer over coffee" — confident, technical, no adjectives doing the heavy lifting). Existing sections are trimmed where content is already covered in dedicated guides. The final README will be ≤ 457 lines.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| documentation | conceptual | modify | `README.md` is the primary artifact; guides are referenced, not modified |

> No formal domain registry exists. This feature is documentation-only.

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `/Users/jordanknight/substrate/fs2/048-better-documentation/README.md` | documentation | internal | Primary (and only) file modified |

## Harness Strategy

Harness: Not applicable. This is a documentation-only change — no code to boot, interact with, or observe.

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | High | No external links reference README heading anchors — restructuring anchors is safe | Proceed with section reordering without redirect concerns |
| 02 | High | README Guides table shows 6 of 11 available user guides — 5 are hidden | Phase 2 expands table to show all relevant guides |
| 03 | High | Current MCP section is 134 lines — most content duplicates `mcp-server-guide.md` | Phase 2 trims to setup-only (~40 lines) |
| 04 | Medium | Embeddings section (27 lines) fully covered by `configuration-guide.md` | Phase 2 removes section, references config guide |
| 05 | Medium | Cross-File Relationships section (58 lines) duplicates `cross-file-relationships.md` | Phase 2 trims to 5-line summary + link |
| 06 | Medium | Workshop resolved: Option A opening (factual pipeline), numbered pipeline list, comparison table respecting grep/ripgrep | Phase 1 implements these decisions directly |
| 07 | Low | OQ-02 (Canonical Example section) — developer concern, not user concern | Phase 2 merges into Developer Setup |
| 08 | Low | OQ-03 (Quick Diagnostics section) — short and practical | Phase 2 keeps it in place |

## Phases

### Phase Index

| Phase | Title | Primary Domain | Objective (1 line) | CS | Depends On |
|-------|-------|---------------|-------------------|----|------------|
| 1 | Write New Sections | documentation | Add opening paragraph, Key Capabilities, How It Works, When to Use fs2 | CS-1 | None |
| 2 | Restructure & Trim | documentation | Reorder sections, trim duplicates, expand guides table, integrate examples | CS-1 | Phase 1 |

**Overall Complexity**: CS-2 (small). S=1 I=0 D=0 N=1 F=0 T=0.

---

### Phase 1: Write New Sections

**Objective**: Write the four new README sections that establish fs2's value proposition.
**Domain**: documentation
**Delivers**:
- Opening paragraph (3-5 sentences explaining what fs2 does)
- "Key Capabilities" section (5 feature blocks, 2-3 sentences each)
- "How It Works" section (6-step numbered pipeline list)
- "When to Use fs2" section (comparison table with 7+ rows)
- Semantic search "aha moment" example
**Depends on**: None
**Key risks**: Tone — the golden rule from Workshop 001 applies: "remove all adjectives, if it still sounds impressive, you've written it correctly"

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 1.1 | Write opening paragraph | documentation | 3-5 sentences; reader can explain what fs2 does after reading it; mentions parse → enrich → search pipeline and both CLI/MCP audiences | Workshop Option A: factual pipeline description |
| 1.2 | Write "Key Capabilities" section | documentation | Exactly 5 blocks: structural parsing, AI-generated summaries, semantic search, cross-file relationships, multi-repository. Each block 2-3 sentences of prose, no inline code. No superlatives. | Workshop Part 3: feature highlight prose |
| 1.3 | Write "How It Works" section | documentation | 6-step numbered list (Scan, Parse, Relate, Summarize, Embed, Store). Each step 1 sentence. Closing sentence mentions CLI and MCP queryability. | Workshop Part 4: numbered list, not Mermaid. Order matches actual implementation: Discovery→Parsing→CrossFileRels→SmartContent→Embedding→Storage. |
| 1.4 | Write "When to Use fs2" section | documentation | Opens with sentence acknowledging grep/ripgrep. Comparison table with ≥ 7 rows mapping needs to tools. One parenthetical explaining what MCP is. | Workshop Part 5: "different tool, different job" framing |
| 1.5 | Write semantic search example | documentation | Shows search query where terms don't appear in source code. Results include smart_content summaries. Explanation in 1 sentence. | Workshop Part 7: the "aha moment" |

### Acceptance Criteria (Phase 1)

- [ ] AC-01: Opening paragraph explains parse → enrich → search pipeline
- [ ] AC-02: 5 feature blocks, 2-3 sentences each, prose only
- [ ] AC-03: 6-step numbered pipeline list
- [ ] AC-04: Comparison table with ≥ 7 rows, respectful of grep/ripgrep
- [ ] AC-05: Semantic search example with terms absent from source
- [ ] AC-07: Word "powerful" does not appear
- [ ] AC-11: Brief MCP explanation included

---

### Phase 2: Restructure & Trim

**Objective**: Reorder sections value-first, trim content duplicated in guides, expand the Guides table, and resolve remaining open questions.
**Domain**: documentation
**Delivers**:
- Restructured README with new section ordering
- Trimmed MCP section (setup only, ~40 lines)
- Removed Embeddings section (covered in config guide)
- Trimmed Cross-File Relationships section (5-line summary + link)
- Trimmed Scanning section (quick start + link)
- Expanded Guides table (all relevant guides)
- Resolved OQ-02 (Canonical Example → Developer Setup)
- Resolved OQ-03 (Quick Diagnostics kept)
**Depends on**: Phase 1
**Key risks**: Trimming must preserve all guide links — no orphaned references. Restructured README must be ≤ 457 lines.

| # | Task | Domain | Success Criteria | Notes |
|---|------|--------|-----------------|-------|
| 2.1 | Reorder sections: new sections first, then Quick Start | documentation | Section order: Opening → Key Capabilities → How It Works → When to Use → Quick Start → Guides → Quick Diagnostics → MCP → Scanning → Cross-File Relationships (trimmed) → Language Support → Developer Setup | Per Workshop Part 8. Cross-File Rels kept as trimmed ≤5-line section per AC-09. |
| 2.2 | Rename "Installation" to "Quick Start" | documentation | H2 heading reads `## Quick Start`. Content preserved. | Per spec AC-08 |
| 2.3 | Trim MCP section | documentation | Remove tool parameter tables and documentation tool examples. Keep client setup (Claude Code, Claude Desktop, GitHub Copilot), Available Tools summary table, and link to MCP server guide. Target: ~40 lines. | 134 → ~40 lines. Detail in mcp-server-guide.md |
| 2.4 | Remove Embeddings section | documentation | Section removed entirely. Config guide link preserved in Scanning section or Quick Start. | Per finding 04. Content in configuration-guide.md |
| 2.5 | Trim Cross-File Relationships section | documentation | Reduce to 5-line summary + link to `cross-file-relationships.md`. Mention supported languages in one sentence. | 58 → ~5 lines. Already covered in Key Capabilities |
| 2.6 | Trim Scanning section | documentation | Keep quick start commands (`fs2 init`, `fs2 scan`) and config note. Link to scanning guide. Target: ~15 lines. | 40 → ~15 lines |
| 2.7 | Expand Guides table | documentation | Surface all user guides. Expected entries: CLI Reference, Scanning, MCP Server, Configuration Guide, Multi-Graph, Agent Integration, Cross-File Relationships, Local Embeddings, Local LLM. Wormhole MCP stays in Developer Guides. | Currently 6 shown; need 9 in user guides table. configuration.md may be superseded by configuration-guide.md — verify and decide. |
| 2.8 | Merge Canonical Example into Developer Setup | documentation | Remove standalone "Canonical Example" section. Add 1-line reference to `test_sample_adapter_pattern.py` in Developer Setup. | Resolves OQ-02 |
| 2.9 | Final line count check | documentation | README.md ≤ 457 lines. All guide links valid. No "powerful". No orphaned anchors. | Per AC-07, AC-12 |

### Acceptance Criteria (Phase 2)

- [ ] AC-06: Guides table surfaces all user guides (9 expected)
- [ ] AC-08: Installation repositioned after value sections, renamed to "Quick Start"
- [ ] AC-09: Embeddings removed, Cross-File trimmed to ≤ 5 lines, Scanning trimmed
- [ ] AC-10: MCP section retains client setup + tools table, details trimmed
- [ ] AC-12: Final README ≤ 457 lines

---

## Line Budget

The new sections need room. Here's the budget:

| Section | Current | Target | Δ |
|---------|---------|--------|---|
| Opening paragraph | 2 | 6 | +4 |
| Key Capabilities | 0 | 25 | +25 |
| How It Works | 0 | 15 | +15 |
| When to Use fs2 | 0 | 20 | +20 |
| Semantic search example | 0 | 15 | +15 |
| **New sections total** | **2** | **81** | **+79** |
| | | | |
| Installation → Quick Start | 63 | 63 | 0 |
| Guides | 11 | 20 | +9 |
| Quick Diagnostics | 34 | 34 | 0 |
| MCP Server | 134 | 40 | **-94** |
| Scanning | 40 | 15 | **-25** |
| Embeddings | 27 | 0 | **-27** |
| Cross-File Rels | 58 | 5 | **-53** |
| Language Support | 24 | 24 | 0 |
| Canonical Example | 4 | 0 | **-4** |
| Developer Setup | 57 | 58 | +1 |
| **Existing sections total** | **452** | **259** | **-193** |
| | | | |
| **Headings/spacing** | ~3 | ~12 | +9 |
| **Grand total** | **457** | **~352** | **~-105** |

Net effect: README shrinks by ~100 lines while adding all new value sections. Well within the ≤ 457 line budget.

---

## Acceptance Criteria (Full)

- [x] AC-01: Opening paragraph explains parse → enrich → search pipeline
- [x] AC-02: Key Capabilities section with 5 feature blocks, prose only
- [x] AC-03: How It Works section with 6-step numbered pipeline list
- [x] AC-04: When to Use section with comparison table (≥ 7 rows), respectful of alternatives
- [x] AC-05: Semantic search example with query terms absent from source code
- [ ] AC-06: Guides table surfaces all user guides (9 expected)
- [x] AC-07: Word "powerful" does not appear in README
- [ ] AC-08: Installation repositioned after value sections, renamed "Quick Start"
- [ ] AC-09: Embeddings removed, Cross-File trimmed, Scanning trimmed
- [ ] AC-10: MCP section retains client setup, details trimmed
- [x] AC-11: Brief MCP explanation included (one sentence)
- [ ] AC-12: Final README ≤ 457 lines

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Tone is too dry or too promotional | Medium | Medium | Workshop 001 golden rule + review pass |
| Trimming loses information users relied on | Low | Low | Every trim includes link to full guide |
| Semantic search example feels contrived | Medium | Low | Use realistic auth/JWT scenario from workshop |
| MCP explanation is confusing for non-agent users | Low | Low | One parenthetical sentence, skippable |

---

## Discoveries & Learnings

*(To be populated during implementation)*
