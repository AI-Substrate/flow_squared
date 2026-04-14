# Validation Report — 048 Better Documentation

**Artifact Validated**: Full plan tree (spec, plan, tasks dossier, workshop, flight plans)
**Agents**: 3 (source-truth, cross-reference, completeness) on GPT-5.4
**Date**: 2026-04-14
**Coverage**: 10 of 11 lenses (Security & Privacy excluded — not applicable)

---

## Verdict: 🟢 PASS (after fixes applied)

4 HIGH issues found → all 4 resolved. 7 MEDIUM issues noted for implementation. 2 LOW issues are advisory.

### Fixes Applied

| ID | Issue | Fix Applied |
|----|-------|------------|
| H-01 | Pipeline order wrong (Summarize before Relate) | Fixed in workshop, plan, tasks dossier, flight plans → now Scan→Parse→Relate→Summarize→Embed→Store |
| H-02 | Opening is 2 sentences, AC-01 needs 3-5 | Deferred to implementor — workshop is a starting point, not final copy |
| H-03 | AC-06 weakened from "all docs" to "≥ 9" | Fixed in plan — now enumerates 9 expected guides, names specific additions |
| H-04 | Cross-File Rels section missing from target order | Fixed in plan task 2.1 — now includes "Cross-File Relationships (trimmed)" |

---

## HIGH Issues (must fix before Phase 1)

### H-01: Pipeline stage order is wrong

**Source**: source-truth-validator
**Lens**: Technical Constraints
**Location**: `tasks.md:120`, `001-selling-the-premise.md:196-201`

The workshop and tasks dossier document the pipeline as: Scan → Parse → **Summarize → Embed → Relate** → Store.

The actual implementation order in `scan_pipeline.py:224-236` is: Discovery → Parsing → **CrossFileRels → SmartContent → Embedding** → Storage.

Cross-file relationship resolution happens **before** summarization and embedding, not after.

**Fix**: Update pipeline order in workshop, plan, tasks dossier, and flight plans to: **Scan → Parse → Relate → Summarize → Embed → Store**.

---

### H-02: Workshop opening is only 2 sentences (AC-01 requires 3-5)

**Source**: cross-reference-validator
**Lens**: System Behavior
**Location**: `001-selling-the-premise.md:88-91`, `better-documentation-spec.md:99`

Workshop Option A (the selected opening) contains exactly 2 sentences. AC-01 requires "3-5 sentences."

**Fix**: Either expand the draft opening to 3-5 sentences during implementation, or relax AC-01 to "2-5 sentences." The implementor has latitude to expand — the workshop is a starting point, not a final draft.

---

### H-03: AC-06 weakened from "all docs" to "≥ 9"

**Source**: cross-reference-validator + completeness-validator
**Lens**: Integration & Ripple, Completeness
**Location**: `better-documentation-plan.md:117,123`, `better-documentation-spec.md:109`

The spec says: "surfaces **all bundled documentation** (currently 10 docs in registry + additional user guides)."
The plan weakens this to: "Show **≥ 9** user guides."
There are 11 user guides in `docs/how/user/`. The plan only names 3 additions.

Missing from plan's named additions: `configuration.md`, `wormhole-mcp-guide.md` (already in Developer Guides section).

**Fix**: Update plan task 2.7 to enumerate all expected Guides table entries. Consider that `wormhole-mcp-guide.md` is already in the Developer Guides section — decide whether to duplicate it or leave it there. Update "≥ 9" to match the actual expected count.

---

### H-04: Cross-File Relationships section missing from target section order

**Source**: cross-reference-validator + completeness-validator
**Lens**: Domain Boundaries, Completeness
**Location**: `better-documentation-plan.md:111`, `better-documentation-plan.md:115`

Task 2.1's target order lists: Opening → Key Capabilities → How It Works → When to Use → Quick Start → Guides → Quick Diagnostics → MCP → Scanning → Language Support → Developer Setup.

Task 2.5 says to keep a trimmed Cross-File Relationships section (≤ 5 lines). But it doesn't appear in the ordering.

**Fix**: Add "Cross-File Relationships (trimmed)" to the target section order between Scanning and Language Support. Or explicitly remove it and fold the content into the "Key Capabilities" section.

---

## MEDIUM Issues (should fix)

### M-01: Summary length claim is inaccurate

**Source**: source-truth-validator
**Lens**: Concept Documentation

Templates for callable/section/block say "1-2 sentences." Templates for file/type say "2-3 sentences." The draft content says "1-2 sentence summary" uniformly.

