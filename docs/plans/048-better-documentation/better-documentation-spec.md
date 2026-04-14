# Better Documentation — README Rewrite

📚 This specification incorporates findings from [research-dossier.md](research-dossier.md)
and design decisions from [Workshop 001: Selling the Premise](workshops/001-selling-the-premise.md).

---

## Research Context

The research dossier (8 parallel agents, 62 findings) established that:

- The current README opens with *"Code intelligence for your codebase"* then jumps to installation on line 6 — it never explains what fs2 does, why it's different, or why someone should care (DE-01, DE-02, DE-10)
- fs2's core value — a multi-stage pipeline from raw source → parsed nodes → AI summaries → dual embeddings → cross-file graph → semantic search — is never told as a story anywhere in the documentation (IA-01 → IA-10)
- Eight differentiating features exist but are scattered across subsections or buried in separate guides (PS-01 → PS-10)
- Prior plans consistently found that "docs should explain user value, not just mechanics" (PL-04, PL-11)
- The bundled docs registry contains 10 guides, but the README only surfaces 2 (DE-09)

The workshop (001-selling-the-premise) resolved key content design questions:
- **Tone**: "Senior engineer explaining to another engineer over coffee" — confident, technical, no adjectives doing the heavy lifting
- **Opening**: Factual paragraph stating parse → enrich → search pipeline (Option A selected)
- **Features**: 5 headline blocks, prose only, no code in capability descriptions
- **Pipeline**: Numbered list (renders everywhere, no Mermaid dependency)
- **Comparison**: "Different tool for different job" framing, respects grep/ripgrep
- **Multi-repo**: Lead with use cases (monorepos, legacy systems), not repo counts
- **Examples**: Semantic search "aha moment" + tree structural example
- **Anti-patterns**: No superlatives, no marketing cadence, no defensive comparisons

---

## Summary

Rewrite the fs2 README so that a newcomer understands what fs2 does, why it exists, and what makes it interesting — before they ever see an installation command. Restructure the document to lead with value (what it does → key capabilities → how it works → when to use it), then follow with setup and reference material. Trim existing sections that duplicate content already covered in dedicated guides.

The voice should be technically precise and confident. Let the architecture speak for itself.

---

## Goals

- **Explain what fs2 does** — A reader understands the parse → enrich → search pipeline after the opening paragraph
- **Show key capabilities** — 5 feature blocks (structural parsing, AI summaries, semantic search, cross-file relationships, multi-repository) presented as outcomes, not mechanics
- **Tell the pipeline story** — A numbered "How It Works" list shows the 6-stage scan pipeline
- **Position clearly** — A "When to Use fs2" comparison table shows where fs2 fits alongside grep/ripgrep (complementary, not competitive)
- **Demonstrate the "aha"** — At least one example showing semantic search finding code by meaning (query terms absent from code)
- **Surface all guides** — The Guides table reflects all 10+ bundled docs and user guides
- **Maintain confidence without promotion** — Tone follows workshop guidelines: technical, specific, no superlatives
- **Preserve existing quality** — Installation methods, MCP client setup, language support table, and developer setup sections remain functional and accurate

---

## Non-Goals

