# Workshop: Selling the fs2 Premise

**Type**: Content Design
**Plan**: 048-better-documentation
**Research Dossier**: [research-dossier.md](../research-dossier.md)
**Created**: 2026-04-13
**Status**: Draft

---

## Purpose

Define the voice, structure, and concrete content for fs2's README value proposition — the sections that explain what fs2 does, why it exists, and what makes it interesting. This is a working reference for the README rewrite.

## Key Questions Addressed

- What should the first 10 lines of the README say?
- How do we explain a multi-stage pipeline without losing people?
- What tone works for dev tools? (confident ≠ salesy)
- Which features carry the most weight and how do we present them?
- How do we handle the multi-repo story naturally?
- What do we cut vs keep from the current README?

---

## Part 1: Tone Principles

### What works (from ripgrep, ruff, uv, tree-sitter)

| Principle | Example | Why it works |
|-----------|---------|-------------|
| **One sentence that lands** | *"An extremely fast Python linter, written in Rust."* — ruff | Reader knows what it is and why it might be interesting in 8 words |
| **Claims backed by structure** | ripgrep: defines behavior, then shows benchmark | Doesn't say "amazing" — shows you the comparison and lets you decide |
| **Bullets for scannability** | uv: 5 feature bullets before installation | Busy engineers scan, they don't read paragraphs |
| **Technical, not promotional** | tree-sitter: *"aims to be general, fast, robust, dependency-free"* | States properties. No superlatives. No exclamation marks. |

### The fs2 voice

fs2 should sound like **a senior engineer explaining their tool to another engineer over coffee**. Knowledgeable, direct, a little proud of the architecture — but never selling. The features are genuinely interesting; they don't need amplification.

**Do this:**
- State what it does, then show it
- Use precise technical language ("tree-sitter AST parsing" not "advanced code analysis")
- Let the architecture speak — "searches both raw code and AI summaries" is already compelling
- Mention scale casually — "tested across 25+ repositories" as a fact, not a boast

**Avoid this:**
- Superlatives without evidence ("the most powerful", "revolutionary")
- Marketing cadence ("unlock the power of", "supercharge your workflow")
- Defensive comparisons ("unlike other tools that fail to...")
- Exclamation marks in technical prose
- Repeating the same benefit in different words

### Tone spectrum

```
Too cold                    Just right                      Too hot
─────────────────────────────────────────────────────────────────────
"A code indexer."     "Builds a searchable code       "The ULTIMATE AI-powered
                       graph with AI summaries          code intelligence
                       and semantic search."            platform!!!"
```

---

## Part 2: The Opening

### Current opening (the problem)

```markdown
# Flowspace2 (fs2)

Code intelligence for your codebase. Scan, search, and explore code with AI agents via MCP.

## Installation
```

Three problems:
1. "Code intelligence" is vague — could be anything from a linter to an IDE
2. "Scan, search, and explore" describes mechanics, not outcomes
3. Installation starts on line 6 — no one knows what they're installing yet

### Proposed opening

```markdown
# Flowspace2 (fs2)

fs2 parses your codebase into individual code elements — functions, classes, methods —
then enriches each one with AI-generated summaries and vector embeddings. The result
is a searchable code graph that supports text, regex, and semantic search across one
or many repositories, available as a CLI or through MCP for AI coding agents.
```

**Why this works:**
- Sentence 1: What it does mechanically (parse → decompose → nodes)
- Sentence 2: What it adds (AI summaries, embeddings)
- Sentence 3: What you get (searchable graph, multiple modes, MCP)
- No adjectives doing the heavy lifting — the nouns carry the meaning

### Alternative openings (for consideration)

**Option B — Lead with the pipeline visual:**
```markdown
# Flowspace2 (fs2)

Turn any codebase into a searchable, AI-enriched code graph.

fs2 scans source code, decomposes it into individual nodes (functions, classes, methods),
generates AI summaries for each one, and builds a graph with cross-file relationships
and vector embeddings. Search by text, regex, or meaning — across multiple repositories
if needed.
```

