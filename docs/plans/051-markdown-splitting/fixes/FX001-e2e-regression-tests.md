# Fix FX001: Add E2E Regression Tests for Markdown Section Nodes

**Created**: 2026-04-15
**Status**: Proposed
**Plan**: [markdown-splitting-plan.md](../markdown-splitting-plan.md)
**Source**: Code review finding F001 (minih code-review agent, 2026-04-15) — AC-09, AC-10, AC-12 manually verified but have no checked-in regression tests
**Domain(s)**: AST Parsing (consume), Language Support (consume)

---

## Problem

The markdown section splitting feature works correctly — the code review agent manually verified that `fs2 tree` shows sections as children, `fs2 search` returns matching section nodes, and `EmbeddingService` processes section nodes with `ContentType.CONTENT`. However, there are **no checked-in regression tests** guarding these three acceptance criteria (AC-09, AC-10, AC-12). A future refactor could silently break tree/search/embedding for markdown sections without any test catching it.

## Proposed Fix

Add targeted integration tests to the existing `test_tree_service.py`, `test_search_service.py`, and `test_embedding_service.py` test files. Each test constructs a graph with a markdown file node + section child nodes and verifies the service handles them correctly. Uses real fixtures and existing fakes (FakeEmbeddingAdapter, etc.) — no mocks.

## Domain Impact

| Domain | Relationship | What Changes |
|--------|-------------|-------------|
| AST Parsing | consume | Tests use parser output; no production code changes |
| Language Support | consume | Tests verify splitter integration; no production code changes |

## Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [ ] | FX001-1 | Add tree service test: scan markdown fixture, verify `tree` output shows section nodes as children of file node with correct names | AST Parsing | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_tree_service.py` | Test passes; section nodes visible as file children in tree output | Covers AC-09 |
| [ ] | FX001-2 | Add search service test: scan markdown fixture, verify `search` returns section node (not whole file) when querying heading text or section content | AST Parsing | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_search_service.py` | Test passes; section node returned for heading text query | Covers AC-10 |
| [ ] | FX001-3 | Add embedding service test: verify markdown section nodes with `content_type=CONTENT` receive embeddings via the standard embedding pipeline | AST Parsing | `/Users/jordanknight/substrate/fs2/048-better-documentation/tests/unit/services/test_embedding_service.py` | Test passes; section nodes have non-null embeddings after processing | Covers AC-12 |

## Workshops Consumed

None

## Acceptance

- [ ] AC-09: A checked-in test verifies `fs2 tree` shows markdown section nodes as children of file nodes
- [ ] AC-10: A checked-in test verifies `fs2 search` finds and returns section nodes by heading text or content
- [ ] AC-12: A checked-in test verifies embedding generation works for markdown section nodes

## Discoveries & Learnings

_Populated during implementation._

| Date | Task | Type | Discovery | Resolution |
|------|------|------|-----------|------------|
