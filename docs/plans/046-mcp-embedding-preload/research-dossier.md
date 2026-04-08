# Research Report: MCP Embedding Model Preloading

**Generated**: 2026-04-07T21:30:00Z
**Research Query**: "When multiple hits are done to the MCP server at the same time when using local embeddings there is a large spike in CPU usage. Preload the embedding model at MCP startup (non-blocking), ensure search calls wait for load, and prevent multiple model instances."
**Mode**: Pre-Plan (Plan-Associated)
**Location**: `docs/plans/046-mcp-embedding-preload/research-dossier.md`
**FlowSpace**: Available ✅
**Findings**: 70 across 8 subagents
**Harness**: Not found
**Domain Registry**: Not found

---

## Executive Summary

### What It Does
The fs2 MCP server exposes semantic search via the `search` tool, which uses a local SentenceTransformer model to embed queries and compare against precomputed node embeddings. Currently, the embedding model is loaded lazily on first use, per-adapter-instance, with no caching across requests.

### Business Purpose
Semantic code search is a core differentiator for fs2. When a coding agent fires multiple concurrent `search` tool calls, each request creates a fresh `SentenceTransformerEmbeddingAdapter`, each of which independently lazy-loads the ~130MB model. This causes severe CPU spikes and duplicated memory usage, degrading the user experience.

### Key Insights
1. **Root cause is double**: (a) the MCP search handler creates a new adapter per request because `get_embedding_adapter()` returns `None`, and (b) the adapter's `_get_model()` has no lock protecting concurrent first-loads.
2. **Singleton infrastructure already exists** in `core/dependencies.py` (`get_embedding_adapter()` / `set_embedding_adapter()` with `RLock`), but MCP startup never populates it.
3. **Architecture is clear**: preload belongs at the MCP composition root, using an `asyncio.Event` to coordinate non-blocking warmup with request readiness, following existing patterns.

### Quick Stats
- **Components**: ~8 files directly involved (MCP server, dependencies, adapter, config, search service)
- **Dependencies**: `sentence-transformers`, `torch`, `numpy`, `fastmcp`
- **Test Coverage**: High for adapters/services, gap on MCP semantic E2E
- **Complexity**: Medium — well-scoped change touching startup + singleton lifecycle
- **Prior Learnings**: 12 relevant discoveries from previous implementations
- **Domains**: No formal domain system; natural boundary between MCP lifecycle and embedding lifecycle

---

## How It Currently Works

### Entry Points

| Entry Point | Type | Location | Purpose |
|-------------|------|----------|---------|
| `fs2 mcp` | CLI Command | `src/fs2/cli/mcp.py:31-61` | Starts MCP server over STDIO |
| `search()` tool | MCP Tool | `src/fs2/mcp/server.py:771-1017` | Handles semantic/text/regex search requests |
| `_get_model()` | Internal | `src/fs2/core/adapters/embedding_adapter_local.py:95-148` | Lazy-loads the SentenceTransformer model |

### Core Execution Flow

1. **MCP Server Startup** (`cli/mcp.py:31-61`)
   - Configures stderr logging (before imports to avoid STDIO corruption)
   - Imports `fs2.mcp.server.mcp` (a module-level `FastMCP` instance)
   - Calls `mcp_server.run()` — starts STDIO transport
   - **No embedding preload happens here**

2. **Search Request Arrives** (`mcp/server.py:892-911`)
   ```python
   adapter = get_embedding_adapter()          # Returns None (never set!)
   if adapter is None:
       adapter = create_embedding_adapter_from_config(config)  # Creates NEW adapter
   service = SearchService(graph_store=store, embedding_adapter=adapter, config=config)
   ```
   - Each request gets a fresh adapter — no caching back to the singleton

