# MCP Embedding Model Preload — Implementation Plan

**Mode**: Simple
**Plan Version**: 1.0.0
**Created**: 2026-04-07
**Spec**: `docs/plans/046-mcp-embedding-preload/mcp-embedding-preload-spec.md`
**Status**: COMPLETE

## Summary

When multiple concurrent MCP search requests use local embeddings, each request creates a separate `SentenceTransformerEmbeddingAdapter` and independently loads the ~130MB model, causing severe CPU spikes and memory duplication. This plan adds: (1) a `threading.Lock` around model loading to prevent concurrent duplicate loads, (2) singleton adapter caching at MCP startup via the existing `set_embedding_adapter()` API, and (3) a non-blocking background warmup thread so the model is ready before the first search arrives — without blocking MCP capability negotiation.

## Target Domains

| Domain | Status | Relationship | Role |
|--------|--------|-------------|------|
| embedding-adapters | no registry | **modify** | Thread-safe `_get_model()`, `warmup()` method, error storage |
| dependencies | no registry | **modify** | Lock `set_embedding_adapter()`, reset warmup state |
| mcp-server | no registry | **modify** | Startup preload, fallback adapter caching in search handler |
| config | no registry | **consume** | Read embedding config for preload decision |

## Domain Manifest

| File | Domain | Classification | Rationale |
|------|--------|---------------|-----------|
| `src/fs2/core/adapters/embedding_adapter.py` | embedding-adapters | contract | Add concrete `warmup()` no-op on ABC |
| `src/fs2/core/adapters/embedding_adapter_local.py` | embedding-adapters | internal | Thread-safe `_get_model()`, `warmup()` override, error storage |
| `src/fs2/core/dependencies.py` | dependencies | internal | Lock setter, warmup state in `reset_services()` |
| `src/fs2/cli/mcp.py` | mcp-server | internal | Embedding preload at MCP startup |
| `src/fs2/mcp/server.py` | mcp-server | internal | Cache fallback adapter in search handler |
| `tests/unit/adapters/test_embedding_adapter_local_warmup.py` | tests | new | Thread-safe loading, warmup, error propagation |
| `tests/mcp_tests/test_mcp_embedding_preload.py` | tests | new | Preload lifecycle, singleton caching, graceful degradation |

## Key Findings

| # | Impact | Finding | Action |
|---|--------|---------|--------|
| 01 | Critical | `asyncio.Event.set()` from executor thread is unsafe (IR-02) | **Not applicable** — design uses `threading.Lock` instead of `asyncio.Event`, avoiding cross-thread event signaling entirely. Lock naturally serializes warmup thread and executor threads. |
| 02 | High | `set_embedding_adapter()` writes without lock (IR-03) | Guard with existing `_lock` in T003 |
| 03 | High | First search can bypass preload if singleton absent (IR-04) | Preload sets singleton before `mcp.run()` in T004; fallback path also caches in T005 |
| 04 | High | `reset_services()` doesn't cover warmup state (IR-06) | No module-level warmup state needed — warmup state lives on the adapter instance, which is already cleared by `_embedding_adapter = None` |
| 05 | High | No existing warmup/preload pattern to reuse (IR-07) | Simple `threading.Thread(target=adapter.warmup, daemon=True)` — no framework needed |
| 06 | High | No MCP startup hook in fs2 (IR-01) | Preload runs before `mcp.run()` in `cli/mcp.py` — no hook needed |

### Design Decision: `threading.Lock` over `asyncio.Event`

The research dossier and prior learnings recommended `asyncio.Event` for coordination. After implementation-focused analysis, a simpler design emerged:

- **`threading.Lock`** on `_get_model()` naturally serializes all model access
- Warmup thread calls `_get_model()` → acquires lock → loads model → releases lock
- Search request calls `_encode_sync()` → `_get_model()` → blocks on lock if warmup in progress → gets cached model
- No cross-thread `asyncio.Event` signaling needed (avoids IR-02 entirely)
- `run_in_executor` already runs `_encode_sync` in a thread → lock works naturally
- Event loop stays free while executor threads block on the lock

This eliminates the highest-risk finding (IR-02) and the workshop opportunity for asyncio thread safety.

## Implementation

