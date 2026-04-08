# MCP Embedding Model Preload

**Mode**: Simple

📚 This specification incorporates findings from `research-dossier.md`

## Research Context

The research dossier (70 findings, 8 subagents) identified three critical problems in the current MCP embedding flow:

1. **Adapter created per-request, never cached**: `search()` handler calls `create_embedding_adapter_from_config()` each time `get_embedding_adapter()` returns `None`, but never stores the result back. Concurrent requests each create separate adapters.
2. **No lock on model loading**: `_get_model()` in `SentenceTransformerEmbeddingAdapter` has no threading protection. Even a single adapter instance can load the model multiple times under concurrency.
3. **Model load takes 3-15 seconds**: Loading the ~130MB SentenceTransformer model is CPU-bound and slow. If preload blocks MCP startup, the coding agent may kill the process on timeout.

Prior learnings from plans 009, 011, and 032 confirm: (a) `get/set_embedding_adapter()` was designed for singleton caching, (b) `asyncio.Event` is the recommended coordination primitive, (c) lazy loading was intentional — warmup should be opt-in, not baked into `__init__`.

## Summary

When multiple concurrent search requests hit the fs2 MCP server using local embeddings, each request independently creates a new embedding adapter and loads the SentenceTransformer model from scratch. This causes severe CPU spikes and duplicated memory usage (~130MB per instance), degrading the experience for coding agents that commonly fire parallel `search` tool calls.

This feature makes the MCP server pre-create and cache a single embedding adapter at startup, then trigger a non-blocking background warmup of the underlying model. Search requests that arrive before the model is ready wait (without blocking the server) until warmup completes. The result: one model instance, zero duplicate loads, and no startup timeout risk.

## Goals

- **Eliminate duplicate model loads**: Ensure only one SentenceTransformer model instance exists across all concurrent MCP search requests
- **Reduce CPU spikes**: Remove the pattern where N concurrent searches trigger N independent model loads
- **Non-blocking startup**: MCP server must begin accepting tool calls immediately — model warmup happens in the background so the coding agent doesn't timeout waiting for capability negotiation
- **Transparent to search callers**: Semantic search requests that arrive during warmup should wait automatically and then proceed normally, with no changes to the search tool's external behavior
- **Graceful degradation preserved**: If local embeddings are not configured or `sentence-transformers` is not installed, behavior remains unchanged (search falls back to text mode)
- **No impact on non-MCP paths**: The CLI `fs2 search` command and the `fs2 scan --embed` pipeline continue to work exactly as before

## Non-Goals

- **Preloading the graph store at MCP startup**: While the research dossier notes graph store warming (PL-06), that's a separate optimization. This feature focuses solely on the embedding model lifecycle.
- **Adding a generic "preload everything" framework**: This is a targeted fix for the embedding model, not an extensible warm-up infrastructure.
- **Changing the embedding adapter ABC contract with new abstract methods**: The ABC should remain backward-compatible. Any warmup capability should be optional/concrete.
- **Supporting hot-reload of the embedding model**: If config changes, the user restarts the MCP server. No runtime model swapping.
- **Optimizing model inference speed**: This feature prevents duplicate loads; it does not tune `encode()` performance or change batching behavior.
- **Preloading for API-based providers (Azure, OpenAI)**: API providers have no heavy model to load — their "warmup" is effectively free. This is a local-embeddings-only concern.

## Target Domains

| Domain | Status | Relationship | Role in This Feature |
|--------|--------|-------------|---------------------|
| mcp-server | no registry | **modify** | Add non-blocking preload trigger at server startup; update search handler to use cached adapter |
| embedding-adapters | no registry | **modify** | Add optional warmup capability and thread-safe model loading to local adapter |
| dependencies | no registry | **modify** | Leverage existing `get/set_embedding_adapter()` singleton cache for adapter lifecycle |
| config | no registry | **consume** | Read embedding config to determine if preload is applicable (local mode only) |