**Option C — Lead with the problem:**
```markdown
# Flowspace2 (fs2)

grep finds text. fs2 understands code.

fs2 parses your codebase into a graph of individual code elements, enriches each
with AI-generated summaries, and embeds them for semantic search. Ask "where is the
authentication logic?" and get the actual function — even if the word "authentication"
never appears in the code.
```

### Recommendation

**Option A** for the main README — it's the most straightforward and technical. Option C's "grep finds text" line is punchy but risks sounding like a takedown. Option B's "Turn any codebase" is slightly marketing-flavored. Option A just states facts.

---

## Part 3: Feature Highlights

### Selection criteria

Not every feature deserves README real estate. These earned their spot:

| Feature | Why it's in the README | How to present |
|---------|----------------------|----------------|
| **Node decomposition** | This is the foundational "what" — without it, nothing else works | Lead with it |
| **Smart content** | This is the "wow" — AI summaries make semantic search actually useful | Show the before/after |
| **Semantic search** | This is the "so what" — the payoff of everything else | Show a query that works |
| **Cross-file relationships** | Shows graph depth — not just search, but navigation | Mention, link to guide |
| **Multi-repository** | The scale story — 25+ repos is genuinely impressive | Mention naturally |
| **40+ languages** | Breadth — "it just works for your stack" | List in a section, don't lead with it |

**What stays in guides only (not README):**
- Content-aware chunking (implementation detail)
- Dual-channel embedding architecture (too deep for README)
- Incremental scanning (nice, but not a headline)
- Configuration details (existing section is fine)

### Proposed feature section

```markdown
## Key Capabilities

**Structural parsing** — fs2 uses tree-sitter to parse 40+ languages into individual
code elements: functions, classes, methods, types, blocks. Each element becomes a
node in a directed graph with its source, signature, qualified name, and position.

**AI-generated summaries** — Each node is summarized by an LLM in 1-2 sentences
describing what it does. These summaries power semantic search — you can find
"the function that validates JWT tokens" even if the code calls it `check_auth`.

**Semantic search** — Search by meaning, not just text. fs2 embeds both raw code
and AI summaries, then searches both channels to find the best match. Also supports
text and regex modes.

**Cross-file relationships** — SCIP-based import and call resolution maps
references across files. See what calls a function, what it depends on, and how
modules connect. Supports Python, TypeScript, JavaScript, Go, and C#.

**Multi-repository** — Configure multiple codebases as named graphs and query
across all of them from one installation. Useful for monorepos, shared libraries,
or legacy systems spanning many repositories.
```

### Tone check on each feature block

Each block follows the same pattern: **what it is** (technical noun) → **how it works** (one sentence) → **why you'd care** (concrete example or outcome). No block exceeds 3 sentences. No block uses words like "powerful", "advanced", or "cutting-edge".

---

## Part 4: The Pipeline Story

The pipeline is fs2's most compelling architectural idea — raw code transforms through stages into something searchable. But it needs to be presented simply.

### Option A — Inline list (recommended for README)

```markdown
## How It Works

fs2 processes your code through a pipeline:

1. **Scan** — Discovers source files (respects `.gitignore`, configurable paths)
2. **Parse** — tree-sitter breaks each file into individual code elements
3. **Relate** — SCIP resolves cross-file imports, calls, and type references
4. **Summarize** — An LLM generates a concise summary for each element
5. **Embed** — Vector embeddings are generated for both code and summaries
6. **Store** — Everything is persisted as a graph (`.fs2/graph.pickle`)

The graph is then queryable via CLI (`fs2 search`, `fs2 tree`) or through MCP
tools for AI coding agents.
```

**Why a numbered list, not a diagram:**
- Renders everywhere (GitHub, terminals, plaintext)
- Naturally implies sequence
- Each step is scannable
- No Mermaid rendering dependency

### Option B — ASCII pipeline (for visual thinkers)

```
Source files → Parse (tree-sitter) → Nodes → Relate (SCIP) → Summarize (LLM) → Embed → Graph → Search/MCP
```

This works as a single-line summary alongside the numbered list, not instead of it.

### Option C — Full diagram (too much for README)

The research dossier has a full pipeline diagram. This belongs in `docs/how/user/scanning.md` or an architecture doc, not in the README. The README version should be digestible in 10 seconds.

