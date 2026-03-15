# Flight Plan: Fix FX001 — Review Fixes + "Just Works" UX

**Fix**: [FX001-review-fixes-and-ux.md](FX001-review-fixes-and-ux.md)
**Status**: Landed ✅

## What → Why

**Problem**: Adapter catches wrong exceptions (AC04/AC12 broken), test file fails ruff, docs not discoverable via MCP, scan.py duplicates factory, and UX requires too much manual config editing.

**Fix**: Catch real SDK exceptions, pass ruff, register docs, refactor factory, auto-detect Ollama in `fs2 init`, add smart_content to default config.

## Domain Context

| Domain | Relationship | What Changes |
|--------|-------------|-------------|
| adapters | modify | Exception handling in llm_adapter_local.py |
| cli | modify | scan.py factory refactor, init.py Ollama detection + smart_content |
| docs | modify | registry.yaml + configuration-guide metadata |
| tests | modify | Ruff fixes + faithful SDK exception mocks |

## Stages

- [x] **Stage 1: Fix adapter + tests** — catch `APIConnectionError`/`APITimeoutError`, align test mocks, pass ruff (FX001-1, FX001-2)
- [x] **Stage 2: Fix docs + factory** — register local-llm.md, refactor scan.py to use `LLMService.create()` (FX001-3, FX001-4)
- [x] **Stage 3: UX improvements** — add smart_content to DEFAULT_CONFIG, auto-detect Ollama in init, improve init output (FX001-5, FX001-6, FX001-7)

## Acceptance

- [ ] `uv run ruff check` passes on all touched files
- [ ] `uv run python -m pytest -q` ≥1715 passed
- [ ] Adapter catches real SDK exceptions with actionable messages
- [ ] MCP docs discovery surfaces local-llm guide
- [ ] scan.py delegates to LLMService.create()
- [ ] `fs2 init` auto-detects Ollama and configures accordingly