3. **Adapter Lazy-Loads Model** (`embedding_adapter_local.py:95-148`)
   ```python
   def _get_model(self):
       if self._model is None:
           from sentence_transformers import SentenceTransformer
           self._model = SentenceTransformer(self._model_name, ...)
       return self._model
   ```
   - Model cached per-instance only — new adapter = new model load
   - No lock around `_get_model()` — concurrent calls on same instance can race

4. **Semantic Search Embeds Query** (`semantic_matcher.py:85-139`)
   ```python
   query_embedding = await self._adapter.embed_text(spec.pattern)
   ```
   - Triggers `_get_model()` if model not yet loaded
   - Then runs `run_in_executor` for sync `encode()` call

### Data Flow
```
MCP Request → search() handler
  → get_embedding_adapter() [returns None]
  → create_embedding_adapter_from_config() [creates NEW adapter]
  → SearchService [creates SemanticMatcher]
  → SemanticMatcher.embed_text()
  → SentenceTransformerEmbeddingAdapter._get_model() [LOADS MODEL ~3-15s]
  → SentenceTransformer.encode() [CPU-bound]
  → cosine similarity against precomputed node embeddings
  → results
```

### Why Concurrent Requests Spike CPU

```
Request 1 ──→ create_adapter() ──→ _get_model() ──→ LOAD MODEL (~130MB, 3-15s)
Request 2 ──→ create_adapter() ──→ _get_model() ──→ LOAD MODEL (~130MB, 3-15s)  ← DUPLICATE!
Request 3 ──→ create_adapter() ──→ _get_model() ──→ LOAD MODEL (~130MB, 3-15s)  ← DUPLICATE!
```

Each concurrent request creates its own adapter with its own model. Three requests = three model loads = 3× CPU + 3× memory.

---

## Architecture & Design

### Component Map

```
┌─────────────────────────────────────────────────────────┐
│  CLI Layer                                               │
│  ├── cli/mcp.py ── configures logging, runs server       │
│  └── cli/search.py ── CLI search (separate path)         │
├─────────────────────────────────────────────────────────┤
│  MCP Layer                                               │
│  ├── mcp/server.py ── FastMCP tools (search/tree/etc)    │
│  └── mcp/dependencies.py ── re-exports core.dependencies │
├─────────────────────────────────────────────────────────┤
│  Core Layer                                              │
│  ├── core/dependencies.py ── singleton cache (RLock)     │
│  ├── core/services/search/ ── SearchService + matchers   │
│  └── core/adapters/                                      │
│      ├── embedding_adapter.py ── ABC + factory           │
│      ├── embedding_adapter_local.py ── SentenceTransformer│
│      ├── embedding_adapter_azure.py ── Azure OpenAI      │
│      ├── embedding_adapter_openai.py ── OpenAI compat    │
│      └── embedding_adapter_fake.py ── test double        │
├─────────────────────────────────────────────────────────┤
│  Config Layer                                            │
│  ├── config/objects.py ── EmbeddingConfig, LocalConfig   │
│  └── config/service.py ── FS2ConfigurationService        │
└─────────────────────────────────────────────────────────┘
```

### Design Patterns Identified

1. **ABC Adapter Pattern** (PS-01): `EmbeddingAdapter` ABC with `embed_text()` / `embed_batch()` contract; 4 implementations (local, azure, openai, fake)
2. **Lazy Singleton Cache** (PS-03): `core/dependencies.py` uses module-level variables + `RLock` for config/graph/adapter singletons
3. **Explicit DI** (PS-02): Services composed via constructor injection — `SearchService(graph_store, embedding_adapter, config)`
4. **Factory Method** (PS-01): `create_embedding_adapter_from_config(config)` selects implementation by `EmbeddingConfig.mode`
5. **Lazy Load on First Use** (PS-05): `TreeService`, `GetNodeService` defer graph loading until needed
6. **Run-in-Executor** (PS-06): Sync `SentenceTransformer.encode()` wrapped in `loop.run_in_executor()` for async compat

### Where Preload Fits in Clean Architecture