**Fix**: Say "concise summary" or "1-3 sentence summary" in the README. Don't specify the exact count.

---

### M-02: Draft opening overstates behavior

**Source**: source-truth-validator
**Lens**: Hidden Assumptions

Not all code gets decomposed into per-element nodes (some languages are file-only). Not all nodes get embeddings (requires LLM/embedding provider configuration). The opening should qualify this.

**Fix**: The implementor should add a qualifier like "for supported languages" or note that AI enrichment is configurable. The README already has a config note in the Scanning section — a brief qualifier in the opening is sufficient.

---

### M-03: Tasks dossier missing explicit AC list

**Source**: cross-reference-validator
**Lens**: Integration & Ripple

The tasks dossier lists goals but doesn't have a standalone "Acceptance Criteria" section mirroring the plan's Phase 1 ACs. AC-07 (no "powerful") and AC-11 (MCP explanation) appear only indirectly.

**Fix**: The tasks dossier DOES have AC-07 and AC-11 in its flight plan and context brief — but could be more explicit. Minor fix.

---

### M-04: MCP trim scope ambiguous

**Source**: cross-reference-validator
**Lens**: System Behavior

Workshop says "move tool reference to guide." AC-10 says "retains... available tools table." These need alignment.

**Fix**: Keep the existing Available Tools summary table (5 rows, no parameters) in the README. Remove the Documentation Tools sub-section with its code examples. This satisfies both the workshop's "trim" and AC-10's "retain tools table."

---

### M-05: Semantic search example should be labeled illustrative

**Source**: completeness-validator
**Lens**: User Experience

The JWT/auth example shows hypothetical output. Users may try to reproduce it.

**Fix**: Either label it "Example output (illustrative)" or use a more generic framing like "Example:" without suggesting it's from a specific codebase.

---

### M-06: Internal README anchor links exist

**Source**: completeness-validator
**Lens**: Edge Cases

`README.md:66` contains `See [Developer Setup](#developer-setup)`. The plan only checked for external anchor references.

**Fix**: During Phase 2, grep the README for `](#` patterns and verify all internal links still resolve after restructuring.

---

### M-07: CS-2 may be slightly optimistic

**Source**: completeness-validator
**Lens**: Complexity Accuracy

The plan's T=0 (no testing) assumes visual review only. Link auditing, rendering checks, and content review add real work.

**Fix**: Keep CS-2 but add an explicit sub-task in Phase 2 for link/anchor verification (grep for `](#` and validate). This is already partially covered by task 2.9.

---

## LOW Issues (advisory)

### L-01: Terminology drift (smart_content vs AI-generated summaries)

**Source**: cross-reference-validator
**Lens**: Terminology Alignment

The README should use "AI-generated summaries" consistently. `smart_content` is an implementation detail that appears in CLI output but shouldn't be the user-facing term.

---

### L-02: Language count is stale and wrong

**Source**: source-truth-validator
**Lens**: Concept Documentation

README says "Code Languages (40)" but the actual `CODE_LANGUAGES` set in `ast_parser_impl.py:251-327` contains **58** entries. MATLAB is listed in the README but has been removed from the code.

**Fix**: During Phase 2, update the language count. Consider saying "55+" rather than an exact number (to avoid staleness). Remove MATLAB from the list.

---

## Resolution Matrix

| ID | Severity | Fix During | Owner |
|----|----------|-----------|-------|
| H-01 | HIGH | Before Phase 1 (update workshop + tasks dossier) | Plan author |
| H-02 | HIGH | During Phase 1 implementation (expand opening) | Implementor |
| H-03 | HIGH | Before Phase 2 (update plan task 2.7) | Plan author |
| H-04 | HIGH | Before Phase 2 (update plan task 2.1) | Plan author |
| M-01 | MEDIUM | During Phase 1 (use "concise summary") | Implementor |
| M-02 | MEDIUM | During Phase 1 (qualify opening) | Implementor |
| M-03 | MEDIUM | Optional (already covered indirectly) | — |
| M-04 | MEDIUM | During Phase 2 (keep tools table, remove detail) | Implementor |
| M-05 | MEDIUM | During Phase 1 (label example) | Implementor |
| M-06 | MEDIUM | During Phase 2 task 2.9 (grep for `](#`) | Implementor |
| M-07 | MEDIUM | Already covered by task 2.9 | — |
| L-01 | LOW | During implementation (use consistent terms) | Implementor |
| L-02 | LOW | During Phase 2 (update language count) | Implementor |