- **Rewriting guide documents** — `scanning.md`, `mcp-server-guide.md`, `multi-graphs.md`, etc. are not in scope (they're already good)
- **Adding new features or changing code** — This is documentation only
- **Creating marketing materials** — No landing pages, no promotional copy
- **Writing a tutorial** — The README orients; guides teach
- **Documenting internal architecture** — Clean Architecture layers belong in `docs/how/dev/`, not README

---

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| documentation | **conceptual** | **modify** | README.md is the primary artifact; guides are referenced but not modified |

> **Note**: No formal domain registry exists yet (`docs/domains/registry.md` not found). This feature is documentation-only — it modifies `README.md` and does not touch code domains. The "documentation" domain is conceptual here, not a code boundary.

---

## Complexity

- **Score**: CS-2 (small)
- **Breakdown**: S=1, I=0, D=0, N=1, F=0, T=0
  - S=1: One primary file (`README.md`), but content touches many feature areas
  - I=0: No external dependencies
  - D=0: No data/schema changes
  - N=1: Some ambiguity in content choices (resolved by workshop, low residual)
  - F=0: No performance/security concerns
  - T=0: No tests to write (documentation change); visual review only
- **Total P**: 2 → CS-2
- **Confidence**: 0.85
- **Assumptions**:
  - Workshop 001 decisions are accepted (tone, structure, feature selection)
  - Existing guide documents don't need updates to support the new README
  - The README can be restructured without breaking any external links (no deep-linked sections relied upon externally)
- **Dependencies**: None
- **Risks**:
  - Content review is subjective — the "right tone" needs human judgment
  - Trimming existing sections might lose information that some users relied on (mitigated: content moves to guides, not deleted)
- **Phases**: 2 suggested phases
  1. **Restructure & write new sections** — Opening, Key Capabilities, How It Works, When to Use
  2. **Trim & integrate existing sections** — Rename Installation → Quick Start, trim Scanning/MCP/Embeddings/Cross-File sections, expand Guides table

---

## Acceptance Criteria

**AC-01**: The README opens with a paragraph (3-5 sentences) that explains what fs2 does: parse codebases into nodes, enrich with AI summaries, embed for semantic search, build a cross-file relationship graph, and serve via CLI/MCP.

**AC-02**: A "Key Capabilities" section exists with exactly 5 feature blocks: structural parsing, AI-generated summaries, semantic search, cross-file relationships, and multi-repository. Each block is 2-3 sentences of prose (no inline code).

**AC-03**: A "How It Works" section exists with a numbered list of 6 pipeline stages (Scan, Parse, Summarize, Embed, Relate, Store) — each stage described in one sentence.

**AC-04**: A "When to Use fs2" section exists with a comparison table showing concrete scenarios (≥ 7 rows) mapping needs to tools (`grep`/`ripgrep` vs `fs2` commands). The section opens with a sentence acknowledging that grep/ripgrep are good at what they do.

**AC-05**: At least one code example demonstrates semantic search finding code where the search terms don't appear in the source code (the "aha moment").

**AC-06**: The Guides table surfaces all bundled documentation (currently 10 docs in registry + additional user guides). Previously showed 6 guides.

**AC-07**: The word "powerful" does not appear in the README. No superlatives are used without evidence.

**AC-08**: Installation is repositioned after value sections (Key Capabilities, How It Works, When to Use). It may be renamed to "Quick Start".

**AC-09**: The Embeddings section is removed from the README (covered in configuration guide). The Cross-File Relationships section is trimmed to ≤ 5 lines with a link to the guide. The Scanning section is trimmed to quick-start + link.

**AC-10**: The MCP section retains client setup (Claude Code, Claude Desktop, GitHub Copilot) and available tools table, but tool parameter details are trimmed (detail in MCP server guide).

**AC-11**: The README includes a brief explanation of what MCP is (one parenthetical sentence) for readers unfamiliar with the protocol.

**AC-12**: The final README is ≤ 457 lines (same or shorter than current). Trimming existing sections compensates for new sections added.

---

## Risks & Assumptions

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Tone doesn't land — too dry or too promotional | Medium | Medium | Workshop 001 provides concrete examples and the golden rule: "remove adjectives, still sounds impressive?" |
| External links to README sections break | Low | Medium | Check for any references to `#installation`, `#embeddings`, `#cross-file-relationships` heading anchors |
| Trimmed content is missed by users | Low | Low | Every trimmed section gets a clear link to its guide document |
| "Aha" example feels contrived | Medium | Low | Use a realistic search scenario (auth/JWT validator pattern from workshop) |

**Assumptions**:
- The target audience is developers and AI agents, not managers or non-technical users
- Readers will follow links to guides for detail — the README should orient, not exhaustively document
- GitHub-flavored Markdown is the rendering target (tables, code blocks, emoji render correctly)

---

## Open Questions

**OQ-01**: Should the README explain what MCP is?
- *Workshop leaning*: Yes, one parenthetical sentence → **adopted as AC-11**

**OQ-02**: Should the `Canonical Example` section (`tests/docs/test_sample_adapter_pattern.py`) stay in the README?
- It's a developer concern, not a user concern. **Leaning**: move to Developer Setup or remove.

**OQ-03**: Should the `Quick Diagnostics` section (`fs2 doctor`) stay in the README?
- It's useful but could go in the CLI guide. **Leaning**: keep it — it's short and practical.

---

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| ~~Selling the premise~~ | ~~Content Design~~ | ~~COMPLETED~~ | ~~See [001-selling-the-premise.md](workshops/001-selling-the-premise.md)~~ |
| Guide document updates | Other | If README trimming creates gaps in guides, those guides may need backfill | Which guides need minor updates to absorb content trimmed from README? |
