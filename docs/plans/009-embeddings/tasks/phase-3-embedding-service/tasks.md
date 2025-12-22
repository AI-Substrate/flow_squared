# Phase 3: Embedding Service – Tasks & Alignment Brief

**Spec**: [embeddings-spec.md](../../embeddings-spec.md)
**Plan**: [embeddings-plan.md](../../embeddings-plan.md)
**Phase Slug**: `phase-3-embedding-service`
**Date**: 2025-12-21
**Updated**: 2025-12-21 (Corrected batching architecture per FlowSpace pattern)

---

## Executive Briefing

### Purpose

This phase implements the `EmbeddingService` that orchestrates embedding generation for CodeNode batches. The service acts as the composition layer between the CLI/pipeline and the embedding adapters, handling content chunking, **API-level batch processing**, hash-based skip logic, and rate limit coordination. Without this service, the pipeline cannot generate embeddings—this is the engine that drives the embedding feature.

### What We're Building

An `EmbeddingService` class that:
- Chunks content based on content-type parameters (code=400, docs=800, smart_content=8000 tokens)
- **Collects items and splits into fixed-size batches** (default: 16 texts per API call)
- **Sends ONE API call per batch** (not parallel individual calls) - this is the FlowSpace pattern
- Skips unchanged content using hash-based detection to minimize API calls
- Coordinates rate limit backoff globally across batches
- Reports progress via callback for pipeline integration
- Follows stateless design (CD10): all batch state local to method, no instance mutation

### Batching Architecture (Critical Distinction)

**WRONG approach** (what SmartContentService does for LLMs):
```
50 Workers → 50 parallel API calls (1 prompt each) → 50 responses
```

**CORRECT approach** (what FlowSpace uses for embeddings):
```
Collect items → Split into batches (16 items each) → 1 API call per batch
Batch 1: [text1..text16] → 1 API call → [emb1..emb16]
Batch 2: [text17..text32] → 1 API call → [emb17..emb32]
```

The embedding API natively supports batch input - sending multiple texts in ONE HTTP request is much more efficient than parallel individual calls.

### User Value

Users running `fs2 scan` get embeddings generated for their code without manual intervention. The service handles:
- **Incremental updates**: Only changed files get re-embedded (cost savings)
- **Resilience**: Rate limits don't crash the scan—service pauses and resumes
- **Efficiency**: API-level batching maximizes throughput with minimal requests
- **Cost optimization**: Fewer API calls = lower costs

### Example

**Input**: 100 CodeNodes (80 unchanged, 20 new/modified)

**Processing** (with batch_size=16):
```python
# Service collects 20 items needing embedding
# Splits into 2 batches: [16 items] + [4 items]
# Makes 2 API calls total (not 20!)

result = await embedding_service.process_batch(nodes)
# result = {
#     "processed": 20,     # New embeddings generated
#     "skipped": 80,       # Hash-based skip
#     "errors": 0,
#     "batches_processed": 2,  # Only 2 API calls
#     "results": {node_id: updated_node for all nodes}
# }
```

**Output**: All nodes updated with `embedding` and `smart_content_embedding` fields (tuple-of-tuples for chunk-level storage).

---

## Objectives & Scope

### Objective

Implement `EmbeddingService` with **API-level batch processing** (FlowSpace pattern), content-type aware chunking, hash-based skip logic, and rate limit coordination as specified in plan § Phase 3.

### Goals

- ✅ Implement content-type aware chunking logic (`_chunk_content()`)
- ✅ Implement hash-based skip logic (`_should_skip()`) for incremental updates
- ✅ Implement batch collection and splitting (`_collect_batches()`)
- ✅ Implement `process_batch()` with **API-level batching** (one `embed_batch()` call per batch)
- ✅ Implement rate limit coordination across batches
- ✅ Support optional concurrent batch processing (`max_concurrent_batches`)
- ✅ Support progress reporting callback for pipeline integration
- ✅ Handle tiktoken fallback for unknown models with warning log
- ✅ All implementations follow TDD: tests first, then implementation

### Non-Goals

- ❌ Pipeline integration (Phase 4) – Service is standalone, pipeline adds EmbeddingStage
- ❌ CLI flags (Phase 4) – `--no-embeddings` flag added in Phase 4
- ❌ Graph config node with embedding metadata (Phase 4) – Stored in EmbeddingStage
- ❌ Integration tests with full pipeline (Phase 5) – This phase creates unit tests only
- ❌ Documentation (Phase 6) – User-facing docs created after testing validation
- ❌ Parallel individual API calls – Use batch API, not parallel single calls
- ❌ Complex retry orchestration – Adapter handles per-request retries; service handles batch-level coordination

---

## Architecture Map

### Component Diagram

<!-- Status: grey=pending, orange=in-progress, green=completed, red=blocked -->
<!-- Updated by plan-6 during implementation -->