| Concern | Layer | File | Rationale |
|---------|-------|------|-----------|
| Trigger preload | Composition root | `cli/mcp.py` or `mcp/server.py` | Startup is a composition concern |
| Cache adapter | Infrastructure | `core/dependencies.py` | Already has `set_embedding_adapter()` |
| Expose warmup | Adapter | `embedding_adapter_local.py` | Model lifecycle is adapter's responsibility |
| Coordinate readiness | Service/MCP | New or `mcp/server.py` | `asyncio.Event` for non-blocking wait |

---

## Dependencies & Integration

### Internal Dependency Chain

```
cli/mcp.py
  └── mcp/server.py (FastMCP instance)
        └── search() handler
              ├── core/dependencies.py (get_embedding_adapter / get_config / get_graph_store)
              ├── core/adapters/embedding_adapter.py (factory)
              │     └── embedding_adapter_local.py (SentenceTransformerEmbeddingAdapter)
              │           └── sentence_transformers.SentenceTransformer
              ├── core/services/search/search_service.py
              │     └── semantic_matcher.py
              └── config/objects.py (EmbeddingConfig → LocalEmbeddingConfig)
```

### External Dependencies

| Library | Purpose | Criticality |
|---------|---------|-------------|
| `sentence-transformers` | Local embedding model | Critical for local mode |
| `torch` | ML backend for SentenceTransformer | Critical for local mode |
| `fastmcp` | MCP protocol server | Critical for MCP |
| `numpy` | Cosine similarity computation | Critical for semantic search |

### Configuration Contract

```yaml
# .fs2/config.yaml
embedding:
  mode: local                          # azure | openai_compatible | local | fake
  local:
    model: BAAI/bge-small-en-v1.5     # HuggingFace model name
    device: auto                       # auto | cpu | cuda | mps
    max_seq_length: 512
```

---

## Quality & Testing

### Current Test Coverage

| Area | Coverage | Location | Notes |
|------|----------|----------|-------|
| EmbeddingAdapter ABC | High | `tests/unit/adapters/test_embedding_adapter_fake.py` | 455 lines of fake adapter tests |
| EmbeddingService | High | `tests/unit/services/test_embedding_service.py` | 1260 lines, batching/chunking/concurrency |
| SearchService | High | `tests/unit/services/test_search_service.py` | Routing, fallback, pagination |
| MCP Tools | High | `tests/mcp_tests/test_search_tool.py` | 1100 lines, all modes |
| MCP E2E | Medium | `tests/mcp_tests/test_mcp_integration.py` | CLI→STDIO, but only TEXT/REGEX |
| MCP Semantic E2E | **Gap** | `tests/mcp_tests/test_mcp_real_embeddings.py` | Gated by Azure creds, partial |
| Embedding Pipeline | High | `tests/integration/test_embedding_pipeline.py` | scan→embed→graph metadata |

### Test Strategy
- **Fakes over mocks**: `FakeEmbeddingAdapter` is the canonical test double
- **Dependency reset**: `conftest.py` resets singletons between tests via `reset_services()`
- **Slow test gating**: Integration tests marked `@pytest.mark.slow`, excluded by default

### Known Issues
- Search `total` is approximate (`server.py:916-921`)
- No lock on `_get_model()` — race condition on concurrent first-load
- No MCP semantic search E2E test in CI

---

## Modification Considerations

### ✅ Safe to Modify
1. **`cli/mcp.py`** — Composition root, few consumers, well-isolated
2. **`core/dependencies.py`** — Already has `set_embedding_adapter()` / `get_embedding_adapter()` with `RLock`
3. **MCP `search()` handler** — Can be updated to use cached adapter

### ⚠️ Modify with Caution
1. **`embedding_adapter_local.py`** — Adding a `warmup()` method is safe, but changing `_get_model()` semantics could affect scan pipeline
   - Risk: Breaking the lazy-load contract for non-MCP paths
   - Mitigation: Make warmup opt-in, keep lazy load as fallback

