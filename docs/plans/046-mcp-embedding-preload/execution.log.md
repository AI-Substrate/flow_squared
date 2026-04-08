# Execution Log: 046 MCP Embedding Preload

**Plan**: `mcp-embedding-preload-plan.md`
**Mode**: Simple
**Started**: 2026-04-07

---

## Baseline

| Check | Status | Details |
|-------|--------|---------|
| Tests | ⚠️ | 1905 passed, 18 failed (pre-existing), 31 skipped, 357 deselected |
| Lint | — | Will verify after changes |

Pre-existing failures: Windows paths (3), async event loop (2), report service (7), secrets loading (2), graph service (2), permission error (1), leading context (1). None related to our changes.

---

## Task Log

### T007: TDD tests — thread-safe model loading ✅
- Created `tests/unit/adapters/test_embedding_adapter_local_warmup.py` — 10 tests
- Tests cover: concurrent `_get_model()`, error storage/re-raise, warmup lifecycle, background thread safety, waiting log message
- Used fake `sentence_transformers` module with controlled delay (DYK#4)
- **Discovery**: Offline-first retry pattern means `SentenceTransformer` constructor is called twice on failure (once with `local_files_only=True`, once without). Test adjusted to check no additional retries on second `_get_model()` call.

### T001: Add warmup() to ABC ✅
- Added concrete `warmup()` no-op to `EmbeddingAdapter` in `embedding_adapter.py`
- `# noqa: B027` suppresses ruff warning for intentional empty method in ABC
- Non-abstract — all 4 implementations unchanged

### T002: Thread-safe _get_model() ✅
- Added `threading.Lock` and `_model_error` to `SentenceTransformerEmbeddingAdapter.__init__()`
- Rewrote `_get_model()` with double-checked locking (DYK#1)
- Added "Waiting for embedding model to load..." log message (DYK#3)
- Error includes "Restart `fs2 mcp` after resolving the issue" (DYK#5)
- Stored `EmbeddingAdapterError` in `_model_error` prevents retries

### T003: Override warmup() in local adapter ✅
- Added `warmup()` method that calls `_get_model()` and catches `EmbeddingAdapterError`
- Logs warning on failure; error stored in `_model_error` for re-raise on search

### T004: Lock set_embedding_adapter() ✅
- Wrapped `set_embedding_adapter()` body in `with _lock:` block
- Existing `reset_services()` already clears `_embedding_adapter = None` — sufficient

### T005: MCP startup preload ✅
- Added `_preload_embedding_adapter()` function to `cli/mcp.py`
- Called after logging config, before `mcp_server.run()`
- Creates adapter via factory, caches with `set_embedding_adapter()`, fires daemon warmup thread
- Graceful: catches all errors, returns silently if no adapter available

### T006: Cache fallback adapter ✅
- Updated MCP `search()` handler in `server.py`
- When fallback `create_embedding_adapter_from_config()` creates adapter, caches it
- DYK#2: `if adapter is not None` guard prevents caching None

### T008: Preload lifecycle tests ✅
- Created `tests/mcp_tests/test_mcp_embedding_preload.py` — 12 tests
- Tests cover: singleton lifecycle, thread-safe setter, cached adapter usage, graceful degradation (missing deps, non-local mode, missing config), _preload_embedding_adapter() function, reset_services() clearing

## Final Results

| Check | Status | Details |
|-------|--------|---------|
| New tests | ✅ | 22/22 pass (10 warmup + 12 preload) |
| Full suite | ✅ | 1927 passed, 18 failed (pre-existing), 31 skipped, 357 deselected |
| Regressions | ✅ | 0 new failures |
| Lint | ✅ | All changed files pass ruff |

## Discoveries & Learnings

| ID | Type | Discovery | Action Taken |
|----|------|-----------|--------------|
| D01 | gotcha | Offline-first retry in `_get_model()` means `SentenceTransformer` constructor is called twice on load failure | Adjusted error storage test to check no additional retries on 2nd call rather than total call count |
| D02 | insight | `threading.Lock` is simpler and safer than `asyncio.Event` for this use case — avoids all cross-thread event signaling risks | Used Lock instead of Event; eliminated workshop opportunity |
| D03 | decision | B027 ruff rule flags empty ABC methods — suppressed with `# noqa: B027` since warmup is intentionally non-abstract | Added inline suppression |
