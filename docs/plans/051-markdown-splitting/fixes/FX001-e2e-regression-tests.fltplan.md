# Flight Plan: Fix FX001 — E2E Regression Tests

**Fix**: [FX001-e2e-regression-tests.md](./FX001-e2e-regression-tests.md)
**Status**: Ready

## What → Why

**Problem**: AC-09 (tree), AC-10 (search), AC-12 (embedding) have no checked-in regression tests — only manual verification from code review.
**Fix**: Add 3 targeted integration tests to existing service test files.

## Domain Context

| Domain | Relationship | What Changes |
|--------|-------------|-------------|
| AST Parsing | consume | Tests only — no production code |

## Stages

- [ ] FX001-1: Tree service test — section nodes as file children
- [ ] FX001-2: Search service test — section nodes returned for queries
- [ ] FX001-3: Embedding service test — section nodes receive embeddings

## Acceptance

- [ ] AC-09: tree shows sections as children
- [ ] AC-10: search returns section nodes
- [ ] AC-12: embedding works for sections