### 🚫 Danger Zones
1. **`EmbeddingAdapter` ABC** — Adding abstract methods would break all 4 implementations
   - Alternative: Add `warmup()` as a concrete no-op on the base class
2. **Config/factory** — Changing `create_embedding_adapter_from_config()` return behavior could break scan pipeline

### Extension Points
1. **`set_embedding_adapter()`** — Designed for exactly this: inject a pre-created adapter at startup
2. **`EmbeddingAdapter` base class** — Can add optional `warmup()` with default no-op
3. **MCP startup** — `cli/mcp.py` can add async init before `mcp_server.run()`

---

## Prior Learnings (From Previous Implementations)

### 📚 PL-01: First model load is expensive
**Source**: `docs/plans/032-local-embeddings/tasks/implementation/`
**Type**: gotcha
**What They Found**: First model load downloads ~130MB and takes 3-15 seconds.
**Action**: Preload must be non-blocking; don't let it block MCP startup or the agent will kill the process.

### 📚 PL-02: Lazy loading was intentional — don't make it eager in `__init__`
**Source**: `docs/plans/032-local-embeddings/workshops/001-*`
**Type**: decision
**What They Found**: Model loading was deliberately made lazy (first embed call). Don't put it in `__init__`.
**Action**: Use a separate `warmup()` method, not constructor loading. Keep lazy-load as fallback.

### 📚 PL-03: Use thread-safe singleton cache for transformer models
**Source**: `docs/plans/009-embeddings/research-dossier.md`
**Type**: insight
**What They Found**: Instance-level caches cause race risks. Use a single shared singleton.
**Action**: Use `set_embedding_adapter()` to cache one adapter, use `asyncio.Event` for readiness.

### 📚 PL-04: MCP lazy singletons have known race conditions
**Source**: `docs/plans/011-mcp/reviews/review.phase-1-core-infrastructure.md`
**Type**: gotcha
**What They Found**: Concurrent tool calls can create duplicate singleton instances without lock guards.
**Action**: Ensure preload path uses `RLock` (already exists in dependencies.py) and `asyncio.Event` for coordination.

### 📚 PL-05: Phase 4 explicitly added `get/set_embedding_adapter()`
**Source**: `docs/plans/011-mcp/tasks/phase-4-*/`
**Type**: decision
**What They Found**: The singleton cache API was designed for this exact use case.
**Action**: Hook preload into `set_embedding_adapter()`, not a custom cache.

### 📚 PL-06: Graph store needs pre-warming too
**Source**: `docs/plans/011-mcp/reviews/review.phase-1-core-infrastructure.md`
**Type**: insight
**What They Found**: First graph store access does sync I/O (10-100ms).
**Action**: Consider warming graph store alongside embedding adapter at startup.

### 📚 PL-07: Graph must be `load()`ed before search
**Source**: `docs/plans/010-search/tasks/phase-5-*/`
**Type**: gotcha
**What They Found**: `get_all_nodes()` returns empty if graph not loaded first.
**Action**: If preloading embedding at startup, ensure graph load order is correct.

### 📚 PL-09: `encode()` is sync and CPU/GPU-bound
**Source**: `docs/plans/032-local-embeddings/workshops/001-*`
**Type**: insight
**What They Found**: `SentenceTransformer.encode()` blocks the thread; wrapped in `run_in_executor`.
**Action**: Model *loading* is also sync/CPU-bound — preload must also use executor or background thread.

### 📚 PL-10: Platform device quirks
**Source**: `docs/plans/032-local-embeddings/local-embeddings-spec.md`
**Type**: gotcha
**What They Found**: macOS needs `pool=None`; device order is CUDA > MPS > CPU.
**Action**: Preload must use the same device detection path as normal load.