```mermaid
flowchart TD
    classDef pending fill:#9E9E9E,stroke:#757575,color:#fff
    classDef inprogress fill:#FF9800,stroke:#F57C00,color:#fff
    classDef completed fill:#4CAF50,stroke:#388E3C,color:#fff
    classDef blocked fill:#F44336,stroke:#D32F2F,color:#fff

    subgraph Phase3["Phase 3: Embedding Service"]
        T001["T001: Write chunking tests ✓"]:::completed
        T002["T002: Implement _chunk_content ✓"]:::completed
        T003["T003: Write skip logic tests ✓"]:::completed
        T004["T004: Implement _should_skip ✓"]:::completed
        T005["T005: Write batch collection tests ✓"]:::completed
        T006["T006: Implement _collect_batches ✓"]:::completed
        T007["T007: Write process_batch tests ✓"]:::completed
        T008["T008: Implement process_batch ✓"]:::completed
        T009["T009: Write rate limit tests ✓"]:::completed
        T010["T010: Implement rate limit coord ✓"]:::completed
        T011["T011: Write tiktoken fallback test ✓"]:::completed
        T012["T012: Create ContentType enum"]:::completed
        T013["T013: Update CodeNode & Parser"]:::completed

        T001 --> T002
        T012 --> T013
        T013 --> T008
        T003 --> T004
        T005 --> T006
        T002 --> T007
        T004 --> T007
        T006 --> T007
        T007 --> T008
        T009 --> T010
        T008 --> T010
        T011 -.-> T002
    end

    subgraph Dependencies["Dependencies (from Phase 1 & 2)"]
        EmbeddingConfig["EmbeddingConfig<br/>(batch_size, max_concurrent_batches)"]:::completed
        ChunkConfig["ChunkConfig"]:::completed
        EmbeddingAdapter["EmbeddingAdapter ABC<br/>(embed_batch)"]:::completed
        TokenCounter["TokenCounterAdapter"]:::completed
        Exceptions["Exception Hierarchy"]:::completed
        CodeNode["CodeNode (dual fields + content_type)"]:::completed
        ContentType["ContentType enum<br/>(CODE/CONTENT)"]:::completed
    end

    subgraph Files["Files to Create"]
        SVC["/src/fs2/core/services/embedding/embedding_service.py ✓"]:::completed
        CHUNK["ChunkItem dataclass ✓<br/>(node_id, chunk_index, text,<br/>is_smart_content)"]:::completed
        TST1["/tests/unit/services/test_embedding_chunking.py ✓"]:::completed
        TST2["/tests/unit/services/test_embedding_skip.py ✓"]:::completed
        TST3["/tests/unit/services/test_embedding_batch_collection.py ✓"]:::completed
        TST4["/tests/unit/services/test_embedding_service.py ✓"]:::completed
        TST5["/tests/unit/services/test_embedding_rate_limit.py ✓"]:::completed
        TST6["/tests/unit/services/test_token_counter_fallback.py ✓"]:::completed
    end

    T001 -.-> TST1
    T002 -.-> SVC
    T003 -.-> TST2
    T005 -.-> TST3
    T007 -.-> TST4
    T009 -.-> TST5
    T011 -.-> TST6

    EmbeddingConfig --> T006
    EmbeddingConfig --> T008
    ChunkConfig --> T002
    TokenCounter --> T002
    EmbeddingAdapter --> T008
    Exceptions --> T010
    CodeNode --> T008
    ContentType --> T008
    CHUNK --> T005
    CHUNK --> T006
    CHUNK --> T007
    CHUNK --> T008
```

### Batching Flow Diagram

```mermaid
flowchart LR
    subgraph Input["Input"]
        Nodes["List[CodeNode]<br/>some with embeddings,<br/>some without"]
    end

    subgraph Service["EmbeddingService.process_batch()"]
        direction TB
        Skip["_should_skip()<br/>Check embedding exists"]
        Chunk["_chunk_content()<br/>Split by content type<br/>→ List[ChunkItem]"]
        Collect["_collect_batches()<br/>Group ChunkItems<br/>by batch_size"]
        Process["Process each batch<br/>sequentially or concurrent"]
        Reassemble["Reassemble embeddings<br/>by ChunkItem.node_id"]
    end

    subgraph Adapter["EmbeddingAdapter.embed_batch()"]
        API["ONE API Call<br/>input=[item.text for item]<br/>→ [emb1..embN]"]
    end

    subgraph Output["Output"]
        Result["Dict:<br/>processed, skipped,<br/>batches_processed"]
        UpdatedNodes["Updated CodeNodes<br/>via replace()"]
    end

    Nodes --> Skip
    Skip -->|"skip=True"| Result
    Skip -->|"skip=False"| Chunk
    Chunk --> Collect
    Collect --> Process
    Process -->|"batch of ChunkItems"| API
    API -->|"batch of embeddings"| Process
    Process --> Reassemble
    Reassemble --> Result
    Result --> UpdatedNodes
```

### Task-to-Component Mapping

<!-- Status: ⬜ Pending | 🟧 In Progress | ✅ Complete | 🔴 Blocked -->

