# Flight Plan: Phase 1 — Write New Sections

**Plan**: [better-documentation-plan.md](../../better-documentation-plan.md)
**Phase**: Phase 1: Write New Sections
**Tasks**: [tasks.md](tasks.md)
**Generated**: 2026-04-13
**Status**: Landed

---

## Departure → Destination

**Where we are**: `README.md` opens with a single vague line — *"Code intelligence for your codebase"* — then immediately jumps to installation. No one reading the README can tell what fs2 actually does, how it works, or why they might want it.

**Where we're going**: A developer or AI agent reading the first 80 lines of the README can explain what fs2 does (parses code into nodes, enriches with AI summaries, searches semantically), how the pipeline works (6 stages), and when to use it vs grep/ripgrep.

---

## Domain Context

### Domains We're Changing

| Domain | What Changes | Key Files |
|--------|-------------|-----------|
| documentation | Insert 4 new sections + 1 example between title and Installation | `/Users/jordanknight/substrate/fs2/048-better-documentation/README.md` |

### Domains We Depend On (no changes)

| Domain | What We Consume | Contract |
|--------|----------------|----------|
| (none) | Workshop 001 content decisions | Draft prose, tone rules, structure decisions |

---

## Flight Status

<!-- Updated by /plan-6-v2: pending → active → done. Use blocked for problems/input needed. -->

```mermaid
stateDiagram-v2
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef active fill:#FFC107,stroke:#FFA000,color:#000
    classDef done fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    state "1: Opening paragraph" as S1
    state "2: Key Capabilities" as S2
    state "3: How It Works" as S3
    state "4: When to Use" as S4
    state "5: Search example" as S5

    [*] --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    S5 --> [*]

    class S1,S2,S3,S4,S5 done
```

**Legend**: grey = pending | yellow = active | red = blocked/needs input | green = done

---

## Stages

<!-- Updated by /plan-6-v2 during implementation: [ ] → [~] → [x] -->

- [x] **Stage 1: Write opening paragraph** — Replace lines 2-3 with 3-sentence pipeline description (`README.md`)
- [x] **Stage 2: Write Key Capabilities** — Insert 5 feature blocks: parsing, summaries, search, cross-file, multi-repo (`README.md`)
- [x] **Stage 3: Write How It Works** — Insert 6-step numbered pipeline list: Scan→Parse→Relate→Summarize→Embed→Store (`README.md`)
- [x] **Stage 4: Write When to Use** — Insert comparison table with 7 rows + MCP explanation (`README.md`)
- [x] **Stage 5: Write search example** — Insert semantic search "aha" example with JWT/auth scenario (`README.md`)

---

## Architecture: Before & After

```mermaid
flowchart LR
    classDef existing fill:#E8F5E9,stroke:#4CAF50,color:#000
    classDef new fill:#E3F2FD,stroke:#2196F3,color:#000

    subgraph Before["README.md — Before"]
        B1["Title + 1-line tagline"]:::existing
        B2["## Installation"]:::existing
        B1 --> B2
    end

    subgraph After["README.md — After"]
        A1["Title + opening paragraph"]:::new
        A2["## Key Capabilities"]:::new
        A3["## How It Works"]:::new
        A4["## When to Use fs2"]:::new
        A5["## Installation"]:::existing
        A1 --> A2 --> A3 --> A4 --> A5
    end
```

**Legend**: existing (green, unchanged) | new (blue, created)

---

## Acceptance Criteria

- [x] AC-01: Opening paragraph explains parse → enrich → search pipeline
- [x] AC-02: 5 feature blocks, 2-3 sentences each, prose only
- [x] AC-03: 6-step numbered pipeline list
- [x] AC-04: Comparison table with ≥ 7 rows, respectful of grep/ripgrep
- [x] AC-05: Semantic search example with terms absent from source code
- [x] AC-07: Word "powerful" does not appear
- [x] AC-11: Brief MCP explanation included

## Goals & Non-Goals

**Goals**:
- ✅ Reader understands what fs2 does after opening paragraph
- ✅ 5 key capabilities highlighted with prose
- ✅ Pipeline explained as numbered list
- ✅ Clear positioning vs grep/ripgrep
- ✅ "Aha moment" semantic search example

**Non-Goals**:
- ❌ Restructuring existing sections (Phase 2)
- ❌ Trimming MCP/Scanning/Embeddings (Phase 2)
- ❌ Modifying guide documents

---

## Checklist

- [x] T001: Write opening paragraph (3 sentences, pipeline description)
- [x] T002: Write Key Capabilities (5 prose blocks, no code, no superlatives)
- [x] T003: Write How It Works (6-step numbered list, correct stage order)
- [x] T004: Write When to Use fs2 (comparison table, MCP explanation)
- [x] T005: Write semantic search example (terms absent from source, labeled illustrative)