---

## Part 5: The Comparison

### Why a comparison works

ripgrep's README works because it shows you exactly where it differs from grep. fs2 needs the same — but positioned as "different tool for different job", not "better than everything".

### Proposed comparison

```markdown
## When to Use fs2

fs2 is not a replacement for grep or ripgrep — those are fast text search tools
and they're great at what they do. fs2 is for when you need to understand code
structure, not just find text.

| Need | Tool |
|------|------|
| Find a string in files | `grep` / `ripgrep` |
| Find a function by name or meaning | `fs2 search` |
| Understand what a class does | `fs2 get-node` (with AI summary) |
| Explore codebase structure | `fs2 tree` |
| Navigate cross-file dependencies | `fs2 get-node` (with relationships) |
| Search across multiple repositories | `fs2 search --graph-name` |
| Give an AI agent code context | `fs2 mcp` |
```

**Why this works:**
- Acknowledges grep/ripgrep are good (not a teardown)
- Shows the boundary clearly — text search vs code understanding
- Each row is a concrete scenario with a concrete answer
- Reader self-selects: "do I need this?"

---

## Part 6: The Multi-Repo Story

### The problem with overselling scale

Saying "supports 25+ repositories!" sounds like a press release. Saying "we tested it with 25+ repos" is an anecdote about your own testing. Neither is great.

### The right framing

Scale should appear as a capability, mentioned in context, with the practical value foregrounded:

```markdown
**Multi-repository** — Configure multiple codebases as named graphs and query
across all of them from one installation. Useful for monorepos, shared libraries,
or legacy systems spanning many repositories.
```

Then, separately, in the Quick Start or Scanning section:

```markdown
> fs2 has been used to index and search across large multi-repo codebases. See
> the [Multi-Graph Guide](docs/how/user/multi-graphs.md) for setup.
```

**Rules for the multi-repo story:**
- Never say "up to 25+ repos" — it implies a limit and sounds like a spec sheet
- Frame it as a workflow: "query across all of them from one installation"
- The number can appear in the guide, not the README
- Lead with the use case (monorepos, shared libs, legacy systems), not the count

---

## Part 7: What to Show (Examples)

### The "aha moment" example

The single most compelling thing fs2 can do is semantic search that finds code by meaning. This should be shown early:

```markdown
### Example: Find code by meaning

```bash
$ fs2 search "function that validates user authentication tokens" --mode semantic

Results:
  callable:src/auth/jwt_validator.py:JWTValidator.validate_token  (score: 0.89)
    → "Validates a JWT token by checking signature, expiration, and claims..."

  callable:src/middleware/auth.py:require_auth                     (score: 0.74)
    → "Middleware decorator that extracts and validates the Bearer token..."
```

The search found `validate_token` and `require_auth` — neither contains the
word "authentication" — because fs2 searches AI-generated summaries alongside
raw code.
```

**Why this is the right example:**
- Shows something grep literally cannot do
- The query is natural language, the results are real code locations
- The explanation is one sentence
- The "aha" is self-evident: *the code doesn't contain the search terms*

### Tree example (structural understanding)

```markdown
```bash
$ fs2 tree --pattern "JWTValidator"

📦 JWTValidator [12-89]
├── ƒ __init__ [15-23]
├── ƒ validate_token [25-56]
├── ƒ decode_payload [58-72]
└── ƒ check_expiration [74-89]
```
```

Short, visual, immediately shows what "node decomposition" means in practice.

---

## Part 8: Proposed README Structure

### New section ordering

```
# Flowspace2 (fs2)
[Opening paragraph — what it does]            ← NEW

## Key Capabilities                           ← NEW (5 feature blocks)
## How It Works                               ← NEW (numbered pipeline)
## When to Use fs2                            ← NEW (comparison table)

## Quick Start                                ← MOVED UP (was Installation)
  ### Prerequisites
  ### Option 1: Zero-Install with uvx
  ### Option 2: Permanent Install
  ### Verify Installation

## Guides                                     ← EXISTING (expand to show all 11)

## MCP Server (AI Agent Integration)          ← EXISTING (trimmed — detail in guide)
## Scanning                                   ← EXISTING (trimmed)
## Language Support                           ← EXISTING (keep as-is)

## Developer Setup                            ← EXISTING (keep at bottom)
```