> ℹ️ No formal domain registry (`docs/domains/registry.md`) exists. Domain names above reflect natural architectural boundaries identified in the research dossier.

## Complexity

- **Score**: CS-3 (medium)
- **Breakdown**: S=1, I=0, D=1, N=0, F=2, T=1 (Total P=5)
- **Confidence**: 0.85

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Surface Area (S) | 1 | ~6-8 files across MCP server, dependencies, adapter, and tests |
| Integration (I) | 0 | All internal; sentence-transformers already integrated |
| Data/State (D) | 1 | New coordination state (readiness event), but no schema/migration |
| Novelty (N) | 0 | Well-researched; prior learnings provide clear patterns |
| Non-Functional (F) | 2 | Core motivation is performance; concurrency safety is critical |
| Testing/Rollout (T) | 1 | Needs concurrency-aware integration tests beyond unit tests |

- **Assumptions**:
  - FastMCP's event loop is compatible with `asyncio.Event` + `run_in_executor` coordination
  - The existing `RLock` in `dependencies.py` is sufficient for thread safety
  - Model warmup in background thread does not interfere with STDIO transport

- **Dependencies**:
  - `sentence-transformers` and `torch` (already optional dependencies)
  - `fastmcp` (already a dependency)
  - No new external dependencies required

- **Risks**:
  - Event loop threading: `asyncio.Event.set()` from a background thread requires `call_soon_threadsafe` — incorrect usage could deadlock or silently fail
  - Startup order: If the MCP event loop isn't fully running when the warmup task is scheduled, the task may not execute
  - Error handling: If model download fails during warmup (e.g., first-time use offline), the error must be surfaced gracefully when search is attempted, not silently swallowed at startup

- **Phases**: 2-3 phases suggested:
  1. Singleton caching + thread-safe model loading (fix the immediate duplication bug)
  2. Non-blocking preload at MCP startup with readiness coordination
  3. Tests for concurrent search scenarios

## Acceptance Criteria

1. **Single adapter instance**: When the MCP server handles 5 concurrent semantic search requests, only one `SentenceTransformerEmbeddingAdapter` instance is created across all requests.

2. **Single model load**: When the MCP server handles 5 concurrent semantic search requests, the SentenceTransformer model is loaded exactly once — not once per request.

3. **Non-blocking startup**: The MCP server responds to the first `tools/list` capability negotiation request within 2 seconds of launch, regardless of how long the embedding model takes to load.

4. **Search waits for warmup**: If a semantic search request arrives while the model is still loading, the request waits until the model is ready and then returns correct results — it does not fail or fall back to text mode.

5. **Text/regex unaffected**: Text and regex search modes work immediately upon server startup, without waiting for embedding model warmup.

6. **Graceful degradation**: If `sentence-transformers` is not installed or embedding mode is not `local`, the MCP server starts normally with no preload attempt and search falls back to text mode as before.

7. **Error surfacing**: If the model fails to load during warmup (e.g., download failure), the error is returned to the search caller with actionable fix instructions — no silent fallback to text mode, no server crash at startup.

8. **No regression on non-MCP paths**: `fs2 search` (CLI) and `fs2 scan --embed` continue to work exactly as before — the preload behavior is specific to MCP server startup.

9. **Thread safety**: Concurrent calls to `_get_model()` on the same adapter instance result in exactly one model load — subsequent calls wait for and reuse the result of the first load.

10. **Memory efficiency**: After the server has handled search requests, only one copy of the model exists in memory, verified by adapter instance count.

## Risks & Assumptions

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `asyncio.Event.set()` from background thread causes race | Medium | High | Use `loop.call_soon_threadsafe(event.set)` pattern; test explicitly |
| Warmup task not scheduled if event loop not yet running | Low | High | Schedule warmup using FastMCP's startup hook or `asyncio.create_task` after loop starts |
| Model download on first use blocks warmup indefinitely | Low | Medium | Set a timeout on warmup; surface download status via logging to stderr |
| Breaking lazy-load contract for scan pipeline | Low | Medium | Warmup is opt-in via explicit call; lazy load remains as fallback for all paths |
| `reset_services()` in tests clears singleton mid-warmup | Low | Low | Ensure test teardown properly awaits/cancels warmup tasks |

