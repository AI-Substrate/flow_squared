# Fix FX001: Review Fixes + "Just Works" UX

**Created**: 2026-03-15
**Status**: Proposed → Complete
**Plan**: [local-llm-smart-content-plan.md](../local-llm-smart-content-plan.md)
**Source**: plan-7-v2 review (FT-001–FT-004) + workshop 001 UX improvements
**Domain(s)**: adapters (modify), cli (modify), docs (modify)

---

## Problem

The review found 4 issues blocking merge: (1) adapter catches wrong exception classes so connection/timeout errors miss actionable Ollama guidance, (2) test file fails ruff, (3) docs registry doesn't expose local-llm.md via MCP, (4) scan.py duplicates the factory pattern instead of delegating to LLMService.create().

Additionally, the workshop identified that the UX requires too much manual config editing. Users must uncomment YAML, add a smart_content section, and know to install Ollama — when it should "just work" if Ollama is already installed.

## Proposed Fix

Address all 4 review blockers + 3 UX improvements in one pass:

**Review fixes**: Catch `openai.APIConnectionError`/`APITimeoutError`, fix ruff violations, register docs, refactor scan.py factory.

**UX improvements**: Auto-detect Ollama in `fs2 init`, add `smart_content:` to DEFAULT_CONFIG, improve init output messaging.

## Domain Impact

| Domain | Relationship | What Changes |
|--------|-------------|-------------|
| adapters | modify | Fix exception handling in `llm_adapter_local.py` |
| cli | modify | Refactor scan.py factory, enhance init.py with Ollama detection |
| docs | modify | Register local-llm.md, update config-guide metadata |
| tests | modify | Fix ruff violations, align mocks with real SDK exceptions |

## Workshops Consumed

- [001-just-works-ux.md](../workshops/001-just-works-ux.md) — Changes 1-4

## Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | FX001-1 | Fix adapter exception handling: catch `openai.APIConnectionError` + `APITimeoutError` instead of builtins | adapters | `src/fs2/core/adapters/llm_adapter_local.py` | Adapter catches real SDK exceptions; connection error shows install URL; timeout shows model/timeout advice | Review FT-001, AC04, AC12 |
| [x] | FX001-2 | Fix test file: align mocks with real SDK exceptions + pass ruff | tests | `tests/unit/adapters/test_llm_adapter_local.py` | `uv run ruff check` passes; tests raise `APIConnectionError`/`APITimeoutError` not builtins | Review FT-002 |
| [x] | FX001-3 | Register local-llm.md in docs registry + update configuration-guide metadata | docs | `docs/how/user/registry.yaml` | `flowspace-docs_list()` shows `local-llm`; `flowspace-docs_get("local-llm")` returns content | Review FT-003, AC11 |
| [x] | FX001-4 | Refactor scan.py: replace inline adapter factory with `LLMService.create()` | cli | `src/fs2/cli/scan.py` | scan.py no longer imports adapter classes; uses `LLMService.create(config)` | Review FT-004, RF-02 |
| [x] | FX001-5 | Add `smart_content:` section to DEFAULT_CONFIG in init.py | cli | `src/fs2/cli/init.py` | Default config has `smart_content:` block; no "missing smart_content section" error | Workshop Change 2 |
| [x] | FX001-6 | Auto-detect Ollama in `fs2 init`: probe localhost:11434, auto-uncomment LLM config if found | cli | `src/fs2/cli/init.py` | With Ollama running: config auto-enabled + message printed; without: config stays commented + breadcrumb printed | Workshop Change 1 |
| [x] | FX001-7 | Improve init output: mention Ollama/smart content status in post-init message | cli | `src/fs2/cli/init.py` | Users see clear "smart content enabled" or "install Ollama for AI summaries" | Workshop Change 4 |

## Acceptance

- [ ] `uv run ruff check` passes on all touched files
- [ ] `uv run python -m pytest -q` passes (≥1715 tests)
- [ ] Adapter catches `APIConnectionError` → install/start guidance (AC04)
- [ ] Adapter catches `APITimeoutError` → timeout guidance (AC12)
- [ ] `flowspace-docs_list()` shows `local-llm` entry
- [ ] scan.py uses `LLMService.create()` not inline adapter selection
- [ ] `fs2 init` with Ollama running → LLM config auto-enabled
- [ ] `fs2 init` without Ollama → LLM config commented + breadcrumb message
- [ ] DEFAULT_CONFIG includes `smart_content:` section

## Discoveries & Learnings

_Populated during implementation._

| Date | Task | Type | Discovery | Resolution |
|------|------|------|-----------|------------|