### What changes

| Section | Action | Rationale |
|---------|--------|-----------|
| Opening | **Replace** | One paragraph, not one line |
| Key Capabilities | **Add** | The missing "what does it do" |
| How It Works | **Add** | The missing pipeline story |
| When to Use | **Add** | The missing "why this tool" |
| Installation | **Rename → Quick Start**, move down | Value before mechanics |
| Guides | **Expand** | Show all 11 docs, not 2 |
| Embeddings section | **Remove from README** | Covered in config guide |
| Cross-File Rels section | **Trim** | Summarized in Key Capabilities, detail in guide |
| Scanning section | **Trim** | Quick start + link to guide |
| MCP section | **Trim** | Keep setup, move tool reference to guide |

### What stays exactly as-is

- Language Support table (it's good, it's scannable)
- Developer Setup (it's for contributors, fine at the bottom)
- Installation methods table (clear and useful)

---

## Part 9: Anti-Patterns to Avoid

These are specific failure modes for this kind of README rewrite:

| Anti-Pattern | Example | Why it fails |
|--------------|---------|-------------|
| **The wall of features** | Listing 15 features in bullet points | Nobody reads past bullet 5 |
| **The architecture dump** | Explaining Clean Architecture in the README | Users don't care about internal layering |
| **The benchmark without context** | "Indexes 10,000 files in 30 seconds" | No one knows if that's good |
| **The "unlike other tools"** | "Unlike grep, which can't understand code..." | Reads as insecure |
| **The future roadmap** | "Coming soon: real-time indexing!" | Promises erode trust |
| **The adjective avalanche** | "Powerful, intelligent, advanced AI-driven..." | Every adjective reduces credibility |
| **The everything-is-configurable** | Showing all config options upfront | Configurability isn't a feature, it's an implementation detail |

### The golden rule

> **If you remove all the adjectives and the sentence still sounds impressive, you've written it correctly.**

- ❌ "fs2's powerful AI-driven smart content engine generates intelligent summaries"
- ✅ "fs2 generates a 1-2 sentence summary for each function, class, and method"

Both say the same thing. The second one is specific, concrete, and actually more impressive because the reader can picture it.

---

## Open Questions

### Q1: Should we show a full terminal session or isolated examples?

**RESOLVED**: Isolated examples. A full session (`init` → `scan` → `search`) is too long for the README. Each example should demonstrate one concept. The Quick Start section can link them together.

### Q2: Should the README explain what MCP is?

**OPEN**: Two options:
- **Option A**: Brief parenthetical — "(MCP is the protocol AI coding agents use to access external tools)"
- **Option B**: Assume the reader knows MCP or will follow the link
- **Leaning toward A** — one sentence costs nothing and prevents confusion

### Q3: Should the opening mention "AI agents" prominently?

**RESOLVED**: Yes, but as one of two audiences. fs2 is useful to both human developers (CLI) and AI agents (MCP). The opening should mention both. AI agents are a differentiator — most code search tools don't have MCP integration.

### Q4: How much of the Key Capabilities section should use code examples?

**RESOLVED**: Zero code in Key Capabilities. That section is prose — 2-3 sentences per feature. Code examples come in the How It Works section and Quick Start. Mixing prose features with inline code blocks creates visual noise.

---

## Summary: The Checklist

Before the README is done, verify:

- [ ] A newcomer can explain what fs2 does after reading the first paragraph
- [ ] The word "powerful" does not appear
- [ ] Every feature mention includes what it *does*, not just what it *is*
- [ ] Semantic search is shown with an example where grep would fail
- [ ] Multi-repo is mentioned as a capability, not a statistic
- [ ] The comparison acknowledges other tools respectfully
- [ ] Installation comes after explanation
- [ ] The README is shorter than the current one (trim, don't expand)
- [ ] No section requires knowledge from another section to understand
- [ ] An AI agent reading the README can immediately understand the MCP value