| Task | Component(s) | Files | Status | Comment |
|------|-------------|-------|--------|---------|
| T001 | Chunking Tests | `/workspaces/flow_squared/tests/unit/services/test_embedding_chunking.py` | ✅ Complete | TDD RED: 17 tests for content-type chunking |
| T002 | Chunking Logic | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | ✅ Complete | TDD GREEN: `_chunk_content()` + ChunkItem (17 tests pass) |
| T003 | Skip Logic Tests | `/workspaces/flow_squared/tests/unit/services/test_embedding_skip.py` | ✅ Complete | TDD RED: 8 tests for hash-based skip |
| T004 | Skip Logic | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | ✅ Complete | TDD GREEN: `_should_skip()` (8 tests pass) |
| T005 | Batch Collection Tests | `/workspaces/flow_squared/tests/unit/services/test_embedding_batch_collection.py` | ✅ Complete | TDD RED: 11 tests for batch splitting |
| T006 | Batch Collection | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | ✅ Complete | TDD GREEN: `_collect_batches()` (11 tests pass) |
| T007 | Batch Processing Tests | `/workspaces/flow_squared/tests/unit/services/test_embedding_service.py` | ✅ Complete | TDD RED: 11 tests for process_batch() |
| T008 | Batch Processing | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | ✅ Complete | TDD GREEN: process_batch() (47 total tests pass) |
| T009 | Rate Limit Tests | `/workspaces/flow_squared/tests/unit/services/test_embedding_rate_limit.py` | ✅ Complete | TDD: 6 tests for rate limit handling |
| T010 | Rate Limit Coordination | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | ✅ Complete | Error handling + continuation in process_batch |
| T011 | Tiktoken Fallback Test | `/workspaces/flow_squared/tests/unit/services/test_token_counter_fallback.py` | ✅ Complete | 5 tests for o200k_base fallback |
| T012 | ContentType Enum | `/workspaces/flow_squared/src/fs2/core/models/content_type.py`, `/workspaces/flow_squared/tests/unit/models/test_content_type.py` | ✅ Complete | CODE/CONTENT enum with 16 unit tests. **Why**: EmbeddingService needs explicit type for chunking strategy (code=400, docs=800 tokens). |
| T013 | CodeNode + Parser Updates | `/workspaces/flow_squared/src/fs2/core/models/code_node.py`, `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | ✅ Complete | Add content_type field, set at scan time. **Why**: Single source of truth - set once at scan, query anywhere without re-checking language. |

---

## Tasks

| Status | ID | Task | CS | Type | Dependencies | Absolute Path(s) | Validation | Subtasks | Notes |
|--------|------|------|-----|------|--------------|------------------|------------|----------|-------|
| [x] | T001 | Write tests for content chunking (code vs docs vs smart_content, overlap, token boundaries, **dual embedding**) | 3 | Test | – | `/workspaces/flow_squared/tests/unit/services/test_embedding_chunking.py` | Tests fail with ModuleNotFoundError, cover all content types, **test both raw + smart_content chunking** | – | Per Plan 3.1, Per Finding 04, **DYK-2** |
| [x] | T002 | Implement `_chunk_content()` with content-type aware parameters, **returns ChunkItems for both content AND smart_content** | 3 | Core | T001 | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | All T001 tests pass, uses `TokenCounterAdapter`, **produces ChunkItems with is_smart_content flag** | – | Per Plan 3.2, **DYK-5: inline conditional** `if is_smart_content → config.smart_content; elif CODE → config.code; else → config.documentation`, **DYK-2** |
| [x] | T003 | Write tests for hash-based skip logic (skip unchanged, process changed, edge cases) | 2 | Test | – | `/workspaces/flow_squared/tests/unit/services/test_embedding_skip.py` | Tests fail with ModuleNotFoundError | – | Per Plan 3.3, Per Finding 08 |
| [x] | T004 | Implement `_should_skip()` for unchanged content detection | 2 | Core | T003 | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | All T003 tests pass, returns bool based on embedding existence | – | Per Plan 3.4 |
| [x] | T005 | Write tests for batch collection (`_collect_batches()` using config.batch_size, **ChunkItem tracking**) | 2 | Test | – | `/workspaces/flow_squared/tests/unit/services/test_embedding_batch_collection.py` | Tests cover: 100 ChunkItems with batch_size=16 → 7 batches, metadata preserved | – | FlowSpace pattern, **DYK-1: ChunkItem for reassembly** |
| [x] | T006 | Implement `_collect_batches()` to split **ChunkItems** into fixed-size batches | 2 | Core | T005 | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | All T005 tests pass, uses `config.batch_size`, **returns List[List[ChunkItem]]** | – | Per FlowSpace pattern, **DYK-1** |
| [x] | T007 | Write tests for `process_batch()` (**API-level batching**, progress callback, stats, stateless CD10, **ChunkItem reassembly**) | 3 | Test | T001, T003, T005 | `/workspaces/flow_squared/tests/unit/services/test_embedding_service.py` | Tests verify adapter.embed_batch() called once per batch, **embeddings correctly mapped back to nodes** | – | Per Finding 02, **DYK-1** |
| [x] | T008 | Implement `process_batch()` calling `adapter.embed_batch()` per batch, **reassemble via ChunkItem into both embedding AND smart_content_embedding, convert list→tuple** | 3 | Core | T002, T004, T006, T007 | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | All T007 tests pass, **all batch state local to method (no instance mutation)**, **dual embedding fields populated via is_smart_content flag**, **tuple conversion: `tuple(tuple(e) for e in embeddings)`** | – | Per Finding 01 (use replace()), **DYK-1, DYK-2, DYK-4** |
| [x] | T009 | Write tests for rate limit handling (**both sequential AND concurrent modes**) | 3 | Test | – | `/workspaces/flow_squared/tests/unit/services/test_embedding_rate_limit.py` | Tests: sequential backoff, **concurrent asyncio.Event coordination**, no batch interference | – | Per Finding 03, **DYK-3: full concurrency** |
| [x] | T010 | Implement rate limit coordination with **asyncio.Event for concurrent batches** | 3 | Core | T008, T009 | `/workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py` | All T009 tests pass, respects retry_after, **all concurrent batches pause on rate limit** | – | max backoff 60s, **DYK-3** |
| [x] | T011 | Write test for tiktoken model fallback with warning log | 2 | Test | – | `/workspaces/flow_squared/tests/unit/services/test_token_counter_fallback.py` | Unknown model logs warning, uses o200k_base fallback | – | Per Finding 11 |
| [x] | T012 | Create ContentType enum (CODE/CONTENT) with unit tests | 2 | Core+Test | – | `/workspaces/flow_squared/src/fs2/core/models/content_type.py`, `/workspaces/flow_squared/tests/unit/models/test_content_type.py` | 16 tests pass: enum values, defaults, parser integration | – | **Why**: Embedding service needs explicit content classification to apply different chunking strategies (code=400 tokens, docs=800 tokens). Previously implicit via `language in CODE_LANGUAGES` check. |
| [x] | T013 | Update CodeNode + TreeSitterParser to set content_type at scan time | 2 | Core | T012 | `/workspaces/flow_squared/src/fs2/core/models/code_node.py`, `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | 73 CodeNode/parser tests pass, content_type field present | – | **Why**: EmbeddingService.process_batch() needs to know content type without re-checking language. Set once at scan time, query anywhere. |

---

## Alignment Brief

### Prior Phases Review

#### Phase 1: Core Infrastructure (Completed 2025-12-20)

**A. Deliverables Created**

| File | Component | Lines |
|------|-----------|-------|
| `/workspaces/flow_squared/src/fs2/config/objects.py` | `ChunkConfig`, `EmbeddingConfig`, `AzureEmbeddingConfig` | 179 |
| `/workspaces/flow_squared/src/fs2/core/adapters/exceptions.py` | `EmbeddingAdapterError`, `EmbeddingRateLimitError`, `EmbeddingAuthenticationError` | 79 |
| `/workspaces/flow_squared/src/fs2/core/models/code_node.py` | Dual embedding fields (`embedding`, `smart_content_embedding`) | Updated |
| `/workspaces/flow_squared/tests/unit/config/test_embedding_config.py` | 35 tests | 726 |
| `/workspaces/flow_squared/tests/unit/adapters/test_embedding_exceptions.py` | 11 tests | 223 |
| `/workspaces/flow_squared/tests/unit/models/test_code_node_embedding.py` | 15 tests | 454 |

**B. Key Lessons Learned**

1. **TDD Methodology Worked**: RED → GREEN → REFACTOR strictly followed
2. **Pattern Following Reduced Time**: SmartContentConfig → ChunkConfig pattern reuse

**C. Dependencies Exported to Phase 3**