### 📚 PL-11: Memory pressure with large models
**Source**: `docs/plans/009-embeddings/embeddings-plan.md`
**Type**: insight
**What They Found**: 10k nodes × 3072 dims ≈ 240MB. Keep defaults small, avoid multiple model copies.
**Action**: Singleton preload prevents duplicate model copies — this is the fix.

### 📚 PL-12: Use `asyncio.Event` for coordination
**Source**: `docs/plans/009-embeddings/tasks/phase-3-*/`
**Type**: decision
**What They Found**: Batch/concurrency design should stay stateless, use bounded concurrency with `asyncio.Event`.
**Action**: Use `asyncio.Event` to signal "model ready" — search waits on event, preload sets it.

### Prior Learnings Summary

| ID | Type | Source Plan | Key Insight | Action |
|----|------|-------------|-------------|--------|
| PL-01 | gotcha | 032-local-embeddings | First load is 3-15s, ~130MB | Non-blocking preload |
| PL-02 | decision | 032-local-embeddings | Lazy load was intentional | Use warmup(), not __init__ |
| PL-03 | insight | 009-embeddings | Singleton cache prevents races | Use set_embedding_adapter() |
| PL-04 | gotcha | 011-mcp | MCP singletons race without locks | Use existing RLock |
| PL-05 | decision | 011-mcp | get/set_embedding_adapter() was designed for this | Hook into existing API |
| PL-06 | insight | 011-mcp | Graph store needs warming too | Consider dual preload |
| PL-09 | insight | 032-local-embeddings | encode() is CPU-bound | Preload via executor/thread |
| PL-10 | gotcha | 032-local-embeddings | macOS needs pool=None | Reuse device detection |
| PL-11 | insight | 009-embeddings | Memory pressure is real | Singleton prevents duplicates |
| PL-12 | decision | 009-embeddings | asyncio.Event for coordination | Signal readiness to waiters |

---

## Critical Discoveries

### 🚨 Critical Finding 01: Adapter Not Cached After Creation
**Impact**: Critical
**Source**: IA-03, IA-04, DC-01, DC-10
**Files**: `mcp/server.py:892-911`, `core/dependencies.py:164-188`
**What**: The MCP `search()` handler calls `create_embedding_adapter_from_config()` when `get_embedding_adapter()` returns `None`, but never caches the result via `set_embedding_adapter()`. Every concurrent request creates a new adapter.
**Required Action**: Either (a) set the adapter at startup, or (b) cache after first creation, or (c) both.

### 🚨 Critical Finding 02: No Lock on Model Loading
**Impact**: Critical
**Source**: IA-06, DC-05, PL-04
**Files**: `embedding_adapter_local.py:95-148`
**What**: `_get_model()` has no threading lock. Even if only one adapter exists, concurrent calls can trigger parallel model loads before the first completes.
**Required Action**: Add a lock around `_get_model()`, or ensure only one call ever reaches it via the singleton + event pattern.

### 🚨 Critical Finding 03: Non-Blocking Requirement
**Impact**: Critical
**Source**: PL-01, PL-02, user requirement
**What**: MCP server must respond to capability negotiation quickly. If preload blocks startup, the coding agent may kill the process (timeout). Model load takes 3-15 seconds.
**Required Action**: Preload must be async/background — fire-and-forget with an `asyncio.Event` that search requests await.

---

## Recommended Solution Architecture

Based on all findings, the recommended approach:

```
MCP Startup (cli/mcp.py or mcp/server.py)
  │
  ├── 1. Create adapter via create_embedding_adapter_from_config()
  ├── 2. Cache via set_embedding_adapter(adapter)
  ├── 3. Fire background task: adapter.warmup()  [non-blocking]
  │      └── Sets asyncio.Event when model loaded
  └── 4. mcp_server.run()  [starts immediately, doesn't wait]

Search Request
  │
  ├── get_embedding_adapter()  [returns cached adapter]
  ├── await adapter._model_ready.wait()  [blocks until warmup done]
  └── proceed with semantic search  [model already loaded]
```

