# Embedding Service Implementation Plan

**Plan Version**: 1.3.0
**Created**: 2025-12-19
**Updated**: 2025-12-19 (Per-content-type ChunkConfig: code, documentation, smart_content)
**Spec**: [./embeddings-spec.md](./embeddings-spec.md)
**Status**: READY

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 1: Core Infrastructure](#phase-1-core-infrastructure)
   - [Phase 2: Embedding Adapters](#phase-2-embedding-adapters)
   - [Phase 3: Embedding Service](#phase-3-embedding-service)
   - [Phase 4: Pipeline Integration](#phase-4-pipeline-integration)
   - [Phase 5: Testing & Validation](#phase-5-testing--validation)
   - [Phase 6: Documentation](#phase-6-documentation)
   - [Phase 7: Fixture Graph for Integration Testing](#phase-7-fixture-graph-for-integration-testing)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: Text-based search (grep, regex) finds exact matches but misses conceptual relationships. Developers cannot search by meaning ("authentication flow", "error handling patterns"), limiting codebase exploration and AI-assisted development.

**Solution**:
- Build an embedding service that converts code content and smart content into dense vector representations
- Implement content-type aware chunking (400 tokens for code, 800 for docs)
- Follow proven SmartContentService async batch processing pattern
- Support multiple providers (Azure OpenAI, OpenAI-compatible, Fake for testing)
- Store embeddings in CodeNode with graph config node for model tracking

**Expected Outcomes**:
- Semantic similarity search capability for codebase
- Incremental embedding updates via hash-based skip logic
- Full TDD coverage with fixture-based testing
- Hybrid documentation (README + docs/how/)
- Fixture graph system enabling deterministic integration testing for Search feature (next plan)

**Success Metrics**:
- All 11 acceptance criteria from spec validated
- 80%+ test coverage for new code
- Embedding generation completes for 1000 nodes within reasonable time
- No API rate limit failures with proper backoff

---

## Technical Context

### Current System State

The fs2 codebase uses Clean Architecture with:
- **Adapters**: ABC interfaces with implementation files (`*_adapter.py` + `*_adapter_*.py`)
- **Services**: Composition layer with `ConfigurationService` injection
- **Pipeline**: `PipelineStage` protocol with `DiscoveryStage → ParsingStage → SmartContentStage → StorageStage`
- **Models**: Frozen `CodeNode` dataclass with `replace()` for updates

### Integration Requirements

| Component | Integration Point | Notes |
|-----------|------------------|-------|
| `CodeNode` | Existing `embedding` field | Already defined as `list[float] \| None` |
| `ConfigurationService` | `config.require(EmbeddingConfig)` | Follow SmartContentConfig pattern |
| `PipelineContext` | Add `embedding_service` field | Mirror smart_content_service pattern |
| `ScanPipeline` | Insert EmbeddingStage after SmartContentStage | Before StorageStage |
| `TokenCounterAdapter` | Reuse for chunking | Already implemented with tiktoken |

### Constraints and Limitations

1. **Token Limits**: Azure 8000, OpenAI 8191 tokens max per embedding
2. **Frozen CodeNode**: All updates via `dataclasses.replace()`
3. **Pickle Security**: Only `list[float]` allowed (no numpy arrays)
4. **Rate Limiting**: Exponential backoff with max 60 second cap

### Assumptions

1. Azure OpenAI text-embedding-3-small model available
2. SmartContentService pattern directly applicable
3. tiktoken cl100k_base encoding works for embedding models
4. Graph pickle format handles additional embedding data

---

## Critical Research Findings

### Deduplication Log

| Final # | Sources | Merged Topics |
|---------|---------|---------------|
| 01 | I1-03, R1-01 | Frozen CodeNode extension + replace() pattern |
| 02 | I1-04, R1-09 | Async batch processing + stateless design |
| 03 | R1-03, R1-06 | Rate limiting + exponential backoff |
| 04 | I1-01, I1-09 | Config pattern + content-type awareness |
| 05 | R1-02 | Pickle security constraints |

---

### 01: Frozen CodeNode Extension Pattern

**Impact**: Critical
**Sources**: [I1-03, I1-08, R1-01]
**Problem**: CodeNode is frozen dataclass. Direct mutation raises FrozenInstanceError. Adding embeddings requires careful coordination.

**Root Cause**: `@dataclass(frozen=True)` prevents attribute assignment after construction. The `embedding` field exists but is None by default.

**Solution**: Use `dataclasses.replace()` for all updates:
```python
# In EmbeddingService.generate_embedding():
updated_node = replace(
    node,
    embedding=embedding_vector,
    # Note: embedding_hash not in current CodeNode - use content_hash for skip logic
)
```

**Action Required**: All embedding updates must use `replace()`. Never instantiate CodeNode directly in embedding service.
**Affects Phases**: Phase 3, Phase 4

---

### 02: Proven Async Batch Processing Pattern

**Impact**: Critical
**Sources**: [I1-04, R1-09]
**Problem**: Parallel processing requires careful state management. Instance-level caches cause race conditions.

**Root Cause**: SmartContentService.process_batch() creates local queue/lock per batch. Service instance is stateless.

**Solution**: Follow CD10 (Stateless Service Design):
```python
async def process_batch(self, nodes: list[CodeNode]) -> EmbeddingResult:
    # All state is LOCAL to this method
    queue: asyncio.Queue[CodeNode | None] = asyncio.Queue()
    stats = {"processed": 0, "skipped": 0, "errors": 0}
    stats_lock = asyncio.Lock()
    # ... worker pool pattern
```

**Action Required**: EmbeddingService must have NO mutable instance attributes except config/adapters. All batch state local to method.
**Affects Phases**: Phase 3

---

### 03: Rate Limit Handling with Global Backoff

**Impact**: Critical
**Sources**: [R1-03, R1-06]
**Problem**: 50 workers hitting rate limit simultaneously create 800+ second total backoff. No global coordination.

**Root Cause**: Per-adapter exponential backoff with no shared rate limit flag. Workers retry independently.

**Solution**: Add rate limit coordination:
```python
rate_limit_event = asyncio.Event()

async def worker(worker_id: int):
    while True:
        if rate_limit_event.is_set():
            await asyncio.sleep(backoff_time)
            rate_limit_event.clear()
        # ... process item
        try:
            result = await adapter.embed(text)
        except EmbeddingRateLimitError:
            rate_limit_event.set()
            # All workers will pause
```

**Action Required**: Implement global rate limit coordination. Cap max backoff at 60 seconds.
**Affects Phases**: Phase 2, Phase 3

---

### 04: Content-Type Aware Configuration Pattern

**Impact**: Critical
**Sources**: [I1-01, I1-09]
**Problem**: Different content types need different chunk sizes. Code needs 400 tokens, docs need 800.

**Root Cause**: External research confirmed optimal chunk sizes vary by content type.

**Solution**: Create EmbeddingConfig with per-content-type nested configs:
```python
class ChunkConfig(BaseModel):
    """Chunking parameters for a specific content type."""
    max_tokens: int          # Maximum tokens per chunk
    overlap_tokens: int      # Overlap between chunks

class EmbeddingConfig(BaseModel):
    __config_path__: ClassVar[str] = "embedding"

    mode: Literal["azure", "openai_compatible", "fake"] = "azure"
    max_workers: int = 50

    # Per-content-type chunking configuration
    code: ChunkConfig = Field(default_factory=lambda: ChunkConfig(max_tokens=400, overlap_tokens=50))
    documentation: ChunkConfig = Field(default_factory=lambda: ChunkConfig(max_tokens=800, overlap_tokens=120))
    smart_content: ChunkConfig = Field(default_factory=lambda: ChunkConfig(max_tokens=8000, overlap_tokens=0))

    # Retry configuration (per Flowspace pattern, DYK-4)
    max_retries: int = 3        # Max retry attempts for 429/5xx errors
    base_delay: float = 2.0     # Base delay in seconds for exponential backoff
    max_delay: float = 60.0     # Maximum delay cap in seconds
```

**YAML Config Example**:
```yaml
embedding:
  mode: azure
  max_workers: 50
  # Retry configuration
  max_retries: 3
  base_delay: 2.0
  max_delay: 60.0
  # Chunking configuration
  code:
    max_tokens: 400
    overlap_tokens: 50
  documentation:
    max_tokens: 800
    overlap_tokens: 120
  smart_content:
    max_tokens: 8000
    overlap_tokens: 0
```

**Action Required**: EmbeddingConfig must define ChunkConfig per content type. Map `node.category` to content type key.
**Affects Phases**: Phase 1

---

### 05: Pickle Security Constraints

**Impact**: Critical
**Sources**: [R1-02]
**Problem**: RestrictedUnpickler only allows whitelisted classes. numpy arrays would fail deserialization.

**Root Cause**: Security boundary prevents arbitrary code execution via pickle.

**Solution**: Store embeddings as plain `list[float]` only:
```python
# ALLOWED
embedding: list[float] = [0.1, 0.2, 0.3, ...]

# FORBIDDEN - would fail unpickling
embedding: np.ndarray = np.array([0.1, 0.2, 0.3])
```

**Action Required**: Never store numpy arrays in CodeNode. Convert all embeddings to `list[float]` before storage.
**Affects Phases**: Phase 2, Phase 3

---

### 06: Service Composition via ConfigurationService

**Impact**: High
**Sources**: [I1-02]
**Problem**: Services need consistent dependency injection pattern.

**Solution**: EmbeddingService follows SmartContentService pattern:
```python
def __init__(
    self,
    config: ConfigurationService,
    embedding_adapter: EmbeddingAdapter,
    token_counter: TokenCounterAdapter,
):
    self._config = config.require(EmbeddingConfig)
    self._adapter = embedding_adapter
    self._token_counter = token_counter
```

**Action Required**: Constructor takes ConfigurationService, extracts EmbeddingConfig internally.
**Affects Phases**: Phase 3

---

### 07: Pipeline Stage Protocol Integration

**Impact**: High
**Sources**: [I1-05, I1-06]
**Problem**: EmbeddingStage must integrate with existing pipeline.

**Solution**: Implement PipelineStage protocol:
```python
class EmbeddingStage:
    @property
    def name(self) -> str:
        return "embedding"

    def process(self, context: PipelineContext) -> PipelineContext:
        if context.embedding_service is None:
            return context  # Skip if --no-embeddings
        # ... process nodes
```

**Action Required**: Add embedding_service field to PipelineContext. Insert EmbeddingStage after SmartContentStage.
**Affects Phases**: Phase 4

---

### 08: Hash-Based Skip Logic

**Impact**: High
**Sources**: [I1-07, R1-05]
**Problem**: Re-embedding unchanged content wastes API calls.

**Solution**: Compare content_hash before embedding:
```python
def _should_skip(self, node: CodeNode) -> bool:
    # Skip if embedding exists AND content unchanged
    return (
        node.embedding is not None and
        len(node.embedding) > 0
        # Content hash comparison handled by prior node merge
    )
```

**Action Required**: Implement skip logic in EmbeddingService. Prior node merge preserves embeddings for unchanged content.
**Affects Phases**: Phase 3, Phase 4

---

### 09: Graph Config Node for Model Tracking

**Impact**: High
**Sources**: [I1-10]
**Problem**: Need to detect model mismatch at search time.

**Solution**: Store embedding metadata in graph:
```python
# Create config entry in graph metadata (not as CodeNode)
graph_config = {
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1024,
    "chunk_config": {
        "code": {"max_tokens": 400, "overlap_tokens": 50},
        "documentation": {"max_tokens": 800, "overlap_tokens": 120},
        "smart_content": {"max_tokens": 8000, "overlap_tokens": 0},
    },
}
# Store in graph metadata during persistence
```

**Action Required**: EmbeddingStage stores model info in graph. Search validates model matches.
**Affects Phases**: Phase 4

---

### 10: Embedding Vector Storage Optimization

**Impact**: High
**Sources**: [R1-08]
**Problem**: 10k nodes with 3072-dim embeddings = 240MB memory.

**Solution**: Use smaller model dimensions and document limits:
```yaml
embedding:
  azure:
    dimensions: 1024  # text-embedding-3-small default
```

**Action Required**: Default to 1024 dimensions. Document memory implications for large codebases.
**Affects Phases**: Phase 1, Phase 6

---

### 11: Token Counter Fallback Handling

**Impact**: Medium
**Sources**: [R1-04]
**Problem**: tiktoken may not recognize new models, silently using wrong encoding.

**Solution**: Add explicit warning and optional strict mode:
```python
try:
    encoder = tiktoken.encoding_for_model(model)
except KeyError:
    logger.warning(f"Model {model} not in tiktoken; using cl100k_base fallback")
    encoder = tiktoken.get_encoding("cl100k_base")
```

**Action Required**: Log warning on fallback. Document that token counts may be approximate.
**Affects Phases**: Phase 3

---

### 12: Atomic Graph Writes

**Impact**: Medium
**Sources**: [R1-10]
**Problem**: Concurrent read/write to graph pickle can corrupt file.

**Solution**: Use atomic write pattern:
```python
with tempfile.NamedTemporaryFile(dir=graph_dir, delete=False) as tmp:
    pickle.dump(graph, tmp)
os.rename(tmp.name, graph_path)  # Atomic on POSIX
```

**Action Required**: StorageStage uses atomic writes. Already implemented - verify embedding updates use same pattern.
**Affects Phases**: Phase 4

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Full TDD
**Rationale**: CS-4 complexity with external API integrations, chunking algorithms, and pipeline integration requires comprehensive test coverage from the start.

### Test-Driven Development

All phases follow RED → GREEN → REFACTOR cycle:
1. Write tests FIRST (RED) - tests fail initially
2. Implement minimal code (GREEN) - tests pass
3. Refactor for quality (REFACTOR) - tests still pass

### Mock Usage

**Policy**: Targeted mocks with pre-computed embedding fixtures

**Approach**:
- **FakeEmbeddingAdapter**: Returns pre-computed embeddings from fixture file
- **Real implementations**: Used for internal components (chunking, token counting, service logic)

**Fixture Generation**:
```python
# One-time script: scripts/generate_embedding_fixtures.py
# Run with real API, save results for deterministic testing
fixtures = [
    {
        "content": "def add(a, b): return a + b",
        "embedding": [0.1, 0.2, ...],  # 1024 dims
    },
    {
        "smart_content": "Adds two numbers together",
        "embedding": [0.3, 0.4, ...],
    },
    # ~20-50 realistic samples covering different content types
]
# Save to tests/fixtures/embedding_fixtures.json
```

**Rationale**: Real embeddings enable testing similarity math with realistic vector distributions.

### Test Documentation

Every test includes:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

---

## Implementation Phases

### Phase 1: Core Infrastructure

**Objective**: Create foundational configuration and extend CodeNode support for embeddings.

**Complexity**: CS-4 (Large) - Updated per DYK session insights

**Deliverables**:
- `ChunkConfig` pydantic model with max_tokens, overlap_tokens validation (DYK-3: overlap >= 0)
- `EmbeddingConfig` pydantic model with:
  - Content-type aware chunk params (code/documentation/smart_content)
  - Retry config: max_retries, base_delay, max_delay (DYK-4: Flowspace pattern)
- Registration in `YAML_CONFIG_TYPES`
- Exception hierarchy with retry metadata:
  - `EmbeddingAdapterError` base
  - `EmbeddingRateLimitError` with retry_after, attempts_made (DYK-4)
  - `EmbeddingAuthenticationError`
- CodeNode field updates (DYK-1, DYK-2):
  - Change `embedding` type: `list[float]` → `tuple[tuple[float, ...], ...]`
  - Add `smart_content_embedding: tuple[tuple[float, ...], ...] | None`
  - Update all factory methods

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Config schema conflicts | Low | Medium | Follow SmartContentConfig pattern exactly |
| CodeNode field type change | Medium | Medium | TDD approach; write tests first |
| Factory method updates | Low | Medium | Systematic update of all 5+ factory methods |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 1.1 | [x] | Write tests for ChunkConfig and EmbeddingConfig validation | 2 | Tests cover: ChunkConfig fields (DYK-3: overlap >= 0), EmbeddingConfig with chunk + retry config, defaults, validation | [📋](./tasks/phase-1-core-infrastructure/execution.log.md#task-t002-t003) | /workspaces/flow_squared/tests/unit/config/test_embedding_config.py |
| 1.2 | [x] | Implement ChunkConfig and EmbeddingConfig models | 3 | All tests from 1.1 pass. Includes retry config per DYK-4, dimensions=1024 per Alignment Finding 10 | [📋](./tasks/phase-1-core-infrastructure/execution.log.md#task-t004-t006) | /workspaces/flow_squared/src/fs2/config/objects.py (add classes after SmartContentConfig) |
| 1.3 | [x] | Write tests for embedding exception hierarchy | 2 | Tests cover: EmbeddingAdapterError, RateLimitError (with retry_after, attempts_made per DYK-4), AuthError | [📋](./tasks/phase-1-core-infrastructure/execution.log.md#task-t007-t008) | /workspaces/flow_squared/tests/unit/adapters/test_embedding_exceptions.py |
| 1.4 | [x] | Add embedding exceptions to exceptions.py | 2 | All tests from 1.3 pass. EmbeddingRateLimitError has retry metadata | [📋](./tasks/phase-1-core-infrastructure/execution.log.md#task-t007-t008) | /workspaces/flow_squared/src/fs2/core/adapters/exceptions.py |
| 1.5 | [x] | Write tests for CodeNode dual embedding fields | 3 | Tests cover: both embedding + smart_content_embedding as tuple-of-tuples, replace(), pickle, factory methods | [📋](./tasks/phase-1-core-infrastructure/execution.log.md#task-t009-t010) | /workspaces/flow_squared/tests/unit/models/test_code_node_embedding.py |
| 1.6 | [x] | Update CodeNode with dual embedding fields | 3 | All tests from 1.5 pass; `embedding` and `smart_content_embedding` both tuple[tuple[float, ...], ...] \| None | [📋](./tasks/phase-1-core-infrastructure/execution.log.md#task-t009-t010) | /workspaces/flow_squared/src/fs2/core/models/code_node.py (type change + new field) |

### Test Examples (Write First!)

```python
# tests/unit/config/test_embedding_config.py
import pytest
from fs2.config.objects import EmbeddingConfig, ChunkConfig

class TestEmbeddingConfig:
    """
    Purpose: Validates EmbeddingConfig correctly parses and validates config
    Quality Contribution: Prevents misconfiguration at startup
    Acceptance Criteria: All validation rules enforced
    """

    def test_default_code_chunk_config(self):
        """Default code chunking matches research findings (400 tokens, 50 overlap)."""
        config = EmbeddingConfig()
        assert config.code.max_tokens == 400
        assert config.code.overlap_tokens == 50

    def test_default_documentation_chunk_config(self):
        """Default docs chunking matches research findings (800 tokens, 120 overlap)."""
        config = EmbeddingConfig()
        assert config.documentation.max_tokens == 800
        assert config.documentation.overlap_tokens == 120

    def test_default_smart_content_chunk_config(self):
        """Smart content uses large max (8000) with no overlap."""
        config = EmbeddingConfig()
        assert config.smart_content.max_tokens == 8000
        assert config.smart_content.overlap_tokens == 0

    def test_azure_mode_requires_endpoint(self):
        """Azure mode validates required fields."""
        with pytest.raises(ValueError, match="endpoint required"):
            EmbeddingConfig(mode="azure", azure=AzureEmbeddingConfig())

    def test_overlap_cannot_exceed_max_tokens(self):
        """Overlap larger than max_tokens is rejected."""
        with pytest.raises(ValueError, match="overlap.*exceed"):
            ChunkConfig(max_tokens=100, overlap_tokens=150)
```

### Non-Happy-Path Coverage
- [ ] Invalid mode value rejected
- [ ] Missing required Azure fields detected
- [ ] Negative max_tokens rejected
- [ ] Overlap larger than max_tokens rejected
- [ ] Zero max_tokens rejected

### Acceptance Criteria
- [ ] EmbeddingConfig registered in YAML_CONFIG_TYPES
- [ ] Exception hierarchy follows existing pattern
- [ ] CodeNode.embedding field verified via tests
- [ ] All tests passing (6 test files)

---

### Phase 2: Embedding Adapters

**Objective**: Create embedding adapter ABC and provider implementations following fs2 patterns.

**Deliverables**:
- `EmbeddingAdapter` ABC with async embed methods
- `AzureEmbeddingAdapter` implementation
- `OpenAICompatibleEmbeddingAdapter` implementation
- `FakeEmbeddingAdapter` with fixture support

**Dependencies**: Phase 1 complete (exceptions, config)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API rate limiting | High | Medium | Exponential backoff with global coordination |
| Azure auth failures | Medium | High | Clear error messages with fix instructions |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.0 | [ ] | Generate embedding fixtures file | 2 | 30+ samples (code, docs, smart content) with real embeddings. Run: `python scripts/generate_embedding_fixtures.py` | - | /workspaces/flow_squared/tests/fixtures/embedding_fixtures.json (requires FS2_AZURE__EMBEDDING__* env vars) |
| 2.1 | [ ] | Write tests for EmbeddingAdapter ABC | 2 | Tests cover: interface compliance, method signatures | - | /workspaces/flow_squared/tests/unit/adapters/test_embedding_adapter.py |
| 2.2 | [ ] | Implement EmbeddingAdapter ABC | 2 | ABC defined with embed_text, embed_batch methods | - | /workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter.py |
| 2.3 | [ ] | Write tests for FakeEmbeddingAdapter | 2 | Tests cover: fixture loading, deterministic responses, hash-based fallback | - | /workspaces/flow_squared/tests/unit/adapters/test_embedding_adapter_fake.py |
| 2.4 | [ ] | Implement FakeEmbeddingAdapter | 2 | Returns pre-computed embeddings from fixture file; hash-based fallback for unknown content | - | /workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_fake.py |
| 2.5 | [ ] | Write tests for AzureEmbeddingAdapter | 3 | Tests cover: auth, embed, rate limit with asyncio.Event coordination, exponential backoff (max 60s) | - | /workspaces/flow_squared/tests/unit/adapters/test_embedding_adapter_azure.py |
| 2.6 | [ ] | Implement AzureEmbeddingAdapter | 3 | Azure OpenAI integration with retry logic and global rate limit event | - | /workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_azure.py |
| 2.7 | [ ] | Write tests for OpenAICompatibleAdapter | 2 | Tests cover: generic OpenAI API compliance | - | /workspaces/flow_squared/tests/unit/adapters/test_embedding_adapter_openai.py |
| 2.8 | [ ] | Implement OpenAICompatibleAdapter | 2 | OpenAI-compatible API integration | - | /workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_openai.py |

### Test Examples (Write First!)

```python
# tests/unit/adapters/test_embedding_adapter_fake.py
import pytest
from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

class TestFakeEmbeddingAdapter:
    """
    Purpose: Validates FakeEmbeddingAdapter returns deterministic embeddings
    Quality Contribution: Enables reliable unit testing without API calls
    Acceptance Criteria: Same input always produces same output
    """

    @pytest.fixture
    def adapter(self):
        return FakeEmbeddingAdapter(fixture_path="tests/fixtures/embedding_fixtures.json")

    async def test_embed_text_returns_vector(self, adapter):
        """Embedding returns list of floats with correct dimensions."""
        result = await adapter.embed_text("def add(a, b): return a + b")
        assert isinstance(result, list)
        assert len(result) == 1024  # Default dimensions
        assert all(isinstance(x, float) for x in result)

    async def test_same_input_same_output(self, adapter):
        """Deterministic: identical input produces identical output."""
        text = "def add(a, b): return a + b"
        result1 = await adapter.embed_text(text)
        result2 = await adapter.embed_text(text)
        assert result1 == result2
```

### Non-Happy-Path Coverage
- [ ] API authentication failure returns EmbeddingAuthenticationError
- [ ] Rate limit returns EmbeddingRateLimitError after retries
- [ ] Network timeout handled gracefully
- [ ] Invalid API response handled

### Acceptance Criteria
- [ ] All adapter files follow naming convention
- [ ] FakeEmbeddingAdapter works with fixture file
- [ ] Azure adapter handles rate limits with backoff
- [ ] All tests passing (4 adapter test files)
- [ ] Embeddings returned as list[float] (not numpy)

---

### Phase 3: Embedding Service

**Objective**: Create EmbeddingService with async batch processing, chunking, and hash-based skip logic.

**Deliverables**:
- `EmbeddingService` with `process_batch()` method
- Content-type aware chunking logic
- Hash-based skip logic for incremental updates
- Progress reporting callback

**Dependencies**: Phase 2 complete (adapters)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Race conditions in batch | Medium | High | Follow stateless design (CD10) |
| Memory pressure with large batches | Medium | Medium | Process in chunks, limit worker count |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [ ] | Write tests for content chunking | 3 | Tests cover: code vs docs, overlap, token boundaries, tiktoken fallback for unknown models | - | /workspaces/flow_squared/tests/unit/services/test_embedding_chunking.py |
| 3.2 | [ ] | Implement chunking logic | 3 | Content split by type with correct overlap. Uses TokenCounterAdapter. | - | /workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py: _chunk_content() |
| 3.3 | [ ] | Write tests for hash-based skip | 2 | Tests cover: skip unchanged, process changed | - | /workspaces/flow_squared/tests/unit/services/test_embedding_skip.py |
| 3.4 | [ ] | Implement skip logic | 2 | Unchanged content preserves embeddings | - | /workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py: _should_skip() |
| 3.5 | [ ] | Write tests for process_batch | 3 | Tests cover: parallel processing, progress, errors, **concurrent batches don't interfere (stateless CD10)** | - | /workspaces/flow_squared/tests/unit/services/test_embedding_service.py |
| 3.6 | [ ] | Implement process_batch | 3 | Async worker pool with stats tracking. **All batch state local to method (no instance mutation)** | - | /workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py: process_batch() |
| 3.7 | [ ] | Write tests for rate limit coordination | 2 | Tests cover: global backoff when one worker hits limit via asyncio.Event | - | /workspaces/flow_squared/tests/unit/services/test_embedding_rate_limit.py |
| 3.8 | [ ] | Implement rate limit coordination | 2 | asyncio.Event signals all workers to pause | - | /workspaces/flow_squared/src/fs2/core/services/embedding/embedding_service.py: _handle_rate_limit() |
| 3.9 | [ ] | Write test for tiktoken model fallback | 2 | Tests: unknown model logs warning, uses cl100k_base fallback | - | /workspaces/flow_squared/tests/unit/services/test_token_counter_fallback.py |

### Test Examples (Write First!)

```python
# tests/unit/services/test_embedding_chunking.py
import pytest
from fs2.core.services.embedding.embedding_service import EmbeddingService
from fs2.config.objects import EmbeddingConfig, ChunkConfig

class TestContentChunking:
    """
    Purpose: Validates chunking respects content-type specific parameters
    Quality Contribution: Ensures optimal chunk sizes for search quality
    Acceptance Criteria: Code=400, documentation=800, smart_content=8000 tokens
    """

    def test_code_content_uses_configured_chunk_size(self, embedding_service):
        """Code content chunked at config.code.max_tokens with overlap."""
        content = "x" * 10000  # Long code content
        chunks = embedding_service._chunk_content(content, content_type="code")

        # Each chunk should be ~400 tokens (default, not exact due to boundaries)
        for chunk in chunks[:-1]:  # Except last
            token_count = embedding_service._token_counter.count_tokens(chunk)
            assert 350 <= token_count <= 450

    def test_documentation_content_uses_configured_chunk_size(self, embedding_service):
        """Documentation chunked at config.documentation.max_tokens with overlap."""
        content = "word " * 5000  # Long doc content
        chunks = embedding_service._chunk_content(content, content_type="documentation")

        for chunk in chunks[:-1]:
            token_count = embedding_service._token_counter.count_tokens(chunk)
            assert 700 <= token_count <= 900

    def test_smart_content_uses_large_chunk_size(self, embedding_service):
        """Smart content uses config.smart_content.max_tokens (8000 default)."""
        # Smart content is typically short, but test chunking still works
        content = "description " * 3000  # Force chunking
        chunks = embedding_service._chunk_content(content, content_type="smart_content")

        # With 8000 token limit, most smart content is single chunk
        for chunk in chunks[:-1]:
            token_count = embedding_service._token_counter.count_tokens(chunk)
            assert token_count <= 8000

    def test_custom_chunk_config_respected(self):
        """Custom ChunkConfig overrides defaults."""
        config = EmbeddingConfig(
            code=ChunkConfig(max_tokens=200, overlap_tokens=20)
        )
        service = EmbeddingService(config=config, ...)

        chunks = service._chunk_content("x" * 5000, content_type="code")
        for chunk in chunks[:-1]:
            token_count = service._token_counter.count_tokens(chunk)
            assert 180 <= token_count <= 220


# tests/unit/services/test_embedding_service.py - Stateless design validation
class TestProcessBatchStateless:
    """
    Purpose: Validates process_batch follows CD10 stateless design
    Quality Contribution: Prevents race conditions in concurrent batches
    Acceptance Criteria: Concurrent batches don't interfere with each other
    """

    async def test_concurrent_batches_no_interference(self, embedding_service):
        """Concurrent process_batch calls maintain isolation."""
        nodes_batch1 = [create_code_node("batch1_" + str(i)) for i in range(10)]
        nodes_batch2 = [create_code_node("batch2_" + str(i)) for i in range(10)]

        # Run concurrently
        result1, result2 = await asyncio.gather(
            embedding_service.process_batch(nodes_batch1),
            embedding_service.process_batch(nodes_batch2),
        )

        # Each batch has independent stats
        assert result1["processed"] == 10
        assert result2["processed"] == 10
        # No cross-contamination
        assert set(result1["results"].keys()) != set(result2["results"].keys())


# tests/unit/services/test_embedding_rate_limit.py - Rate limit coordination
class TestRateLimitCoordination:
    """
    Purpose: Validates global rate limit coordination across workers
    Quality Contribution: Prevents cascading rate limit failures
    Acceptance Criteria: All workers pause when any hits rate limit
    """

    async def test_rate_limit_event_pauses_all_workers(self, embedding_service, mock_adapter):
        """When one worker hits rate limit, all workers pause."""
        # Configure mock to return rate limit on first call
        mock_adapter.embed_text.side_effect = [
            EmbeddingRateLimitError("Rate limited"),
            [0.1] * 1024,  # Success after backoff
            [0.2] * 1024,
        ]

        nodes = [create_code_node(f"node_{i}") for i in range(3)]
        result = await embedding_service.process_batch(nodes)

        # All nodes eventually processed (after backoff)
        assert result["processed"] == 3
        # Rate limit was hit and recovered
        assert result.get("rate_limit_pauses", 0) >= 1


# tests/unit/services/test_token_counter_fallback.py - Tiktoken fallback
class TestTokenCounterFallback:
    """
    Purpose: Validates tiktoken uses cl100k_base fallback for unknown models
    Quality Contribution: Prevents crashes with new embedding models
    Acceptance Criteria: Warning logged, fallback encoding used
    """

    def test_unknown_model_uses_fallback(self, caplog):
        """Unknown model logs warning and uses cl100k_base."""
        from fs2.core.adapters.token_counter_adapter_tiktoken import TiktokenTokenCounterAdapter

        adapter = TiktokenTokenCounterAdapter(model="future-embedding-model-v9")

        # Should work (fallback used)
        count = adapter.count_tokens("Hello world")
        assert count > 0

        # Warning should be logged
        assert "not in tiktoken" in caplog.text or "fallback" in caplog.text.lower()
```

### Non-Happy-Path Coverage
- [ ] Empty content returns empty embedding list
- [ ] Very short content (< chunk size) returns single embedding
- [ ] Worker failure doesn't crash entire batch
- [ ] Progress callback receives accurate counts

### Acceptance Criteria
- [ ] Chunking respects content-type parameters
- [ ] Hash-based skip reduces API calls for unchanged content
- [ ] Parallel processing with configurable workers
- [ ] Rate limit coordination across workers
- [ ] All tests passing (4 service test files)

---

### Phase 4: Pipeline Integration

**Objective**: Integrate embedding generation into scan pipeline with CLI support.

**Deliverables**:
- `EmbeddingStage` implementing PipelineStage protocol
- `PipelineContext` extension with embedding_service field
- CLI `--no-embeddings` flag
- Graph config node with embedding metadata

**Dependencies**: Phase 3 complete (service)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Pipeline ordering issues | Low | High | Insert after SmartContentStage, before StorageStage |
| Graph metadata corruption | Low | Medium | Atomic writes, validation on load |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Write tests for PipelineContext extension | 2 | Tests cover: embedding_service field, optional None | - | /workspaces/flow_squared/tests/unit/services/test_pipeline_context.py |
| 4.2 | [ ] | Extend PipelineContext | 1 | Add `embedding_service: EmbeddingService \| None = None`, `embedding_progress_callback` | - | /workspaces/flow_squared/src/fs2/core/services/pipeline_context.py |
| 4.3 | [ ] | Write tests for EmbeddingStage | 3 | Tests cover: process nodes, skip if no service, metrics | - | /workspaces/flow_squared/tests/unit/services/test_embedding_stage.py |
| 4.4 | [ ] | Implement EmbeddingStage | 3 | Process nodes via EmbeddingService, update context | - | /workspaces/flow_squared/src/fs2/core/services/stages/embedding_stage.py |
| 4.5 | [ ] | Write tests for graph config node | 2 | Tests cover: store metadata as dict in graph, validate on load, detect model mismatch | - | /workspaces/flow_squared/tests/unit/services/test_graph_config.py |
| 4.6 | [ ] | Implement graph config storage | 2 | Store `{"embedding_model": str, "embedding_dimensions": int, "chunk_params": dict}` in graph metadata | - | /workspaces/flow_squared/src/fs2/core/services/stages/embedding_stage.py |
| 4.7 | [ ] | Write tests for CLI flag | 2 | Tests cover: `fs2 scan --no-embeddings /path` skips stage | - | /workspaces/flow_squared/tests/integration/test_cli_embeddings.py |
| 4.8 | [ ] | Implement CLI flag | 2 | Add --no-embeddings to scan command | - | /workspaces/flow_squared/src/fs2/cli/commands/scan.py |

### Test Examples (Write First!)

```python
# tests/unit/services/test_embedding_stage.py
import pytest
from fs2.core.services.stages.embedding_stage import EmbeddingStage

class TestEmbeddingStage:
    """
    Purpose: Validates EmbeddingStage correctly integrates with pipeline
    Quality Contribution: Ensures embedding generation in scan workflow
    Acceptance Criteria: Stage processes nodes and updates context
    """

    def test_stage_skips_when_no_service(self, pipeline_context):
        """Stage gracefully skips when embedding_service is None."""
        pipeline_context.embedding_service = None
        stage = EmbeddingStage()

        result = stage.process(pipeline_context)

        assert result is pipeline_context  # Unchanged
        assert result.metrics.get("embedding_enriched", 0) == 0

    def test_stage_processes_nodes(self, pipeline_context, embedding_service):
        """Stage processes all nodes and updates embeddings."""
        pipeline_context.embedding_service = embedding_service
        pipeline_context.nodes = {
            "node1": create_code_node("def foo(): pass"),
            "node2": create_code_node("def bar(): pass"),
        }
        stage = EmbeddingStage()

        result = stage.process(pipeline_context)

        assert result.metrics["embedding_enriched"] == 2
        for node in result.nodes.values():
            assert node.embedding is not None
```

### Non-Happy-Path Coverage
- [ ] Stage handles empty node list
- [ ] Stage handles partial failures (some nodes fail)
- [ ] CLI flag correctly disables stage
- [ ] Graph config validates on load

### Acceptance Criteria
- [ ] EmbeddingStage implements PipelineStage protocol
- [ ] Stage inserted after SmartContentStage
- [ ] --no-embeddings flag works
- [ ] Graph config node stores model metadata
- [ ] All tests passing (4 test files)

---

### Phase 5: Testing & Validation

**Objective**: Ensure comprehensive test coverage and validate end-to-end embedding pipeline.

**Deliverables**:
- Integration tests for full pipeline
- Test coverage report > 80%
- Fixture format documentation
- End-to-end validation

**Dependencies**: Phase 4 complete (integration). Note: Fixture generation moved to Phase 2 task 2.0.

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Flaky integration tests | Medium | Medium | Use deterministic FakeAdapter with fixtures from Phase 2 |
| Coverage gaps | Low | Medium | Run coverage report, add tests for uncovered paths |

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write integration tests | 3 | Full pipeline scan with embeddings. Run: `pytest tests/integration/test_embedding_pipeline.py -v` | - | /workspaces/flow_squared/tests/integration/test_embedding_pipeline.py |
| 5.2 | [ ] | Verify test coverage | 1 | Coverage > 80% for embedding code. Run: `pytest --cov=fs2.core.services.embedding --cov=fs2.core.adapters.embedding_adapter` | - | Coverage report |
| 5.3 | [ ] | Document fixture format | 1 | README with schema, regeneration instructions | - | /workspaces/flow_squared/tests/fixtures/README.md |
| 5.4 | [ ] | End-to-end validation | 2 | Scan real project, verify embeddings in graph.pickle | - | Manual verification with `fs2 scan /path/to/project` |

### Test Examples (Write First!)

```python
# tests/integration/test_embedding_pipeline.py
import pytest
from fs2.core.services.scan_pipeline import ScanPipeline

class TestEmbeddingPipeline:
    """
    Purpose: Validates full scan pipeline generates embeddings
    Quality Contribution: End-to-end verification of feature
    Acceptance Criteria: Scanned graph contains embeddings
    """

    async def test_scan_generates_embeddings(self, temp_project):
        """Full scan generates embeddings for all nodes."""
        pipeline = ScanPipeline(
            config=create_config(),
            embedding_service=create_embedding_service(),
        )

        result = await pipeline.run(temp_project)

        assert result.metrics["embedding_enriched"] > 0
        for node in result.nodes.values():
            if node.content:
                assert node.embedding is not None
```

### Acceptance Criteria
- [ ] Integration tests pass with FakeAdapter (from Phase 2 fixtures)
- [ ] Test coverage > 80% for embedding code
- [ ] Fixture format documented in README
- [ ] End-to-end validation completed successfully

---

### Phase 6: Documentation

**Objective**: Document embedding service for users and maintainers.

**Deliverables**:
- README.md section on embedding configuration
- docs/how/embeddings/ detailed guide
- API documentation in code

**Dependencies**: Phase 5 complete (testing verified)

### Discovery & Placement Decision

**Existing docs/how/ structure**: To be surveyed during implementation

**Decision**: Create new `docs/how/embeddings/` directory

**File strategy**: Create numbered files:
- 1-overview.md
- 2-configuration.md
- 3-providers.md

### Tasks (Lightweight Approach for Documentation)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 6.1 | [ ] | Survey existing docs/how/ directories | 1 | List of existing feature dirs documented in log | - | Run: `ls -la /workspaces/flow_squared/docs/how/` |
| 6.2 | [ ] | Update README.md with embeddings section | 2 | Config example, link to docs/how/embeddings/ | - | /workspaces/flow_squared/README.md |
| 6.3 | [ ] | Create docs/how/embeddings/1-overview.md | 2 | Introduction, architecture diagram | - | /workspaces/flow_squared/docs/how/embeddings/1-overview.md |
| 6.4 | [ ] | Create docs/how/embeddings/2-configuration.md | 2 | Config options, env vars, chunk params | - | /workspaces/flow_squared/docs/how/embeddings/2-configuration.md |
| 6.5 | [ ] | Create docs/how/embeddings/3-providers.md | 2 | Azure, OpenAI, Fake adapter setup guides | - | /workspaces/flow_squared/docs/how/embeddings/3-providers.md |
| 6.6 | [ ] | Review documentation for clarity | 1 | Peer review passed, no broken links | - | All docs reviewed |

### Content Outlines

**README.md section** (getting-started only):
```markdown
### Embeddings

Enable semantic search by generating embeddings:

​```yaml
# .fs2/config.yaml
embedding:
  mode: azure
  azure:
    endpoint: "${FS2_AZURE__EMBEDDING__ENDPOINT}"
    api_key: "${FS2_AZURE__EMBEDDING__API_KEY}"
  # Optional: customize chunking per content type
  code:
    max_tokens: 400
    overlap_tokens: 50
  documentation:
    max_tokens: 800
    overlap_tokens: 120
  smart_content:
    max_tokens: 8000
    overlap_tokens: 0
​```

See [docs/how/embeddings/](docs/how/embeddings/) for detailed configuration.
```

**docs/how/embeddings/1-overview.md**:
- What are embeddings and why they matter
- Architecture diagram
- Content-type aware chunking explanation

**docs/how/embeddings/2-configuration.md**:
- Full config.yaml options
- Environment variables
- Chunk parameters

**docs/how/embeddings/3-providers.md**:
- Azure OpenAI setup
- OpenAI-compatible setup
- FakeAdapter for testing

### Acceptance Criteria
- [ ] README.md updated with embeddings section
- [ ] docs/how/embeddings/ created with 3 files
- [ ] Code examples tested and working
- [ ] No broken links

---

### Phase 7: Fixture Graph for Integration Testing

**Objective**: Create a content-addressable fixture graph system that enables deterministic integration testing of the full pipeline (scan → smart content → embeddings → search) without live API calls.

**Deliverables**:
- Fixture samples directory with multi-language code files (Python, Go, TypeScript, Rust, etc.)
- Generation script that scans samples with real APIs to create a complete graph
- `FakeSmartContentAdapter` that looks up pre-computed smart content by content hash
- Enhanced `FakeEmbeddingAdapter` that loads from fixture graph
- Integration test infrastructure using fake adapters

**Context**:
This phase creates the testing foundation for the **Search feature** (out of scope for this plan). By generating real smart content and embeddings for fixture samples, we enable:
1. Full pipeline integration tests without API calls
2. Deterministic, reproducible test runs
3. Realistic AI-generated content for search quality validation

**Dependencies**: Phases 1-4 complete (full embedding pipeline functional)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Fixture graph stale after code changes | Medium | Low | Document regeneration process; git-ignore graph file |
| API costs for regeneration | Low | Low | One-time generation; samples are small (~50 nodes) |
| Hash collisions | Very Low | Medium | Use SHA-256 content hashing |

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Fixture Generation (One-Time with Real APIs)                          │
│                                                                         │
│  tests/fixtures/samples/           scan pipeline        fixture_graph.pkl
│  ├── python/                    ─────────────────►   (all nodes with     │
│  │   ├── auth_handler.py         (real Azure APIs)    real smart_content │
│  │   └── data_parser.py                               and embeddings)    │
│  ├── go/                                                                 │
│  │   └── server.go                                                       │
│  ├── typescript/                                                         │
│  │   └── component.tsx                                                   │
│  ├── rust/                                                               │
│  │   └── lib.rs                                                          │
│  └── markdown/                                                           │
│      └── README.md                                                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│  Runtime Lookup (Hash-Based)                                            │
│                                                                         │
│  ┌─────────────────────┐     ┌─────────────────────────────────────────┐│
│  │ FakeSmartContent    │     │ fixture_graph.nodes                     ││
│  │ Adapter             │ ──► │ {content_hash → node.smart_content}     ││
│  │ generate(content)   │     │                                         ││
│  └─────────────────────┘     └─────────────────────────────────────────┘│
│                                                                         │
│  ┌─────────────────────┐     ┌─────────────────────────────────────────┐│
│  │ FakeEmbedding       │     │ fixture_graph.nodes                     ││
│  │ Adapter             │ ──► │ {content → node.raw_embedding}          ││
│  │ embed(content)      │     │ {smart_content → node.smart_embedding}  ││
│  └─────────────────────┘     └─────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
```

### Fixture Samples Strategy

**Language Coverage** (representative samples for each supported language):

| Language | Sample File | Concepts Covered |
|----------|-------------|------------------|
| Python | `auth_handler.py` | Classes, methods, decorators, type hints |
| Python | `data_parser.py` | Functions, error handling, generators |
| Go | `server.go` | Structs, interfaces, goroutines |
| TypeScript | `component.tsx` | React components, hooks, JSX |
| Rust | `lib.rs` | Traits, implementations, lifetimes |
| Markdown | `README.md` | Documentation, headers, code blocks |

**Sample Complexity**: Each sample should be 50-150 lines with 3-5 symbols (class + methods or functions). This creates ~30-50 total nodes in the fixture graph.

### Tasks (Full TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 7.1 | [ ] | Create fixture samples directory structure | 1 | Directories for each language created | - | /workspaces/flow_squared/tests/fixtures/samples/{python,go,typescript,rust,markdown}/ |
| 7.2 | [ ] | Write Python fixture samples | 2 | 2 Python files, ~100 lines each, realistic code | - | /workspaces/flow_squared/tests/fixtures/samples/python/auth_handler.py, data_parser.py |
| 7.3 | [ ] | Write Go fixture sample | 2 | 1 Go file with struct, interface, goroutine | - | /workspaces/flow_squared/tests/fixtures/samples/go/server.go |
| 7.4 | [ ] | Write TypeScript fixture sample | 2 | 1 TSX file with React component, hooks | - | /workspaces/flow_squared/tests/fixtures/samples/typescript/component.tsx |
| 7.5 | [ ] | Write Rust fixture sample | 2 | 1 Rust file with trait, impl | - | /workspaces/flow_squared/tests/fixtures/samples/rust/lib.rs |
| 7.6 | [ ] | Write Markdown fixture sample | 1 | 1 README with headers, code blocks | - | /workspaces/flow_squared/tests/fixtures/samples/markdown/README.md |
| 7.7 | [ ] | Write tests for fixture graph generation | 2 | Tests cover: scan samples, verify all nodes have smart_content and embeddings | - | /workspaces/flow_squared/tests/unit/fixtures/test_fixture_graph_generation.py |
| 7.8 | [ ] | Implement fixture graph generation script | 3 | Script scans samples with real APIs, saves graph. Run: `python scripts/generate_fixture_graph.py` | - | /workspaces/flow_squared/scripts/generate_fixture_graph.py (requires FS2_AZURE__* env vars) |
| 7.9 | [ ] | Write tests for FakeSmartContentAdapter | 2 | Tests cover: hash lookup, missing content handling, deterministic output | - | /workspaces/flow_squared/tests/unit/adapters/test_smart_content_adapter_fake.py |
| 7.10 | [ ] | Implement FakeSmartContentAdapter | 3 | Loads fixture graph, returns smart_content by content_hash lookup | - | /workspaces/flow_squared/src/fs2/core/adapters/smart_content_adapter_fake.py |
| 7.11 | [ ] | Write tests for graph-backed FakeEmbeddingAdapter | 2 | Tests cover: raw content lookup, smart content lookup, fallback behavior | - | /workspaces/flow_squared/tests/unit/adapters/test_embedding_adapter_fake_graph.py |
| 7.12 | [ ] | Enhance FakeEmbeddingAdapter with graph support | 2 | Loads fixture graph, returns embeddings by content lookup | - | /workspaces/flow_squared/src/fs2/core/adapters/embedding_adapter_fake.py (update) |
| 7.13 | [ ] | Write pipeline integration tests using fixture adapters | 3 | Full scan with fake adapters produces same results as fixture graph | - | /workspaces/flow_squared/tests/integration/test_pipeline_with_fixtures.py |
| 7.14 | [ ] | Generate fixture graph (one-time) | 2 | fixture_graph.pkl created with real embeddings | - | /workspaces/flow_squared/tests/fixtures/fixture_graph.pkl |
| 7.15 | [ ] | Document fixture system | 2 | README explains generation, usage, regeneration | - | /workspaces/flow_squared/tests/fixtures/README.md (update from Phase 5) |

### Test Examples (Write First!)

```python
# tests/unit/adapters/test_smart_content_adapter_fake.py
import pytest
from fs2.core.adapters.smart_content_adapter_fake import FakeSmartContentAdapter
from fs2.core.models.code_graph import CodeGraph

class TestFakeSmartContentAdapter:
    """
    Purpose: Validates FakeSmartContentAdapter returns pre-computed smart content
    Quality Contribution: Enables deterministic testing without LLM calls
    Acceptance Criteria: Content hash lookup returns correct smart content
    """

    @pytest.fixture
    def fixture_graph(self) -> CodeGraph:
        return CodeGraph.load("tests/fixtures/fixture_graph.pkl")

    @pytest.fixture
    def adapter(self, fixture_graph) -> FakeSmartContentAdapter:
        return FakeSmartContentAdapter(fixture_graph=fixture_graph)

    async def test_returns_smart_content_for_known_content(self, adapter):
        """Known content returns pre-computed smart content."""
        # Content from auth_handler.py fixture
        content = '''def authenticate(user: str, token: str) -> bool:
            """Validate user token against auth service."""
            return self._auth_service.validate(user, token)'''

        result = await adapter.generate(content)

        assert result is not None
        assert len(result) > 0
        assert "authenticate" in result.lower() or "token" in result.lower()

    async def test_returns_none_for_unknown_content(self, adapter):
        """Unknown content returns None (not in fixture graph)."""
        result = await adapter.generate("completely random content xyz123")
        assert result is None

    async def test_same_content_same_output(self, adapter):
        """Deterministic: identical content produces identical output."""
        content = "def add(a, b): return a + b"
        result1 = await adapter.generate(content)
        result2 = await adapter.generate(content)
        assert result1 == result2


# tests/unit/adapters/test_embedding_adapter_fake_graph.py
import pytest
from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter
from fs2.core.models.code_graph import CodeGraph

class TestFakeEmbeddingAdapterWithGraph:
    """
    Purpose: Validates FakeEmbeddingAdapter returns real embeddings from fixture graph
    Quality Contribution: Enables similarity testing with realistic vectors
    Acceptance Criteria: Both raw and smart content lookups work
    """

    @pytest.fixture
    def adapter(self) -> FakeEmbeddingAdapter:
        graph = CodeGraph.load("tests/fixtures/fixture_graph.pkl")
        return FakeEmbeddingAdapter(fixture_graph=graph)

    async def test_raw_content_returns_raw_embedding(self, adapter):
        """Raw content lookup returns raw_embedding from matching node."""
        raw_content = "def authenticate(user, token): ..."  # From fixture

        result = await adapter.embed_text(raw_content)

        assert isinstance(result, list)
        assert len(result) == 1024  # Expected dimensions
        assert all(isinstance(x, float) for x in result)

    async def test_smart_content_returns_smart_embedding(self, adapter):
        """Smart content lookup returns smart_embedding from matching node."""
        smart_content = "Validates user authentication tokens..."  # From fixture

        result = await adapter.embed_text(smart_content)

        assert isinstance(result, list)
        assert len(result) == 1024

    async def test_unknown_content_returns_deterministic_fallback(self, adapter):
        """Unknown content returns deterministic fallback (hash-based)."""
        unknown = "completely unknown content xyz"

        result1 = await adapter.embed_text(unknown)
        result2 = await adapter.embed_text(unknown)

        # Fallback is deterministic
        assert result1 == result2


# tests/integration/test_pipeline_with_fixtures.py
import pytest
from fs2.core.services.scan_pipeline import ScanPipeline
from fs2.core.adapters.smart_content_adapter_fake import FakeSmartContentAdapter
from fs2.core.adapters.embedding_adapter_fake import FakeEmbeddingAdapter

class TestPipelineWithFixtureAdapters:
    """
    Purpose: Validates full pipeline works with fixture-backed fake adapters
    Quality Contribution: Integration test without external API calls
    Acceptance Criteria: Scanning fixture samples produces expected results
    """

    @pytest.fixture
    def pipeline(self) -> ScanPipeline:
        graph = CodeGraph.load("tests/fixtures/fixture_graph.pkl")
        return ScanPipeline(
            smart_content_adapter=FakeSmartContentAdapter(fixture_graph=graph),
            embedding_adapter=FakeEmbeddingAdapter(fixture_graph=graph),
        )

    async def test_scan_fixture_samples_matches_graph(self, pipeline):
        """Scanning fixture samples produces same nodes as fixture graph."""
        result = await pipeline.run("tests/fixtures/samples/")

        # All nodes have smart content and embeddings
        for node in result.nodes.values():
            if node.content:
                assert node.smart_content is not None
                assert node.embedding is not None

    async def test_results_are_deterministic(self, pipeline):
        """Multiple scans produce identical results."""
        result1 = await pipeline.run("tests/fixtures/samples/")
        result2 = await pipeline.run("tests/fixtures/samples/")

        assert result1.nodes.keys() == result2.nodes.keys()
        for node_id in result1.nodes:
            assert result1.nodes[node_id].embedding == result2.nodes[node_id].embedding
```

### Fixture Graph Schema

```python
# The fixture graph is a standard CodeGraph with all nodes populated
# Each node contains:

@dataclass(frozen=True)
class CodeNode:
    id: str                              # e.g., "method:python/auth_handler.py:AuthHandler.authenticate"
    path: str                            # e.g., "tests/fixtures/samples/python/auth_handler.py"
    symbol: str                          # e.g., "authenticate"
    category: str                        # e.g., "method"
    content: str                         # Raw source code
    content_hash: str                    # SHA-256 of content (for lookup)
    smart_content: str | None            # AI-generated description (POPULATED)
    embedding: list[float] | None        # Raw content embedding (POPULATED)
    smart_embedding: list[float] | None  # Smart content embedding (POPULATED)
    # ... other fields

# Lookup indexes built at adapter initialization:
# - by_content_hash: {hash → node}           # For smart content lookup
# - by_raw_content: {content → embedding}    # For raw embedding lookup
# - by_smart_content: {smart → embedding}    # For smart embedding lookup
```

### Generation Script

```python
# scripts/generate_fixture_graph.py
"""
One-time script to generate fixture_graph.pkl with real AI content.

Usage:
    # Set Azure credentials
    export FS2_AZURE__OPENAI__ENDPOINT=...
    export FS2_AZURE__OPENAI__API_KEY=...
    export FS2_AZURE__EMBEDDING__ENDPOINT=...
    export FS2_AZURE__EMBEDDING__API_KEY=...

    # Generate fixture graph
    python scripts/generate_fixture_graph.py

    # Verify
    python -c "from fs2.core.models.code_graph import CodeGraph; g = CodeGraph.load('tests/fixtures/fixture_graph.pkl'); print(f'{len(g.nodes)} nodes with embeddings')"

Notes:
    - Requires valid Azure OpenAI credentials
    - API costs are minimal (~50 nodes, ~$0.02)
    - Output: tests/fixtures/fixture_graph.pkl
    - Regenerate when fixture samples change
"""

import asyncio
from pathlib import Path
from fs2.core.services.scan_pipeline import ScanPipeline
from fs2.config import ConfigurationService

async def main():
    config = ConfigurationService.from_env()
    pipeline = ScanPipeline(config)  # Uses real adapters

    samples_dir = Path("tests/fixtures/samples")
    result = await pipeline.run(samples_dir)

    # Verify all nodes populated
    for node in result.nodes.values():
        if node.content:
            assert node.smart_content is not None, f"Missing smart content: {node.id}"
            assert node.embedding is not None, f"Missing embedding: {node.id}"

    # Save fixture graph
    result.graph.save("tests/fixtures/fixture_graph.pkl")
    print(f"Generated fixture_graph.pkl with {len(result.nodes)} nodes")

if __name__ == "__main__":
    asyncio.run(main())
```

### Non-Happy-Path Coverage
- [ ] Unknown content returns None (FakeSmartContentAdapter)
- [ ] Unknown content returns deterministic hash-based fallback (FakeEmbeddingAdapter)
- [ ] Corrupted fixture graph raises clear error
- [ ] Missing fixture graph file detected at import time
- [ ] Hash collision handling (log warning, use first match)

### Acceptance Criteria
- [ ] Fixture samples cover 5+ languages with realistic code
- [ ] fixture_graph.pkl contains ~30-50 nodes with real smart content and embeddings
- [ ] FakeSmartContentAdapter returns smart content by hash lookup
- [ ] FakeEmbeddingAdapter returns embeddings for both raw and smart content
- [ ] Pipeline integration tests pass with fixture adapters
- [ ] Generation script documented with regeneration instructions
- [ ] fixture_graph.pkl committed to repo (small file, deterministic)

### Future: Search System Integration

This fixture graph enables the **Search feature** (next plan after embeddings):

```python
# Example search test enabled by fixture graph
async def test_semantic_search_finds_similar_code():
    """Search for 'authentication' finds auth_handler.py."""
    graph = CodeGraph.load("tests/fixtures/fixture_graph.pkl")
    search = SemanticSearch(graph)

    results = await search.query("user authentication flow")

    assert any("auth_handler" in r.node.path for r in results[:3])
```

---

## Cross-Cutting Concerns

### Security Considerations

| Concern | Implementation |
|---------|---------------|
| API key storage | Use environment variables, never commit |
| Pickle security | RestrictedUnpickler whitelist, no numpy |
| Input validation | Validate content before embedding |

### Observability

| Metric | Location |
|--------|----------|
| embedding_enriched | PipelineContext.metrics |
| embedding_skipped | PipelineContext.metrics |
| embedding_errors | PipelineContext.metrics |
| rate_limit_pauses | EmbeddingService stats |

### Error Handling

| Error Type | Handling |
|------------|----------|
| EmbeddingAuthenticationError | Fail fast, clear message |
| EmbeddingRateLimitError | Exponential backoff, global pause |
| EmbeddingAdapterError | Log, continue with next node |

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| **Phase 1: Core Infrastructure** | 4 | Large | S=2,I=1,D=2,N=1,F=1,T=2 | Per DYK session: dual embedding fields, type changes, retry config, exception metadata | TDD approach, follow existing patterns |
| EmbeddingService | 4 | Large | S=2,I=1,D=1,N=1,F=1,T=2 | Async batch processing with multiple providers | Follow SmartContentService pattern |
| ChunkingLogic | 3 | Medium | S=1,I=1,D=1,N=1,F=1,T=1 | Token-based content splitting | Content-type config, extensive tests |
| PipelineIntegration | 3 | Medium | S=1,I=2,D=1,N=0,F=1,T=1 | Multiple integration points | Follow existing stage pattern |
| FixtureGraphSystem | 3 | Medium | S=2,I=1,D=1,N=1,F=0,T=2 | Multi-file samples, graph gen, 2 fake adapters | Reuse existing graph/adapter patterns |
| FakeSmartContentAdapter | 2 | Small | S=1,I=0,D=1,N=0,F=0,T=1 | Hash-based lookup from graph | Simple dict lookup |
| FakeEmbeddingAdapter (graph) | 2 | Small | S=1,I=0,D=1,N=0,F=0,T=1 | Content-to-embedding lookup | Extend existing fake |

---

## Progress Tracking

### Phase Completion Checklist
- [x] Phase 1: Core Infrastructure - **COMPLETE** (2025-12-20) - [📋 Execution Log](./tasks/phase-1-core-infrastructure/execution.log.md)
- [ ] Phase 2: Embedding Adapters - PENDING
- [ ] Phase 3: Embedding Service - PENDING
- [ ] Phase 4: Pipeline Integration - PENDING
- [ ] Phase 5: Testing & Validation - PENDING
- [ ] Phase 6: Documentation - PENDING
- [ ] Phase 7: Fixture Graph for Integration Testing - PENDING

### STOP Rule

**IMPORTANT**: This plan must be validated before creating tasks.

1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

**NOTE**: This section is populated during implementation. Footnotes link to specific code changes.

**Phase 1: Core Infrastructure** (Completed 2025-12-20):

[^1]: `src/fs2/config/objects.py:ChunkConfig` - Chunking config model with max_tokens/overlap_tokens validation (DYK-3)
[^2]: `src/fs2/config/objects.py:EmbeddingConfig` - Embedding service config with mode, dimensions=1024, retry config (DYK-4)
[^3]: `src/fs2/core/adapters/exceptions.py:EmbeddingAdapterError` - Base exception for embedding operations
[^4]: `src/fs2/core/adapters/exceptions.py:EmbeddingRateLimitError` - Rate limit error with retry_after, attempts_made (DYK-4)
[^5]: `src/fs2/core/adapters/exceptions.py:EmbeddingAuthenticationError` - Authentication error for HTTP 401
[^6]: `src/fs2/core/models/code_node.py:embedding` - Changed from list[float] to tuple[tuple[float, ...], ...] (DYK-1)
[^7]: `src/fs2/core/models/code_node.py:smart_content_embedding` - New field for AI description embeddings (DYK-2)
[^8]: `tests/unit/config/test_embedding_config.py` - 26 tests for ChunkConfig and EmbeddingConfig
[^9]: `tests/unit/adapters/test_embedding_exceptions.py` - 11 tests for exception hierarchy
[^10]: `tests/unit/models/test_code_node_embedding.py` - 15 tests for CodeNode embedding fields

---

## Deviation Ledger

No constitution or architecture deviations required.

---

## ADR Ledger

| ADR | Status | Affects Phases | Notes |
|-----|--------|----------------|-------|
| - | - | - | No ADRs exist. ADR seeds in spec for future consideration. |

**ADR Seeds** (from spec):
- ADR-001: Chunking vs Truncation Strategy (recommend: chunking)
- ADR-002: Embedding Provider Architecture (recommend: ABC pattern)

---

**Plan Complete**: 2025-12-19
**Next Step**: Run `/plan-4-complete-the-plan` to validate readiness