```python
# Configuration API (UPDATED)
from fs2.config.objects import EmbeddingConfig, ChunkConfig
config = config_service.require(EmbeddingConfig)
# config.batch_size (16) - texts per API call
# config.max_concurrent_batches (1) - concurrent batch processing
# config.code.max_tokens (400), config.documentation.max_tokens (800), etc.

# Exception API
from fs2.core.adapters.exceptions import EmbeddingRateLimitError
# EmbeddingRateLimitError(message, retry_after: float | None, attempts_made: int)

# CodeNode Storage Pattern
from dataclasses import replace
updated_node = replace(node, embedding=((0.1, 0.2, ...), ...), smart_content_embedding=...)
```

---

#### Phase 2: Embedding Adapters (Completed 2025-12-21)

**A. Deliverables Created**

| File | Component | Lines |
|------|-----------|-------|
| `/workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter.py` | `EmbeddingAdapter` ABC | ~100 |
| `/workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_azure.py` | `AzureEmbeddingAdapter` | ~200 |
| `/workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_openai.py` | `OpenAICompatibleEmbeddingAdapter` | ~150 |
| `/workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_fake.py` | `FakeEmbeddingAdapter` with fixture support | ~200 |
| `/workspaces/flow_squared/tests/fixtures/fixture_graph.pkl` | 397 nodes, real embeddings | 3.9 MB |

**B. Critical API Design for Phase 3**

The adapters are **already correctly designed** for API-level batching:

```python
class EmbeddingAdapter(ABC):
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts in a SINGLE API call.

        Per DYK-3: This method makes a single API call with all texts.
        The service layer (Phase 3) handles batch sizing/chunking.
        """

# Azure implementation (line 155-159):
response = await client.embeddings.create(
    model=self._azure_config.deployment_name,
    input=texts,  # <-- ALL texts in ONE call
    dimensions=self._embedding_config.dimensions,
)
```

**C. Dependencies Exported to Phase 3**

```python
# EmbeddingAdapter ABC Contract
class EmbeddingAdapter(ABC):
    async def embed_text(self, text: str) -> list[float]:
        """Single text → single embedding"""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Multiple texts → ONE API call → multiple embeddings"""

# Service should call embed_batch() per batch, NOT embed_text() per item!
# This is the FlowSpace pattern for efficiency.
```

---

#### Cross-Phase Synthesis

**Cumulative Deliverables Available to Phase 3:**

| Category | Files/Components | Origin Phase |
|----------|------------------|--------------|
| Configuration | `EmbeddingConfig` (batch_size, max_concurrent_batches) | Phase 1 (updated) |
| Exceptions | `EmbeddingRateLimitError` with retry metadata | Phase 1 |
| Models | `CodeNode` with dual embedding fields | Phase 1 |
| Adapters | `EmbeddingAdapter.embed_batch()` - ONE API call per batch | Phase 2 |
| Test Infrastructure | 75 tests, `fixture_graph` pytest fixture | Phase 1 + 2 |

**Key Architecture Insight:**

The adapter layer already supports the correct batching pattern. Phase 3 service must:
1. Collect items needing embedding
2. Split into batches of `config.batch_size` (default: 16)
3. For each batch, call `adapter.embed_batch(texts)` - **ONE** API call
4. Optionally process batches concurrently (`max_concurrent_batches`)

---

### Critical Findings Affecting This Phase

| Finding | Title | Constraint/Requirement | Addressed By |
|---------|-------|------------------------|--------------|
| 01 | Frozen CodeNode Extension Pattern | Use `dataclasses.replace()` for all updates | T008: `process_batch()` returns updated nodes via replace() |
| 02 | Proven Async Batch Processing Pattern | All batch state LOCAL to method (no instance mutation) | T007, T008: Stateless design tests and implementation |
| 03 | Rate Limit Handling with Global Backoff | Coordinate backoff across batches | T009, T010: Rate limit coordination |
| 08 | Hash-Based Skip Logic | Compare `content_hash` before embedding | T003, T004: Skip logic tests and implementation |
| 11 | Token Counter Fallback Handling | Log warning, use cl100k_base for unknown models | T011: Tiktoken fallback test |

**NEW Critical Insight: API-Level Batching**

| Finding | Title | Constraint/Requirement | Addressed By |
|---------|-------|------------------------|--------------|
| NEW | FlowSpace Batching Pattern | Use `embed_batch()` per batch, NOT parallel `embed_text()` calls | T005, T006, T007, T008: Batch collection and processing |

**NEW Critical Insight: Explicit Content Classification**

| Finding | Title | Constraint/Requirement | Addressed By |
|---------|-------|------------------------|--------------|
| NEW | ContentType Enum | Explicit CODE/CONTENT classification at scan time for embedding strategy | T012, T013: ContentType enum and CodeNode integration |

**NEW Critical Insight: Chunk-to-Node Reassembly (DYK-1)**

| Finding | Title | Constraint/Requirement | Addressed By |
|---------|-------|------------------------|--------------|
| DYK-1 | ChunkItem Data Structure | Track `(node_id, chunk_index, text)` through batching pipeline for embedding reassembly | T005, T006, T007, T008: ChunkItem tracking and reassembly |

**Rationale for ChunkItem**:

When processing large nodes, content is chunked into multiple texts. These chunks are then batched for API calls. After `embed_batch()` returns embeddings, we need to:
1. Know which embeddings belong to which original node
2. Know the chunk order to reconstruct `tuple[tuple[float, ...], ...]`
3. Know whether chunk is raw content or smart_content (for dual embedding)

The ChunkItem dataclass provides explicit tracking:
```python
@dataclass(frozen=True)
class ChunkItem:
    node_id: str              # Original CodeNode.node_id
    chunk_index: int          # Position in chunk sequence (0, 1, 2, ...)
    text: str                 # Chunk content to embed
    is_smart_content: bool = False  # True for smart_content chunks (DYK-2)
```

**NEW Critical Insight: Dual Embedding Unified Batching (DYK-2)**

| Finding | Title | Constraint/Requirement | Addressed By |
|---------|-------|------------------------|--------------|
| DYK-2 | Unified Smart Content Batching | Embed both `content` and `smart_content` in single pass via ChunkItem.is_smart_content flag | T002, T005, T006, T007, T008 |

**Rationale for Unified Batching**:

Per spec AC1, each node needs BOTH `embedding` (raw content) AND `smart_content_embedding` populated. Rather than two separate passes:
- Chunk raw content → ChunkItem(is_smart_content=False)
- Chunk smart_content → ChunkItem(is_smart_content=True)
- Batch all ChunkItems together
- Reassembly separates by `is_smart_content` flag into respective fields

Benefits:
1. Single API call round handles both embedding types
2. Consistent control flow, less duplication
3. Smart content typically fits in one chunk (8000 token limit)

**NEW Critical Insight: Full Concurrent Batch Processing (DYK-3)**

| Finding | Title | Constraint/Requirement | Addressed By |
|---------|-------|------------------------|--------------|
| DYK-3 | Concurrent Rate Limit Coordination | Implement asyncio.Event pattern for max_concurrent_batches > 1 | T009, T010: Full concurrency tests and implementation |

**Rationale for Full Concurrency**:

The `max_concurrent_batches` config exists (default: 1). Rather than defer concurrent support:
- Implement asyncio.Event coordination pattern from Finding 03
- When any batch hits rate limit, set event → all concurrent batches pause
- After backoff, clear event → all batches resume
- Tests cover both sequential (=1) and concurrent (>1) modes

This ensures:
1. Power users get performance benefits immediately
2. No hidden tech debt or "TODO: implement concurrency"
3. T009/T010 are complete with full test coverage

**NEW Critical Insight: Type Conversion in Service (DYK-4)**

| Finding | Title | Constraint/Requirement | Addressed By |
|---------|-------|------------------------|--------------|
| DYK-4 | list→tuple Conversion | Convert `list[list[float]]` from adapter to `tuple[tuple[float, ...], ...]` for CodeNode in service layer | T008: Inline conversion during reassembly |

**Rationale for Service-Layer Conversion**:

API returns `list[list[float]]`, but CodeNode stores `tuple[tuple[float, ...], ...]`:
- Tuples are immutable (frozen dataclass requirement)
- Tuples are hashable (enables set/dict operations)
- Single conversion point in T008: `tuple(tuple(e) for e in embeddings)`

Adapters stay generic, service owns the storage contract.

**NEW Critical Insight: ContentType → ChunkConfig Mapping (DYK-5)**

| Finding | Title | Constraint/Requirement | Addressed By |
|---------|-------|------------------------|--------------|
| DYK-5 | Inline Config Selection | Map ContentType to ChunkConfig via simple if/elif/else in `_chunk_content()` | T002: Inline conditional |

**Rationale for Inline Conditional**:

ContentType has only 2 values (CODE/CONTENT), plus smart_content as a flag. Extracting a mapping method would be over-engineering:

```python
def _chunk_content(self, node: CodeNode, is_smart_content: bool = False) -> list[ChunkItem]:
    if is_smart_content:
        chunk_config = self._config.smart_content      # 8000 tokens, 0 overlap
    elif node.content_type == ContentType.CODE:
        chunk_config = self._config.code               # 400 tokens, 50 overlap
    else:  # ContentType.CONTENT
        chunk_config = self._config.documentation      # 800 tokens, 120 overlap
```

KISS principle: simple conditional at point of use, not abstracted.

**Rationale for ContentType**:

The EmbeddingService uses different chunking strategies based on content type:
- **CODE** (Python, JS, etc.): 400 tokens per chunk (smaller for precision)
- **CONTENT** (Markdown, YAML, etc.): 800 tokens per chunk (larger for context)

Previously, this required checking `language in CODE_LANGUAGES` at embedding time. With explicit `content_type` on CodeNode:
1. Classification happens once at scan time (single source of truth)
2. EmbeddingService can query `node.content_type` directly
3. Future services can use the same classification without duplicating logic
4. Enables content-type-aware embedding strategies without language coupling

---

### Invariants & Guardrails

| Type | Constraint | Enforcement |
|------|------------|-------------|
| Memory | 1024 dimensions per embedding (not 3072) | `config.dimensions` default |
| Batch Size | 1-2048 texts per API call | `config.batch_size` validation |
| Concurrency | 1+ concurrent batches (default: 1) | `config.max_concurrent_batches` |
| Rate Limit | Max backoff 60 seconds | `config.max_delay` |
| Security | `list[float]` only, no numpy | Type annotations + tests |
| Stateless | No instance mutation in `process_batch()` | Test: concurrent batches don't interfere |

---

### Inputs to Read

| File | Purpose |
|------|---------|
| `/workspaces/flow_squared/src/fs2/core/services/smart_content_service.py` | Pattern reference for stateless batch processing |
| `/workspaces/flow_squared/src/fs2/core/adapters/token_counter_adapter_tiktoken.py` | TokenCounterAdapter implementation |
| `/workspaces/flow_squared/src/fs2/config/objects.py` | EmbeddingConfig with batch_size, max_concurrent_batches |
| `/workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter.py` | EmbeddingAdapter ABC - note `embed_batch()` semantics |
| `/workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_azure.py` | Reference implementation - ONE API call per batch |

---

### Visual Alignment Aids

#### System State Flow Diagram

```mermaid
flowchart LR
    subgraph Input["Input"]
        Nodes["List[CodeNode]<br/>100 nodes"]
    end

    subgraph Service["EmbeddingService.process_batch()"]
        direction TB
        Skip["_should_skip()<br/>80 skipped"]
        Chunk["_chunk_content()<br/>per node content type"]
        Collect["_collect_batches()<br/>20 items → 2 batches"]
        Process["Process batches<br/>sequentially"]
    end

    subgraph Adapter["adapter.embed_batch()"]
        Batch1["Batch 1: 16 texts<br/>→ 1 API call<br/>→ 16 embeddings"]
        Batch2["Batch 2: 4 texts<br/>→ 1 API call<br/>→ 4 embeddings"]
    end

    subgraph Output["Output"]
        Result["processed: 20<br/>skipped: 80<br/>batches: 2"]
    end

    Nodes --> Skip
    Skip --> Chunk
    Chunk --> Collect
    Collect --> Process
    Process --> Batch1
    Batch1 --> Batch2
    Batch2 --> Result
```

#### Sequence Diagram: Process Batch Flow (Corrected)