### Assumptions

- The FastMCP STDIO transport starts an asyncio event loop that is accessible for scheduling background tasks
- The `RLock` in `dependencies.py` is sufficient for thread-safe singleton management (no need for a separate lock)
- One warmup approach works across all platforms (Windows, macOS, Linux) with the existing device detection logic
- The model download path (first-time use) is acceptable to happen during warmup — the user has previously run `fs2 scan --embed` which would have triggered the download

## Open Questions

*All resolved — see Clarifications section.*

## Testing Strategy

- **Approach**: Hybrid — TDD for thread-safety and concurrency logic (lock around `_get_model()`, readiness event coordination, concurrent search handling), lightweight for wiring/config changes (singleton caching, MCP startup hookup)
- **Mock Policy**: Avoid mocks entirely — use real data/fixtures and project-standard fakes (`FakeEmbeddingAdapter`). Per project convention: fakes over mocks.
- **Focus Areas**:
  - Thread-safe model loading: concurrent `_get_model()` calls yield exactly one load (TDD)
  - Readiness coordination: search waits for warmup, text/regex bypass it (TDD)
  - Singleton lifecycle: adapter cached on first creation, reused across requests (lightweight)
  - Graceful degradation: no preload when `sentence-transformers` absent (lightweight)
  - Error propagation: warmup failure surfaces on first semantic search (TDD)
- **Excluded**: No benchmarking suite; no real model loading in CI (too slow/heavy)

## Documentation Strategy

- **Location**: No new documentation. This is internal plumbing — the MCP server and search tool interfaces remain unchanged.
- **Rationale**: Preload is invisible to users. No new CLI flags, config options, or behavioral changes to document. Existing MCP and search docs remain accurate.

## Workshop Opportunities

| Topic | Type | Why Workshop | Key Questions |
|-------|------|--------------|---------------|
| asyncio.Event + executor thread safety | Integration Pattern | Correct cross-thread signaling between background model load and async MCP handlers is critical — incorrect usage can deadlock | Can `asyncio.Event.set()` be called from executor thread? Should we use `call_soon_threadsafe`? What's the FastMCP event loop lifecycle? |
| Warmup lifecycle state machine | State Machine | Model goes through states: not-started → loading → ready / failed. Need clean state transitions and error propagation | How to propagate warmup errors to first search caller? How to handle warmup cancellation on shutdown? What happens on retry? |

## Clarifications

### Session 2026-04-07

**Q1: Workflow Mode** → **Simple**. Single-phase plan, inline tasks. Despite CS-3 rating, the change is well-scoped with clear patterns from prior learnings.

**Q2: Testing Strategy** → **Hybrid**. TDD for concurrency/thread-safety logic, lightweight for wiring/config. No mocks — fakes only per project convention.

**Q3: Mock Usage** → **Avoid mocks entirely**. Use `FakeEmbeddingAdapter` and real fixtures. Matches project convention of fakes over mocks.

**Q4: Harness** → **Continue without harness**. Feature is internal plumbing. Validate via unit tests and existing MCP integration tests.

**Q5: Domain Review** → **Confirmed**. All 4 domains (mcp-server, embedding-adapters, dependencies, config) and their roles are correct. No adjustments needed.

**Q6: Config toggle** → **No config option**. Always preload when local mode is configured. Preload is always beneficial and uses the same memory as lazy load. Simpler implementation.

**Q7: CLI applicability** → **MCP-only**. CLI search is single-shot; preload adds overhead for no benefit. Preload is specific to the long-running MCP server lifecycle.

**Q8: Warmup failure behavior** → **Fail loudly**. Return error to the search caller with fix instructions. No silent fallback to text mode — the user configured semantic search and should know it's broken.