**Objective**: Eliminate duplicate embedding model loads in MCP server via singleton caching, thread-safe loading, and non-blocking startup warmup.
**Testing Approach**: Hybrid — TDD for thread-safety and concurrency logic, lightweight for wiring. Fakes only, no mocks.

### Tasks

| Status | ID | Task | Domain | Path(s) | Done When | Notes |
|--------|-----|------|--------|---------|-----------|-------|
| [x] | T007 | TDD tests: thread-safe model loading | tests | `tests/unit/adapters/test_embedding_adapter_local_warmup.py` | 10 tests, all pass | Complete |
| [x] | T001 | Add concrete `warmup()` no-op to EmbeddingAdapter ABC | embedding-adapters | `src/fs2/core/adapters/embedding_adapter.py` | Complete | `# noqa: B027` for intentional no-op |
| [x] | T002 | Thread-safe `_get_model()` with lock and error storage | embedding-adapters | `src/fs2/core/adapters/embedding_adapter_local.py` | Complete | DYK#1,#3,#5 applied |
| [x] | T003 | Override `warmup()` in local adapter | embedding-adapters | `src/fs2/core/adapters/embedding_adapter_local.py` | Complete | Catches errors, logs warning |
| [x] | T004 | Lock `set_embedding_adapter()` | dependencies | `src/fs2/core/dependencies.py` | Complete | Guarded by `_lock` |
| [x] | T005 | Add embedding preload to MCP startup | mcp-server | `src/fs2/cli/mcp.py` | Complete | `_preload_embedding_adapter()` + daemon thread |
| [x] | T006 | Cache fallback adapter in MCP search handler | mcp-server | `src/fs2/mcp/server.py` | Complete | DYK#2 None guard applied |
| [x] | T008 | Tests: preload lifecycle and graceful degradation | tests | `tests/mcp_tests/test_mcp_embedding_preload.py` | 12 tests, all pass | Complete |

### Task Dependencies

```
T001 (ABC warmup) ──┐
                     ├──→ T003 (local warmup override)
T002 (thread-safe) ──┘
T004 (lock setter) ── standalone
T005 (MCP preload) ──→ depends on T001, T002, T003, T004
T006 (search cache) ── standalone (but logically after T005)
T007 (TDD tests) ──→ write BEFORE T002 (TDD)
T008 (preload tests) ──→ write AFTER T005, T006
```

### Recommended Execution Order

1. **T007** — Write thread-safety tests first (TDD)
2. **T001** — Add `warmup()` to ABC
3. **T002** — Thread-safe `_get_model()` with lock
4. **T003** — Override `warmup()` in local adapter → T007 tests pass
5. **T004** — Lock `set_embedding_adapter()`
6. **T005** — MCP startup preload
7. **T006** — Cache fallback adapter
8. **T008** — Preload lifecycle tests

### Acceptance Criteria

- [x] AC-1: 5 concurrent semantic search requests create only one adapter instance
- [x] AC-2: 5 concurrent semantic search requests load the model exactly once
- [x] AC-3: MCP server responds to `tools/list` within 2 seconds of launch
- [x] AC-4: Semantic search arriving during warmup waits and returns correct results
- [x] AC-5: Text/regex search works immediately, no warmup wait
- [x] AC-6: No preload attempt when `sentence-transformers` absent or mode ≠ `local`
- [x] AC-7: Warmup failure surfaces as actionable error on first semantic search
- [x] AC-8: `fs2 search` CLI and `fs2 scan --embed` work unchanged
- [x] AC-9: Concurrent `_get_model()` calls yield exactly one model load
- [x] AC-10: Only one model copy in memory after serving search requests

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Warmup thread not started before first search | Low | Medium | `set_embedding_adapter()` runs synchronously before `mcp.run()` — adapter is cached even if warmup hasn't finished. Lock serializes access. |
| Model download blocks warmup (first-time use) | Low | Medium | User typically runs `fs2 scan --embed` first which downloads the model. Warmup logs download progress to stderr. |
| Executor thread pool exhaustion during warmup | Very Low | Low | Default pool has 8-32 workers. One blocked on lock for 3-15s is negligible. |
| `daemon=True` thread killed on shutdown mid-load | Low | None | No harm — next startup re-warms. No state corruption since lock is released. |
| Existing tests break due to ABC change | Very Low | Medium | `warmup()` is concrete no-op — no override required. Run full test suite. |