```mermaid
sequenceDiagram
    participant Pipeline
    participant Service as EmbeddingService
    participant Skip as _should_skip()
    participant Chunk as _chunk_content()
    participant Collect as _collect_batches()
    participant Adapter as EmbeddingAdapter

    Pipeline->>Service: process_batch(nodes)

    Note over Service: Phase 1: Filter & Chunk
    loop For each node
        Service->>Skip: _should_skip(node)
        alt Has embedding & unchanged
            Skip-->>Service: True (skip)
        else Needs embedding
            Skip-->>Service: False (process)
            Service->>Chunk: _chunk_content(node.content)
            Chunk-->>Service: chunked texts
        end
    end

    Note over Service: Phase 2: Collect into batches
    Service->>Collect: _collect_batches(all_texts, batch_size=16)
    Collect-->>Service: List[Batch] (e.g., 2 batches)

    Note over Service: Phase 3: Process each batch
    loop For each batch
        Service->>Adapter: embed_batch(batch.texts)
        Note over Adapter: ONE API call with<br/>all texts in batch
        Adapter-->>Service: List[List[float]] embeddings
        Service->>Service: update nodes via replace()
    end

    Service-->>Pipeline: {processed, skipped, batches_processed, results}
```

---

### Test Plan (Full TDD)

**Testing Approach**: Full TDD per plan specification.

**Mock Usage**: Targeted mocks for adapter calls only; real implementations for internal logic.

| Test File | Test Class | Purpose | Fixtures | Key Assertions |
|-----------|------------|---------|----------|----------------|
| `test_embedding_chunking.py` | `TestContentChunking` | Validates content-type specific chunk sizes | `EmbeddingConfig` with custom `ChunkConfig` | code=400 tokens, docs=800 tokens, overlap respected |
| `test_embedding_skip.py` | `TestHashBasedSkip` | Validates unchanged content skipped | `CodeNode` with/without embeddings | Returns True for unchanged, False for new |
| `test_embedding_batch_collection.py` | `TestBatchCollection` | Validates items split into fixed batches | List of texts, batch_size=16 | 100 items → 7 batches (6×16 + 1×4) |
| `test_embedding_service.py` | `TestProcessBatch` | Validates API-level batching | `fake_embedding_adapter` | `embed_batch()` called once per batch, NOT per item |
| `test_embedding_service.py` | `TestProcessBatchStateless` | Validates CD10 stateless design | Two concurrent batches | No interference, independent stats |
| `test_embedding_rate_limit.py` | `TestRateLimitCoordination` | Validates rate limit handling | Mock adapter with `EmbeddingRateLimitError` | Pause, respect retry_after, resume |
| `test_token_counter_fallback.py` | `TestTokenCounterFallback` | Validates cl100k_base fallback | Unknown model name | Warning logged, fallback used |

**Critical Test: API-Level Batching Verification**

```python
# test_embedding_service.py
class TestAPILevelBatching:
    """
    Purpose: Validates service uses embed_batch() per batch, NOT embed_text() per item.
    Quality Contribution: Ensures efficient API usage (FlowSpace pattern).
    Acceptance Criteria: With 20 items and batch_size=16, exactly 2 embed_batch() calls.
    """

    async def test_process_batch_calls_embed_batch_per_batch_not_per_item(
        self, embedding_service, fake_embedding_adapter
    ):
        """20 items with batch_size=16 → exactly 2 embed_batch() calls."""
        nodes = [create_code_node(f"content_{i}") for i in range(20)]

        await embedding_service.process_batch(nodes)

        # Verify embed_batch was called exactly twice (not 20 times)
        batch_calls = [c for c in fake_embedding_adapter.call_history if "texts" in c]
        assert len(batch_calls) == 2

        # First batch has 16 items, second has 4
        assert len(batch_calls[0]["texts"]) == 16
        assert len(batch_calls[1]["texts"]) == 4
```

---

### Step-by-Step Implementation Outline

| Step | Task | Action | Validation |
|------|------|--------|------------|
| 1 | T001 | Write chunking tests (code, docs, smart_content, overlap) | Tests fail with `ModuleNotFoundError` |
| 2 | T002 | Implement `_chunk_content()` using `TokenCounterAdapter` | T001 tests pass |
| 3 | T003 | Write skip logic tests (skip unchanged, process new) | Tests fail with `ModuleNotFoundError` |
| 4 | T004 | Implement `_should_skip()` checking `node.embedding` | T003 tests pass |
| 5 | T005 | Write batch collection tests (split into fixed batches) | Tests fail with `ModuleNotFoundError` |
| 6 | T006 | Implement `_collect_batches()` using `config.batch_size` | T005 tests pass |
| 7 | T007 | Write process_batch tests (API-level batching, stats, stateless) | Tests fail with `ModuleNotFoundError` |
| 8 | T008 | Implement `process_batch()` calling `embed_batch()` per batch | T007 tests pass |
| 9 | T009 | Write rate limit tests (batch-level handling) | Tests fail with `ModuleNotFoundError` |
| 10 | T010 | Integrate rate limit handling across batches | T009 tests pass, T007 tests still pass |
| 11 | T011 | Write tiktoken fallback test | Test fails, then passes with implementation |

---

### Commands to Run

```bash
# Environment setup
cd /workspaces/flow_squared
uv sync

# Run Phase 3 tests (as they're created)
uv run pytest tests/unit/services/test_embedding_chunking.py -v
uv run pytest tests/unit/services/test_embedding_skip.py -v
uv run pytest tests/unit/services/test_embedding_batch_collection.py -v
uv run pytest tests/unit/services/test_embedding_service.py -v
uv run pytest tests/unit/services/test_embedding_rate_limit.py -v
uv run pytest tests/unit/services/test_token_counter_fallback.py -v

# Run all Phase 3 tests
uv run pytest tests/unit/services/test_embedding*.py -v

# Linting and type checks
uv run ruff check src/fs2/core/services/embedding/
uv run mypy src/fs2/core/services/embedding/

# Verify Phase 1 + 2 regression
uv run pytest tests/unit/config/test_embedding_config.py tests/unit/adapters/test_embedding_exceptions.py tests/unit/models/test_code_node_embedding.py tests/unit/adapters/test_embedding_adapter*.py -v
```

---