**Key design decisions**:
1. `warmup()` as a concrete method on `EmbeddingAdapter` base (no-op default)
2. `SentenceTransformerEmbeddingAdapter` overrides to trigger `_get_model()` in executor
3. `asyncio.Event` (`_model_ready`) set after model loads; `embed_text()`/`embed_batch()` await it
4. `set_embedding_adapter()` at MCP startup guarantees singleton
5. `threading.Lock` around `_get_model()` as belt-and-suspenders safety

---

## Domain Context

> No domain registry found. Consider running `/plan-v2-extract-domain` to formalize domain boundaries.

**Natural boundaries identified**:
- **MCP Server Lifecycle**: startup, tool registration, shutdown — composition root concern
- **Embedding Model Lifecycle**: load, warmup, encode, unload — adapter concern
- **Search Request Handling**: routing, matching, ranking — service concern

The preload feature crosses the MCP/Embedding boundary, which is expected for a composition-root coordination concern.

---

## External Research Opportunities

### Research Opportunity 1: asyncio.Event + run_in_executor best practices

**Why Needed**: The preload fires a background task via `run_in_executor` and signals readiness via `asyncio.Event`. Need to confirm this pattern is correct for FastMCP's event loop model.
**Impact on Plan**: Incorrect event loop usage could deadlock or silently fail.
**Source Findings**: PL-09, PL-12, PS-06

**Ready-to-use prompt:**
```
/deepresearch "Best practices for combining asyncio.Event with concurrent.futures.ThreadPoolExecutor (run_in_executor) in Python 3.12. Specifically: (1) Can run_in_executor safely call event.set() from the background thread? (2) Should we use loop.call_soon_threadsafe(event.set) instead? (3) What happens if the event loop isn't running yet when the background thread completes? Context: FastMCP server using STDIO transport, Python 3.12, need to preload a SentenceTransformer model in background thread and signal readiness to async tool handlers."
```

---

## Appendix: File Inventory

### Core Files

| File | Purpose | Key Lines |
|------|---------|-----------|
| `src/fs2/cli/mcp.py` | MCP CLI command, composition root | 31-61 |
| `src/fs2/mcp/server.py` | FastMCP instance, tool handlers | 34-85, 771-1017 |
| `src/fs2/core/dependencies.py` | Singleton cache with RLock | 47-242 |
| `src/fs2/core/adapters/embedding_adapter.py` | ABC + factory | 20-178 |
| `src/fs2/core/adapters/embedding_adapter_local.py` | SentenceTransformer impl | 30-190 |
| `src/fs2/core/services/search/search_service.py` | Search routing/orchestration | 61-239 |
| `src/fs2/core/services/search/semantic_matcher.py` | Semantic search + cosine sim | 68-226 |
| `src/fs2/config/objects.py` | EmbeddingConfig, LocalEmbeddingConfig | 570-808 |

### Test Files

| File | Purpose |
|------|---------|
| `tests/unit/adapters/test_embedding_adapter_fake.py` | Fake adapter tests |
| `tests/unit/services/test_embedding_service.py` | Embedding service tests |
| `tests/unit/services/test_search_service.py` | Search service tests |
| `tests/mcp_tests/test_search_tool.py` | MCP search tool tests |
| `tests/mcp_tests/test_mcp_integration.py` | MCP E2E tests |
| `tests/mcp_tests/conftest.py` | MCP test fixtures, dependency resets |

---

## Next Steps

1. **Optional**: Run `/deepresearch` prompt above for asyncio.Event + executor safety
2. **Proceed**: Run `/plan-1b-specify` to create the feature specification
3. **Then**: `/plan-3-architect` for implementation plan

---

**Research Complete**: 2026-04-07T21:30:00Z
**Report Location**: `docs/plans/046-mcp-embedding-preload/research-dossier.md`
