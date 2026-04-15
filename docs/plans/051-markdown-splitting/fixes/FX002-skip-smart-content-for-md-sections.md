# Fix FX002: Skip Smart Content for Markdown Sections

**Created**: 2026-04-15
**Status**: Proposed
**Plan**: [markdown-splitting-plan.md](../markdown-splitting-plan.md)
**Source**: Implementation review — markdown sections are human-written prose that doesn't benefit from LLM summarization
**Workshop**: [001-smart-content-filtering.md](../workshops/001-smart-content-filtering.md)
**Domain(s)**: Scan Pipeline (modify)

---

## Problem

Markdown section nodes contain human-written prose. The smart content pipeline sends these to an LLM for summarization — wasting API tokens to paraphrase text that's already readable. The raw content embedding captures the meaning perfectly; a `smart_content_embedding` of an LLM paraphrase adds no search value.

## Proposed Fix (Option A from Workshop)

Add a `_is_self_documenting()` filter in `SmartContentStage` (line ~114) that skips markdown/rst section nodes before they enter the batch queue. `smart_content` stays None — no LLM call, no extra embedding tokens.

## Domain Impact

| Domain | Relationship | What Changes |
|--------|-------------|-------------|
| Scan Pipeline | **modify** | SmartContentStage gets a pre-filter for self-documenting nodes |

## Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [ ] | FX002-1 | Write failing test: markdown section node is NOT sent to LLM for smart content generation | Scan Pipeline | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/stages/test_smart_content_stage.py` | Test exists and FAILS (section node currently gets smart content) | TDD red |
| [ ] | FX002-2 | Add `_is_self_documenting()` filter function and integrate at `smart_content_stage.py:~114` before batch queueing | Scan Pipeline | `/Users/jordanknight/substrate/fs2/048-better-documentation/src/fs2/core/services/stages/smart_content_stage.py` | FX002-1 test passes; markdown sections skipped with log message | ~5 lines |
| [ ] | FX002-3 | Verify: section nodes still get raw content embeddings (embedding != None) but NOT smart_content_embedding | Scan Pipeline | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/stages/test_smart_content_stage.py` | Assertion passes: `embedding is not None and smart_content_embedding is None` | Confirms no regression |
| [ ] | FX002-4 | Run full test suite — no regressions | — | — | `uv run pytest` passes | Regression gate |

## Acceptance

- [ ] Markdown section nodes are NOT sent for LLM summarization during `fs2 scan`
- [ ] Markdown section nodes still receive raw content embeddings
- [ ] `smart_content` stays None for markdown sections
- [ ] RST section nodes are also skipped (same filter)
- [ ] File-level markdown nodes still get smart content (only sections are skipped)
- [ ] Log message indicates how many self-documenting nodes were skipped