### Risks/Unknowns

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Batch size too large for API | Medium | Low | Validate batch_size <= 2048 in config |
| Rate limit handling complexity | Medium | Medium | Simple pause-and-resume per batch |
| Memory pressure with large batches | Low | Low | batch_size=16 default is conservative |
| Token boundaries for chunking | Medium | Low | Comprehensive chunking tests with real content |

---

### Ready Check

- [x] Prior phases reviewed (Phase 1 + Phase 2 synthesis complete)
- [x] Critical findings mapped to tasks (Findings 01, 02, 03, 08, 11 + NEW batching insight)
- [x] ADR constraints mapped to tasks - N/A (no ADRs exist)
- [x] Test plan defined with named tests
- [x] Commands documented for validation
- [x] **Batching architecture corrected** - API-level batching per FlowSpace pattern
- [ ] **Awaiting explicit GO/NO-GO from human sponsor**

---

## Phase Footnote Stubs

_Populated during implementation by plan-6. Footnotes link specific code changes to tasks._

| Tag | File | Description |
|-----|------|-------------|
| T012 | `/workspaces/flow_squared/src/fs2/core/models/content_type.py` | Created ContentType enum (CODE/CONTENT) |
| T012 | `/workspaces/flow_squared/tests/unit/models/test_content_type.py` | 16 unit tests for ContentType enum, defaults, parser integration |
| T013 | `/workspaces/flow_squared/src/fs2/core/models/code_node.py` | Added content_type field with default |
| T013 | `/workspaces/flow_squared/src/fs2/core/adapters/ast_parser_impl.py` | Set content_type at scan time, added EXTRACTABLE_LANGUAGES |
| T013 | `/workspaces/flow_squared/src/fs2/core/repos/graph_store_impl.py` | Added content_type module to ALLOWED_MODULES for pickle |

---

## Evidence Artifacts

**Execution Log**: `./execution.log.md` (created by plan-6 during implementation)

**Test Evidence**:

*Completed (T012, T013):*
- `uv run pytest tests/unit/models/test_content_type.py -v` → **16 passed**

*Pending (T001-T011):*
- `uv run pytest tests/unit/services/test_embedding_chunking.py -v`
- `uv run pytest tests/unit/services/test_embedding_skip.py -v`
- `uv run pytest tests/unit/services/test_embedding_batch_collection.py -v`
- `uv run pytest tests/unit/services/test_embedding_service.py -v`
- `uv run pytest tests/unit/services/test_embedding_rate_limit.py -v`
- `uv run pytest tests/unit/services/test_token_counter_fallback.py -v`

---

## Discoveries & Learnings

_Populated during implementation by plan-6. Log anything of interest to your future self._

| Date | Task | Type | Discovery | Resolution | References |
|------|------|------|-----------|------------|------------|
| 2025-12-21 | Pre-phase | insight | API-level batching is more efficient than parallel workers | Updated dossier with FlowSpace pattern | FlowSpace generator.py |
| 2025-12-21 | Pre-phase | decision | Changed max_workers to batch_size in EmbeddingConfig | Renamed field, updated tests | objects.py, test_embedding_config.py |
| 2025-12-21 | T012 | decision | Need explicit content type for embedding strategy (code=400 tokens, docs=800 tokens chunking) | Created ContentType enum (CODE/CONTENT) with 16 unit tests | content_type.py, test_content_type.py |
| 2025-12-21 | T013 | insight | Extraction and content_type are separate concerns - markdown needs sections extracted but is still CONTENT | Created EXTRACTABLE_LANGUAGES = CODE_LANGUAGES ∪ {markdown, rst, hcl, dockerfile} | ast_parser_impl.py |
| 2025-12-21 | T013 | decision | Made content_type optional with default for backwards compat (93 existing test usages) | Default ContentType.CODE in dataclass field | code_node.py |
| 2025-12-21 | T012 | gotcha | Pickle security: ContentType module needed in ALLOWED_MODULES for graph serialization | Added fs2.core.models.content_type to whitelist | graph_store_impl.py |
| 2025-12-22 | T005-T008 | decision | Chunk-to-node reassembly requires explicit tracking through batching pipeline (DYK-1) | Create ChunkItem(node_id, chunk_index, text) dataclass for explicit tracking | /didyouknow session |
| 2025-12-22 | T001-T008 | decision | Dual embedding (raw + smart_content) should use unified batching, not two passes (DYK-2) | Add is_smart_content flag to ChunkItem; reassembly populates both embedding fields | /didyouknow session |
| 2025-12-22 | T009-T010 | decision | Implement full concurrent batch processing now, not deferred (DYK-3) | asyncio.Event coordination pattern; T009/T010 CS increased from 2→3 | /didyouknow session |
| 2025-12-22 | T008 | decision | Convert list[list[float]] → tuple[tuple[float, ...], ...] in service layer (DYK-4) | Inline conversion in T008 reassembly: `tuple(tuple(e) for e in embeddings)` | /didyouknow session |
| 2025-12-22 | T002 | decision | ContentType → ChunkConfig mapping via inline conditional (DYK-5) | Simple if/elif/else in `_chunk_content()`, not abstracted | /didyouknow session |

**Types**: `gotcha` | `research-needed` | `unexpected-behavior` | `workaround` | `decision` | `debt` | `insight`

_See also: `execution.log.md` for detailed narrative._

---

## Directory Layout

```
docs/plans/009-embeddings/
├── embeddings-spec.md
├── embeddings-plan.md
└── tasks/
    ├── phase-1-core-infrastructure/
    │   ├── tasks.md
    │   └── execution.log.md
    ├── phase-2-embedding-adapters/
    │   ├── tasks.md
    │   ├── execution.log.md
    │   ├── 001-subtask-fixture-graph-fakes.md
    │   └── 001-subtask-fixture-graph-fakes.execution.log.md
    └── phase-3-embedding-service/
        ├── tasks.md                    # This file
        └── execution.log.md            # Created by plan-6
```

---

## Critical Insights Discussion

**Session**: 2025-12-22
**Context**: Phase 3 Embedding Service Tasks & Alignment Brief
**Analyst**: AI Clarity Agent
**Reviewer**: Development Team
**Format**: Water Cooler Conversation (5 Critical Insights)

### Insight 1: Chunk-to-Node Reassembly Tracking (DYK-1)

**Did you know**: After batch-processing embeddings, there's no mechanism to map embeddings back to their original node chunks without explicit tracking.

**Implications**:
- Chunks from multiple nodes get mixed in batches
- After `embed_batch()` returns, we need to know which embedding belongs to which node
- Chunk order matters for reconstructing `tuple[tuple[float, ...], ...]`

**Options Considered**:
- Option A: ChunkItem Data Structure - Create frozen dataclass with node_id, chunk_index, text
- Option B: Parallel Index Lists - Maintain separate texts and metadata lists
- Option C: Node-Centric Batching - Never mix nodes in same batch

**AI Recommendation**: Option A - ChunkItem Data Structure
- Reasoning: Explicit tracking prevents index desync bugs; aligns with KISS principle and ContentType pattern

**Discussion Summary**: User immediately chose Option A. No debate needed.

**Decision**: Create `ChunkItem(node_id, chunk_index, text, is_smart_content)` dataclass

**Action Items**:
- [x] Document ChunkItem in tasks T005, T006, T007, T008
- [x] Update Architecture Map with ChunkItem component
- [x] Update Batching Flow Diagram with reassembly step

**Affects**: T005, T006, T007, T008, Architecture Map

---

### Insight 2: Dual Embedding Unified Batching (DYK-2)

**Did you know**: The spec requires both `embedding` and `smart_content_embedding`, but the tasks don't specify when/how smart_content gets embedded.

**Implications**:
- Each node needs TWO embedding fields populated
- Smart content uses different chunking (8000 tokens vs 400/800)
- Could be two separate passes or unified batching

**Options Considered**:
- Option A: Single Pass, Unified Batching - ChunkItem.is_smart_content flag distinguishes
- Option B: Two Separate Passes - First raw content, then smart_content
- Option C: Optional Smart Content Flag - Config to enable/disable

**AI Recommendation**: Option A - Unified Batching
- Reasoning: Single API call round, consistent control flow, minimal design change

**Discussion Summary**: User chose unified approach. Efficiency wins over separation.

**Decision**: Add `is_smart_content: bool = False` to ChunkItem; reassembly populates both fields

**Action Items**:
- [x] Update ChunkItem design to include is_smart_content
- [x] Update T001, T002 for dual embedding testing/chunking
- [x] Update T008 for dual field reassembly

**Affects**: T001, T002, T005, T006, T007, T008

---

### Insight 3: Full Concurrent Batch Processing (DYK-3)

**Did you know**: The `max_concurrent_batches` config exists (default: 1), meaning we might need asyncio.Event coordination if users set >1.

**Implications**:
- Sequential (=1): Simple try/except per batch
- Concurrent (>1): Need global rate limit coordination
- Could defer concurrent support or implement now

**Options Considered**:
- Option A: Sequential Only - Remove config option
- Option B: Keep Option, Default Sequential - Implement concurrent later
- Option C: Implement Full Concurrency Now - asyncio.Event pattern

**AI Recommendation**: Option B - Keep option, implement sequential only for now
- Reasoning: Default is safe, power users can wait

**Discussion Summary**: User chose Option C - full concurrency now. No tech debt.

**Decision**: Implement asyncio.Event coordination; T009/T010 CS increased 2→3

**Action Items**:
- [x] Update T009 to test both sequential and concurrent modes
- [x] Update T010 to implement asyncio.Event pattern
- [x] Document concurrency in Critical Insights

**Affects**: T009, T010

---

### Insight 4: Type Conversion in Service (DYK-4)

**Did you know**: API returns `list[list[float]]` but CodeNode stores `tuple[tuple[float, ...], ...]`, and the conversion point wasn't specified.

**Implications**:
- Tuples required for frozen dataclass (immutable)
- Tuples are hashable (enable set/dict operations)
- Conversion must happen somewhere

**Options Considered**:
- Option A: Convert in EmbeddingService (T008)
- Option B: Convert in EmbeddingAdapter
- Option C: Add Helper Function

**AI Recommendation**: Option A - Convert in Service
- Reasoning: Single point of truth, adapter stays generic, trivial implementation

**Discussion Summary**: User agreed. One-liner: `tuple(tuple(e) for e in embeddings)`

**Decision**: Inline conversion in T008 during reassembly

**Action Items**:
- [x] Update T008 validation to include tuple conversion

**Affects**: T008

---

### Insight 5: ContentType → ChunkConfig Mapping (DYK-5)

**Did you know**: ContentType (CODE/CONTENT) was created, but the mapping to ChunkConfig (code/documentation) wasn't specified.

**Implications**:
- CODE → config.code (400 tokens)
- CONTENT → config.documentation (800 tokens)
- smart_content → config.smart_content (8000 tokens)

**Options Considered**:
- Option A: Inline Conditional - Simple if/elif/else
- Option B: Mapping Method - Extract `_get_chunk_config()`
- Option C: Dict Mapping - Class attribute

**AI Recommendation**: Option A - Inline Conditional
- Reasoning: Only 2 branches + smart_content, not worth abstracting

**Discussion Summary**: User agreed. KISS principle applies.

**Decision**: Simple if/elif/else in `_chunk_content()`, not abstracted

**Action Items**:
- [x] Document inline conditional pattern in T002

**Affects**: T002

---

## Session Summary

**Insights Surfaced**: 5 critical insights identified and discussed
**Decisions Made**: 5 decisions reached through collaborative discussion
**Action Items Created**: 12 follow-up documentation items (all completed inline)
**Areas Updated**:
- Tasks table (T001, T002, T005, T006, T007, T008, T009, T010)
- Architecture Map (ChunkItem component added)
- Batching Flow Diagram (ChunkItem and Reassemble steps)
- Critical Findings section (5 new DYK insights)
- Discoveries & Learnings table (5 new entries)

**Shared Understanding Achieved**: ✓

**Confidence Level**: High - All architectural gaps identified and resolved before implementation

**Next Steps**:
Proceed with T001-T011 implementation. All design decisions captured in DYK-1 through DYK-5.

**Notes**:
- ChunkItem is now the central data structure for batch processing
- T009/T010 complexity increased from CS-2 to CS-3 due to full concurrency decision
- All 5 insights aligned with KISS principle - minimal abstraction, explicit over implicit
