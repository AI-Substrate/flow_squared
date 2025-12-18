# Smart Content Generation Service Implementation Plan

**Plan Version**: 1.1.0
**Created**: 2025-12-18
**Updated**: 2025-12-18 (Added asyncio Queue + Worker Pool parallelization pattern from FlowSpace research)
**Spec**: [./smart-content-spec.md](./smart-content-spec.md)
**Status**: DRAFT

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technical Context](#technical-context)
3. [Critical Research Findings](#critical-research-findings)
4. [Testing Philosophy](#testing-philosophy)
5. [Implementation Phases](#implementation-phases)
   - [Phase 1: Foundation & Infrastructure](#phase-1-foundation--infrastructure)
   - [Phase 2: Template System](#phase-2-template-system)
   - [Phase 3: Core Service Implementation](#phase-3-core-service-implementation)
   - [Phase 4: Batch Processing Engine](#phase-4-batch-processing-engine)
   - [Phase 5: CLI Integration & Documentation](#phase-5-cli-integration--documentation)
6. [Cross-Cutting Concerns](#cross-cutting-concerns)
7. [Complexity Tracking](#complexity-tracking)
8. [Progress Tracking](#progress-tracking)
9. [Change Footnotes Ledger](#change-footnotes-ledger)

---

## Executive Summary

**Problem**: CodeNodes in the fs2 graph contain raw source code but lack semantic summaries. Developers exploring codebases must read raw code to understand purpose, slowing comprehension and limiting search capabilities.

**Solution Approach**:
- Add `content_hash` field to CodeNode for change detection
- Create SmartContentService that generates AI summaries using LLMService
- Use Jinja2 templates per node category (file, type, callable, section, block, base)
- Implement hash-based regeneration to avoid redundant LLM calls
- Process nodes in parallel with configurable concurrency
- Enhance `get-node` CLI with `--content` and `--smart-content` flags

**Expected Outcomes**:
- Every CodeNode has a human-readable `smart_content` summary
- Hash-based skip logic prevents unnecessary regeneration
- Configurable token limits and truncation for large content
- CLI access to raw and smart content for any node
- High-throughput parallel processing via asyncio Queue + Worker Pool

**Success Metrics**:
- 100% of nodes processed (no skip logic by category)
- Hash-based regeneration correctly skips unchanged nodes
- Parallel processing with configurable workers (default 50, via config)
- All 13 acceptance criteria from spec satisfied

---

## Technical Context

### Current System State

| Component | Location | State |
|-----------|----------|-------|
| CodeNode model | `src/fs2/core/models/code_node.py` | Has `smart_content` placeholder (None), needs `content_hash` field |
| LLMService | `src/fs2/core/services/llm_service.py` | In development (007-llm-service), provides `async generate()` |
| FakeLLMAdapter | `src/fs2/core/adapters/llm_adapter_fake.py` | Available for testing |
| get-node CLI | `src/fs2/cli/get_node.py` | Exists, needs `--content`/`--smart-content` flags |
| Templates directory | `src/fs2/core/templates/` | Does not exist, needs creation |

### Integration Requirements

1. **LLMService Dependency**: SmartContentService composes LLMService via DI (not direct adapter access)
2. **ConfigurationService Pattern**: Service receives registry, calls `config.require(SmartContentConfig)` internally
3. **Graph Access**: If needed, access via GraphStore ABC (no data copying per R3.5)
4. **Adapter Boundaries**: Token counting wrapped in TokenCounter adapter (not direct tiktoken import)

### Constraints and Limitations

- CodeNode is frozen dataclass → use `dataclasses.replace()` for updates
- Jinja2 templates must load via `importlib.resources` for package compatibility
- tiktoken model-specific → cache encoder instances per model
- Async-first design → all I/O methods are `async def`

### Assumptions

1. LLMService (007) is complete or mockable when Phase 3 begins
2. FakeLLMAdapter supports `set_response()` pattern for testing
3. Python 3.12+ (TaskGroup + Semaphore patterns available)
4. SHA-256 hashing via stdlib hashlib is sufficient

---

## Critical Research Findings

### Deduplication Log

| Final # | Sources | Merged From |
|---------|---------|-------------|
| 01 | S1-01, S4-02 | ConfigurationService registry pattern |
| 02 | S1-02, S4-04 | Adapter ABC + implementation split |
| 03 | S2-01 | Frozen dataclass immutability |
| 04 | S2-02, S4-08 | Jinja2 template loading from package |
| 05 | S2-03 | tiktoken model-specific caching |
| 06 | S2-04, S3-05, FlowSpace | Async Queue + Worker Pool pattern |
| 06b | FlowSpace docs/research/async.md | Event loop blocking prevention |
| 07 | S3-01 | LLM error handling strategy |
| 08 | S3-02 | Empty content edge case |
| 09 | S3-03 | Template validation at init |
| 10 | S3-04 | Concurrency and race conditions |
| 11 | S4-03 | Graph data access prohibition |
| 12 | S1-03, S4-05 | Exception translation boundary |

---

### Critical Discovery 01: ConfigurationService Registry Pattern
**Impact**: Critical
**Sources**: [S1-01, S4-02]
**Problem**: Services must receive `ConfigurationService` (registry), not extracted config objects. Composition root doesn't know what configs services need.
**Solution**: SmartContentService constructor accepts `ConfigurationService`, calls `config.require(SmartContentConfig)` internally.
**Example**:
```python
# ✅ CORRECT - Service extracts its own config
class SmartContentService:
    def __init__(self, config: ConfigurationService, llm_service: LLMService):
        self._config = config.require(SmartContentConfig)
        self._llm_service = llm_service

# ❌ WRONG - Composition root extracts config
def create_service(config: ConfigurationService):
    smart_config = config.require(SmartContentConfig)  # DON'T DO THIS
    return SmartContentService(smart_config, ...)
```
**Action Required**: Define SmartContentConfig in `config/objects.py`, service extracts it internally.
**Affects Phases**: Phase 1, Phase 3

---

### Critical Discovery 02: Adapter ABC + Implementation Split
**Impact**: Critical
**Sources**: [S1-02, S4-04]
**Problem**: Token counting (tiktoken) must be wrapped in adapter ABC to prevent SDK coupling. Service imports ABC only.
**Solution**: Create TokenCounter adapter following three-file pattern.
**Example**:
```
src/fs2/core/adapters/
├── token_counter_adapter.py                 # ABC: count_tokens(text) -> int
├── token_counter_adapter_fake.py            # Test double with configurable returns
└── token_counter_adapter_tiktoken.py        # Real implementation importing tiktoken
```
**Action Required**: Create TokenCounter adapter before SmartContentService.
**Affects Phases**: Phase 1, Phase 3

---

### Critical Discovery 03: Frozen Dataclass Immutability
**Impact**: Critical
**Sources**: [S2-01]
**Problem**: CodeNode is frozen dataclass. Direct field assignment raises `FrozenInstanceError`.
**Solution**: Use `dataclasses.replace()` to create new instances with updated fields.
**Example**:
```python
import dataclasses

# ❌ WRONG - Raises FrozenInstanceError
node.smart_content = "summary"

# ✅ CORRECT - Creates new instance
updated_node = dataclasses.replace(
    node,
    smart_content="AI-generated summary",
    content_hash=hashlib.sha256(node.content.encode()).hexdigest()
)
```
**Action Required**: All CodeNode updates must use `dataclasses.replace()`.
**Affects Phases**: Phase 1, Phase 3, Phase 4

---

### Critical Discovery 04: Jinja2 Template Loading from Package
**Impact**: High
**Sources**: [S2-02, S4-08]
**Problem**: Templates must load from package resources (not filesystem paths) for installation compatibility.
**Solution**: Use `importlib.resources.files()` + `jinja2.DictLoader` pattern.
**Example**:
```python
from importlib import resources
import jinja2

# Load templates from package
templates_pkg = resources.files("fs2.core.templates.smart_content")
template_dict = {}
for name in ["smart_content_file.j2", "smart_content_callable.j2"]:
    template_dict[name] = (templates_pkg / name).read_text()

env = jinja2.Environment(loader=jinja2.DictLoader(template_dict))
template = env.get_template("smart_content_callable.j2")
```
**Action Required**: Create TemplateService that loads templates via importlib.resources.
**Affects Phases**: Phase 2

---

### Critical Discovery 05: tiktoken Model-Specific Caching
**Impact**: High
**Sources**: [S2-03]
**Problem**: tiktoken encoders are model-specific and expensive to create. Creating per-call causes performance issues.
**Solution**: Cache encoder instance per model at service/adapter initialization.
**Example**:
```python
class TiktokenTokenCounter(TokenCounter):
    def __init__(self, model: str = "gpt-4"):
        self._encoder = tiktoken.encoding_for_model(model)  # Cache once

    def count_tokens(self, text: str) -> int:
        return len(self._encoder.encode(text))
```
**Action Required**: TokenCounter adapter must cache encoder instance.
**Affects Phases**: Phase 1

---

### Critical Discovery 06: Async Queue + Worker Pool Pattern
**Impact**: Critical
**Sources**: [S2-04, S3-05, FlowSpace SmartContentService]
**Problem**: Unbounded `asyncio.gather()` launches all tasks immediately. Need controlled concurrency with proper worker lifecycle and progress tracking.
**Solution**: Use asyncio.Queue + Worker Pool pattern from FlowSpace for high-throughput parallel processing.

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────────┐
│                    SmartContentService.process_batch()              │
├─────────────────────────────────────────────────────────────────────┤
│  1. Create asyncio.Queue()                                          │
│  2. Pre-filter with _needs_processing() (hash check)                │
│  3. Enqueue all items needing processing                            │
│  4. Spawn N worker tasks (create_synchronized_worker)               │
│  5. Workers wait until ALL ready (asyncio.Event barrier)            │
│  6. Workers process from queue until None sentinel                  │
│  7. Gather all workers and return aggregated stats                  │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Components**:

1. **Worker Configuration** (configurable via SmartContentConfig):
```python
# Default 50 workers, configurable in .fs2/config.yaml
self._max_workers = self._config.max_workers  # default: 50
```

2. **Synchronized Worker Start** (ensures fair work distribution):
```python
worker_ready_event = asyncio.Event()
workers_ready = [0]  # Use list for nonlocal mutation

async def create_synchronized_worker(worker_id: int):
    workers_ready[0] += 1
    if workers_ready[0] >= actual_workers:
        worker_ready_event.set()  # All workers ready
    else:
        await worker_ready_event.wait()  # Wait for others
    await self._worker_loop(worker_id, stats)
```

3. **Worker Processing Loop**:
```python
async def _worker_loop(self, worker_id: int, stats: dict) -> None:
    self._logger.info(f"Worker {worker_id} started")

    while True:
        item = await self._queue.get()

        if item is None:  # Sentinel for shutdown
            self._logger.debug(f"Worker {worker_id} received stop signal")
            break

        node = item
        try:
            updated_node = await self._process_single(node)
            async with self._stats_lock:
                stats["processed"] += 1
                stats["results"][node.node_id] = updated_node

            # Progress logging every 100 items
            if stats["processed"] % 100 == 0:
                self._logger.info(f"Progress: {stats['processed']}/{stats['total']} nodes")

        except Exception as e:
            self._logger.error(f"Worker {worker_id} error: {e}")
            async with self._stats_lock:
                stats["errors"].append((node.node_id, str(e)))
```

4. **Sentinel Shutdown Pattern**:
```python
# After enqueuing all work items
for _ in range(actual_workers):
    await self._queue.put(None)  # One sentinel per worker

await asyncio.gather(*workers)  # Wait for all workers to complete
```

**Configuration in .fs2/config.yaml**:
```yaml
smart_content:
  max_workers: 50              # Number of parallel workers (default: 50)
  max_input_tokens: 50000      # Truncation threshold
  token_limits:
    file: 200
    type: 200
    callable: 150
```

**Config Binding Note (Critical)**: `SmartContentConfig.__config_path__` MUST be `"smart_content"` to bind this YAML block (and env vars `FS2_SMART_CONTENT__...`) via `ConfigurationService.require(SmartContentConfig)`.

**Action Required**: Implement asyncio.Queue + Worker Pool pattern with configurable worker count.
**Affects Phases**: Phase 1 (config), Phase 4 (implementation)

---

### Critical Discovery 06b: Event Loop Blocking Prevention
**Impact**: Critical
**Sources**: [FlowSpace docs/research/async.md]
**Problem**: Multiple worker coroutines intended to process tasks concurrently can end up serialized if a blocking/synchronous call exists inside an async function. This prevents other workers from progressing, causing only one worker to do all the work.

**Root Cause**:
```python
# ❌ WRONG - Blocking call inside async function serializes workers
async def _process_single(self, node: CodeNode):
    # This blocking call prevents other workers from running
    result = self._llm_service.generate_sync(prompt)  # BLOCKING!
    return result

# Workers appear to run in parallel but actually serialize:
# Worker 0: starts, blocks on generate_sync
# Worker 1-49: waiting for event loop (blocked by Worker 0)
# Worker 0: finishes, event loop yields to Worker 1
# Worker 1: starts, blocks on generate_sync
# ... etc (effectively sequential)
```

**Solution**: Ensure ALL I/O operations in worker coroutines are truly async. If using a synchronous SDK, wrap in `run_in_executor`:
```python
# ✅ CORRECT - Truly async operation allows concurrent workers
async def _process_single(self, node: CodeNode):
    # Option A: Use async SDK method
    result = await self._llm_service.generate(prompt)
    return result

# ✅ CORRECT - Wrap sync operation in executor
async def _process_single(self, node: CodeNode):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,  # Default ThreadPoolExecutor
        self._llm_service.generate_sync,
        prompt
    )
    return result
```

**Verification Test**:
```python
async def test_workers_actually_run_concurrently():
    """Verify workers don't serialize due to blocking calls."""
    fake_llm = FakeLLMAdapter()
    fake_llm.set_delay(0.1)  # 100ms async delay
    config = SmartContentConfig(max_workers=10)
    service = SmartContentService(config, fake_llm, ...)

    nodes = [create_node(f"content_{i}") for i in range(10)]

    start = time.time()
    await service.process_batch(nodes)
    elapsed = time.time() - start

    # If workers are truly parallel: ~0.1s (all 10 run concurrently)
    # If serialized due to blocking: ~1.0s (10 * 0.1s sequential)
    assert elapsed < 0.3, f"Workers appear to be serialized! Took {elapsed:.2f}s"
```

**Action Required**: Verify LLMService.generate() is truly async; add explicit test for concurrent execution.
**Affects Phases**: Phase 3, Phase 4

---

### High Discovery 07: LLM Error Handling Strategy
**Impact**: High
**Sources**: [S3-01]
**Problem**: Spec doesn't define behavior when LLM fails during batch. Need per-node error semantics.
**Solution**: Per-node error handling with specific strategies per error type.
**Example**:
```python
async def process_node(node: CodeNode) -> ProcessResult:
    try:
        response = await self._llm_service.generate(prompt)
        return ProcessResult.ok(smart_content=response.content)
    except LLMAuthenticationError:
        raise  # Fail entire batch - config issue
    except LLMRateLimitError:
        await asyncio.sleep(backoff)
        return await self.process_node(node)  # Retry
    except LLMContentFilterError:
        return ProcessResult.ok(smart_content="[Content filtered]")
    except LLMAdapterError as e:
        logger.warning(f"Node {node.node_id} failed: {e}")
        return ProcessResult.fail(error=str(e))
```
**Action Required**: Define error handling strategy in SmartContentService.
**Affects Phases**: Phase 3, Phase 4

---

### High Discovery 08: Empty Content Edge Case
**Impact**: High
**Sources**: [S3-02]
**Problem**: Nodes with empty/whitespace-only content waste LLM tokens on trivial summarization.
**Solution**: Pre-processing validation skips empty nodes, sets placeholder smart_content.
**Example**:
```python
def should_process(node: CodeNode) -> bool:
    if not node.content or not node.content.strip():
        return False
    if len(node.content.strip()) < 10:
        return False
    return True
```
**Action Required**: Add pre-processing validation before LLM call.
**Affects Phases**: Phase 3

---

### High Discovery 09: Template Validation at Init
**Impact**: High
**Sources**: [S3-03]
**Problem**: Missing or malformed templates cause runtime failures. Need eager validation.
**Solution**: Validate all required templates exist and compile at service initialization.
**Example**:
```python
def __init__(self, ...):
    required_templates = ["smart_content_file.j2", "smart_content_callable.j2", ...]
    for template_name in required_templates:
        if not self._template_exists(template_name):
            raise SmartContentError(f"Missing template: {template_name}")
        self._env.get_template(template_name)  # Pre-compile to catch syntax errors
```
**Action Required**: Add template validation in TemplateService initialization.
**Affects Phases**: Phase 2

---

### High Discovery 10: Concurrency and Deterministic Processing
**Impact**: High
**Sources**: [S3-04]
**Problem**: Concurrent workers updating same node can cause race conditions and hash mismatches.
**Solution**: SmartContentService is stateless - returns new node instances. Caller handles storage.
**Example**:
```python
async def process(self, nodes: list[CodeNode]) -> dict[str, CodeNode]:
    """Process nodes and return new instances with smart_content.

    Returns dict mapping node_id -> updated CodeNode.
    Caller is responsible for storing/merging results.
    """
    results = {}
    for node in nodes:
        updated = await self._process_single(node)
        results[node.node_id] = updated
    return results
```
**Action Required**: Design service as stateless, return new instances.
**Affects Phases**: Phase 3, Phase 4

---

### High Discovery 11: Graph Data Access Prohibition
**Impact**: High
**Sources**: [S4-03]
**Problem**: Per R3.5, services MUST NOT store copies of graph data. All access via GraphStore methods.
**Solution**: If SmartContentService needs graph access, store GraphStore reference only, query on-demand.
**Example**:
```python
# ❌ WRONG - Copying graph data
self._all_nodes = graph_store.all_nodes()

# ✅ CORRECT - Store reference, query on-demand
self._graph_store = graph_store
node = self._graph_store.get_node(node_id)
```
**Action Required**: No graph data caching in SmartContentService.
**Affects Phases**: Phase 3

---

### High Discovery 12: Exception Translation at Adapter Boundary
**Impact**: High
**Sources**: [S1-03, S4-05]
**Problem**: Services must catch domain exceptions only, never SDK exceptions. Adapters translate.
**Solution**: TokenCounter adapter catches tiktoken exceptions, raises TokenCounterError.
**Example**:
```python
# In token_counter_adapter_tiktoken.py (adapter implementation)
class TiktokenTokenCounter(TokenCounter):
    def count_tokens(self, text: str) -> int:
        try:
            return len(self._encoder.encode(text))
        except Exception as e:
            raise TokenCounterError(f"Token counting failed: {e}") from e

# In SmartContentService (service layer)
try:
    tokens = self._token_counter.count_tokens(content)
except TokenCounterError as e:
    # Handle domain exception
    return fallback_count(content)
```
**Action Required**: TokenCounter adapter must translate all tiktoken exceptions.
**Affects Phases**: Phase 1, Phase 3

**Layering Note (Critical)**: Adapter exceptions (e.g., `TokenCounterError`) live only in `src/fs2/core/adapters/exceptions.py`. Service-layer smart content exceptions live separately and may catch/wrap adapter exceptions, but MUST NOT duplicate or re-export them.

---

## Testing Philosophy

### Testing Approach

**Selected Approach**: Full TDD
**Rationale**: Hash logic, template selection, and parallel processing require comprehensive coverage; FakeLLMAdapter enables isolated testing
**Focus Areas**:
- Hash computation and comparison logic
- Template selection by category
- Token-based truncation with tiktoken
- Parallel batch processing
- CLI flag handling (`--content`, `--smart-content`)

### Test-Driven Development

- Write tests FIRST (RED)
- Implement minimal code (GREEN)
- Refactor for quality (REFACTOR)

### Test Documentation

Every test must include:
```python
"""
Purpose: [what truth this test proves]
Quality Contribution: [how this prevents bugs]
Acceptance Criteria: [measurable assertions]
"""
```

### Mock Usage

**Policy**: Targeted mocks (B)
- Use FakeLLMAdapter for all automated tests
- Use FakeTokenCounter for token counting tests
- Real LLM calls reserved for manual validation before release

---

## Implementation Phases

### Phase 1: Foundation & Infrastructure

**Objective**: Create foundational components (config, adapters, hash utilities) that other phases depend on.

**Deliverables**:
- SmartContentConfig in `config/objects.py`
- TokenCounter adapter (ABC + Fake + tiktoken implementation)
- Hash utility functions
- CodeNode `content_hash` field addition
- SmartContentError exception hierarchy

**Dependencies**: None (foundational phase)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| tiktoken installation issues | Low | Medium | `tiktoken` is a required dependency managed by `uv`; keep it pinned and ensure CI/dev installs include it |
| CodeNode field addition breaks tests | Medium | Low | Run full test suite after change |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 1.1 | [x] | Write tests for SmartContentConfig validation | 2 | Tests cover: token limits, max_workers range, required fields | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t001-smartcontentconfig-tests) | Completed · log#task-t001-smartcontentconfig-tests [^1] |
| 1.2 | [x] | Implement SmartContentConfig in objects.py | 2 | All tests from 1.1 pass, config loads from YAML/env | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t002-implement-smartcontentconfig) | Completed · log#task-t002-implement-smartcontentconfig [^2] |
| 1.3 | [x] | Write tests for TokenCounter ABC and FakeTokenCounter | 2 | Tests cover: count_tokens interface, fake configurability | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t003-token-counter-abc-fake-tests) | Completed · log#task-t003-token-counter-abc-fake-tests [^3] |
| 1.4 | [x] | Create TokenCounter ABC and FakeTokenCounter | 2 | All tests from 1.3 pass | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t005-implement-token-counter-adapters) | Completed · log#task-t005-implement-token-counter-adapters [^5] |
| 1.5 | [x] | Write tests for TiktokenTokenCounter | 2 | Tests cover: actual token counts, encoding caching, error handling | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t005-implement-token-counter-adapters) | Completed · offline-safe via fake tiktoken module · log#task-t005-implement-token-counter-adapters [^5] |
| 1.6 | [x] | Implement TiktokenTokenCounter | 2 | All tests from 1.5 pass, encoder cached | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t005-implement-token-counter-adapters) | Completed · encoder cached at init · log#task-t005-implement-token-counter-adapters [^5] |
| 1.7 | [x] | Write tests for hash utility functions | 1 | Tests cover: SHA-256 computation, empty content, unicode | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t006-hash-utility-tests) | Completed · `tests/unit/models/test_hash_utils.py` · log#task-t006-hash-utility-tests [^6] |
| 1.8 | [x] | Implement hash utility functions | 1 | All tests from 1.7 pass | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t007-implement-hash-utilities) | Completed · `src/fs2/core/utils/hash.py` · log#task-t007-implement-hash-utilities [^7] |
| 1.9 | [x] | Write tests for CodeNode content_hash field | 2 | Tests cover: field exists, factory methods compute hash | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t008-codenode-content-hash-tests) | Completed · `tests/unit/models/test_code_node.py` · log#task-t008-codenode-content-hash-tests [^8] |
| 1.10 | [x] | Add content_hash field to CodeNode | 2 | All tests pass, frozen dataclass constraints respected | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t009-implement-codenode-content-hash) | Completed · factories compute via SHA-256 · follow-through call-site updates · log#task-t009-implement-codenode-content-hash [^9] [^10] |
| 1.11 | [x] | Define SmartContentError hierarchy in exceptions.py | 1 | TokenCounterError, TemplateError, SmartContentProcessingError defined | [📋](tasks/phase-1-foundation-and-infrastructure/execution.log.md#task-t011-smart-content-exceptions) | Completed · TokenCounterError (adapter) + service-layer SmartContentError hierarchy · log#task-t011-smart-content-exceptions [^4] [^11] |

### Test Examples (Write First!)

```python
# tests/test_config/test_smart_content_config.py
class TestSmartContentConfig:
    def test_default_values(self):
        """
        Purpose: Proves SmartContentConfig has sensible defaults
        Quality Contribution: Prevents missing config crashes
        Acceptance Criteria: Defaults match spec (50k input tokens, 50 workers)
        """
        config = SmartContentConfig()
        assert config.max_input_tokens == 50000
        assert config.max_workers == 50
        assert config.token_limits["file"] == 200
        assert config.token_limits["callable"] == 150

    def test_max_workers_configurable(self):
        """
        Purpose: Proves max_workers is configurable
        Quality Contribution: Enables tuning for different environments
        Acceptance Criteria: Custom worker count accepted when valid
        """
        config = SmartContentConfig(max_workers=10)
        assert config.max_workers == 10

        config = SmartContentConfig(max_workers=100)
        assert config.max_workers == 100

    def test_invalid_max_workers_rejected(self):
        """
        Purpose: Proves validation catches invalid worker counts
        Quality Contribution: Prevents configuration errors
        Acceptance Criteria: ValueError for workers < 1
        """
        with pytest.raises(ValueError):
            SmartContentConfig(max_workers=0)
        with pytest.raises(ValueError):
            SmartContentConfig(max_workers=-1)
```

### Non-Happy-Path Coverage
- [ ] Empty string content hashing
- [ ] Unicode content in hash computation
- [ ] tiktoken encoding failure (invalid UTF-8)
- [ ] Config validation errors

### Acceptance Criteria
- [ ] SmartContentConfig loads from YAML and environment variables
- [ ] TokenCounter ABC defined with count_tokens method
- [ ] FakeTokenCounter allows configurable return values
- [ ] TiktokenTokenCounter caches encoder instance
- [ ] content_hash field added to CodeNode
- [ ] All factory methods compute content_hash
- [ ] Exception hierarchy follows existing patterns

---

### Phase 2: Template System

**Objective**: Create Jinja2 template infrastructure with category-specific templates and token limit injection.

**Deliverables**:
- Template directory structure (`src/fs2/core/templates/smart_content/`)
- 6 template files (file, type, callable, section, block, base)
- TemplateService for loading and rendering
- Template validation at initialization

**Dependencies**: Phase 1 (SmartContentConfig for token limits)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Template loading fails in installed package | Medium | High | Use importlib.resources pattern |
| Jinja2 syntax errors in templates | Medium | Medium | Pre-compile validation at init |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 2.1 | [x] | Write tests for TemplateService initialization | 2 | Tests cover: template loading, missing template error, syntax validation | [📋](tasks/phase-2-template-system/execution.log.md#task-t004-write-templateservice-init-tests) | Completed (RED tests) · log#task-t004-write-templateservice-init-tests [^14] |
| 2.2 | [x] | Write tests for template selection by category | 2 | Tests cover: all 9 categories map to correct templates | [📋](tasks/phase-2-template-system/execution.log.md#task-t005-write-category-mapping-tests-ac11) | Completed (RED tests) · log#task-t005-write-category-mapping-tests-ac11 [^15] |
| 2.3 | [x] | Write tests for template rendering with context | 2 | Tests cover: all context variables available, token limits injected | [📋](tasks/phase-2-template-system/execution.log.md#task-t006-write-rendering-context-tests-ac8) | Completed (RED tests) · log#task-t006-write-rendering-context-tests-ac8 [^16] |
| 2.4 | [x] | Create template directory structure | 1 | Directory exists at `src/fs2/core/templates/smart_content/` | [📋](tasks/phase-2-template-system/execution.log.md#task-t003-add-templates-package-structure) | With `__init__.py` · Completed · log#task-t003-add-templates-package-structure [^13] |
| 2.5 | [x] | Implement TemplateService with importlib loading | 3 | All tests from 2.1-2.3 pass | [📋](tasks/phase-2-template-system/execution.log.md#task-t007-implement-templateservice-loader-api) | Use DictLoader pattern · Completed · log#task-t007-implement-templateservice-loader-api [^17] |
| 2.6 | [x] | Create smart_content_file.j2 template | 2 | Renders file-level prompts with 200 token limit | [📋](tasks/phase-2-template-system/execution.log.md#task-t009-add-template-files-6) | For `file` category · Completed · log#task-t009-add-template-files-6 [^18] |
| 2.7 | [x] | Create smart_content_type.j2 template | 2 | Renders class/struct prompts with 200 token limit | [📋](tasks/phase-2-template-system/execution.log.md#task-t009-add-template-files-6) | For `type` category · Completed · log#task-t009-add-template-files-6 [^18] |
| 2.8 | [x] | Create smart_content_callable.j2 template | 2 | Renders function/method prompts with 150 token limit | [📋](tasks/phase-2-template-system/execution.log.md#task-t009-add-template-files-6) | For `callable` category · Completed · log#task-t009-add-template-files-6 [^18] |
| 2.9 | [x] | Create smart_content_section.j2 template | 2 | Renders markdown section prompts with 150 token limit | [📋](tasks/phase-2-template-system/execution.log.md#task-t009-add-template-files-6) | For `section` category · Completed · log#task-t009-add-template-files-6 [^18] |
| 2.10 | [x] | Create smart_content_block.j2 template | 2 | Renders IaC block prompts with 150 token limit | [📋](tasks/phase-2-template-system/execution.log.md#task-t009-add-template-files-6) | For `block` category · Completed · log#task-t009-add-template-files-6 [^18] |
| 2.11 | [x] | Create smart_content_base.j2 fallback template | 2 | Generic template for other categories with 100-150 token limit | [📋](tasks/phase-2-template-system/execution.log.md#task-t009-add-template-files-6) | For `definition`, `statement`, `expression`, `other` · Completed · log#task-t009-add-template-files-6 [^18] |
| 2.12 | [x] | Write integration test for all templates | 2 | All templates load and render without error | [📋](tasks/phase-2-template-system/execution.log.md#task-t010-integration-test-load-render-all-templates) | End-to-end template validation · Completed · log#task-t010-integration-test-load-render-all-templates [^19] |

### Test Examples (Write First!)

```python
# tests/test_services/test_template_service.py
class TestTemplateService:
    def test_loads_all_required_templates(self):
        """
        Purpose: Proves all 6 required templates exist and load
        Quality Contribution: Prevents runtime template failures
        Acceptance Criteria: No TemplateNotFound errors
        """
        service = TemplateService()
        required = ["smart_content_file.j2", "smart_content_type.j2",
                   "smart_content_callable.j2", "smart_content_section.j2",
                   "smart_content_block.j2", "smart_content_base.j2"]
        for template_name in required:
            template = service.get_template(template_name)
            assert template is not None

    def test_category_to_template_mapping(self):
        """
        Purpose: Proves AC11 category-to-template mapping
        Quality Contribution: Ensures correct prompts per node type
        Acceptance Criteria: All 9 categories map correctly
        """
        service = TemplateService()
        assert service.get_template_for_category("callable") == "smart_content_callable.j2"
        assert service.get_template_for_category("type") == "smart_content_type.j2"
        assert service.get_template_for_category("other") == "smart_content_base.j2"

    def test_template_context_variables(self):
        """
        Purpose: Proves AC8 context variables available in templates
        Quality Contribution: Ensures prompts have all needed data
        Acceptance Criteria: name, qualified_name, category, ts_kind, language, content, signature, max_tokens
        """
        service = TemplateService()
        context = {
            "name": "my_func",
            "qualified_name": "MyClass.my_func",
            "category": "callable",
            "ts_kind": "function_definition",
            "language": "python",
            "content": "def my_func(): pass",
            "signature": "def my_func():",
            "max_tokens": 150,
        }
        result = service.render("smart_content_callable.j2", context)
        assert "my_func" in result
        assert "python" in result.lower()
```

### Non-Happy-Path Coverage
- [ ] Missing template file
- [ ] Template syntax error
- [ ] Missing context variable in template
- [ ] Empty content in context

### Acceptance Criteria
- [ ] All 6 templates created and valid Jinja2 syntax
- [ ] TemplateService loads templates via importlib.resources
- [ ] Category mapping per AC11 implemented
- [ ] Context variables per AC8 available
- [ ] Token limits injected per category per AC4
- [ ] Fallback to base template for unknown categories per AC3

---

### Phase 3: Core Service Implementation

**Objective**: Implement SmartContentService with hash-based regeneration, truncation, and LLM integration.

**Deliverables**:
- SmartContentService class
- Hash-based skip logic (AC5, AC6)
- Token-based truncation (AC13)
- Single-node processing with error handling
- Integration with LLMService and TemplateService

**Dependencies**: Phase 1 (config, adapters, hash), Phase 2 (templates)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLMService not ready | Medium | High | Use FakeLLMAdapter for all tests |
| Hash comparison edge cases | Medium | Medium | Comprehensive test coverage |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 3.1 | [x] | Write tests for SmartContentService initialization | 2 | Tests cover: DI pattern, config extraction, template validation | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t001-t006-t012) | Complete [^20] |
| 3.2 | [x] | Write tests for hash-based skip logic | 3 | Tests cover: AC5 skip when hash matches, AC6 regenerate when mismatch | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t001-t006-t012) | Complete [^20] |
| 3.3 | [x] | Write tests for content truncation | 2 | Tests cover: AC13 truncation at token limit, WARNING log, marker | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t001-t006-t012) | Complete [^20] |
| 3.4 | [x] | Write tests for single-node processing | 3 | Tests cover: prompt generation, LLM call, result storage | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t001-t006-t012) | Complete [^20] |
| 3.5 | [x] | Write tests for empty/trivial content handling | 2 | Tests cover: skip empty nodes, placeholder smart_content | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t001-t006-t012) | Complete [^20] |
| 3.6 | [x] | Write tests for error handling strategies | 2 | Tests cover: auth error fails, rate limit retries, filter fallback | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t001-t006-t012) | Complete [^20] |
| 3.7 | [x] | Implement SmartContentService skeleton | 2 | Constructor follows DI pattern, config extracted | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t007-t011) | Complete [^21] |
| 3.8 | [x] | Implement hash-based skip/regenerate logic | 3 | AC5 and AC6 tests pass | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t007-t011) | Complete [^22] |
| 3.9 | [x] | Implement content truncation | 2 | AC13 tests pass, WARNING logged | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t007-t011) | Complete [^23] |
| 3.10 | [x] | Implement single-node generate_smart_content | 3 | All tests from 3.4 pass | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t007-t011) | Complete [^24] |
| 3.11 | [x] | Implement error handling strategies | 2 | All tests from 3.6 pass | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t007-t011) | Complete [^25] |
| 3.12 | [x] | Write integration test with FakeLLMAdapter | 2 | End-to-end single node processing works | [📋](tasks/phase-3-core-service-implementation/execution.log.md#task-t001-t006-t012) | Complete [^26] |

### Test Examples (Write First!)

```python
# tests/test_services/test_smart_content_service.py
class TestSmartContentService:
    def test_skips_when_hash_matches(self):
        """
        Purpose: Proves AC5 hash-based skip logic
        Quality Contribution: Prevents redundant LLM calls
        Acceptance Criteria: No LLM call made when hashes match
        """
        fake_llm = FakeLLMAdapter()
        service = SmartContentService(config, fake_llm, ...)

        # Node with existing smart_content and matching hash
        node = create_node_with_smart_content(
            content="def foo(): pass",
            content_hash="abc123",
            smart_content="A function that does foo",
            smart_content_hash="abc123"  # Matches content_hash
        )

        result = await service.process_node(node)

        assert result == node  # Unchanged
        assert fake_llm.call_count == 0  # No LLM call

    def test_regenerates_when_hash_mismatch(self):
        """
        Purpose: Proves AC6 hash-based regeneration
        Quality Contribution: Ensures smart_content stays current
        Acceptance Criteria: LLM called, new smart_content stored
        """
        fake_llm = FakeLLMAdapter()
        fake_llm.set_response("Updated summary")
        service = SmartContentService(config, fake_llm, ...)

        node = create_node_with_smart_content(
            content="def foo(): pass",
            content_hash="abc123",
            smart_content="Old summary",
            smart_content_hash="old_hash"  # Different from content_hash
        )

        result = await service.process_node(node)

        assert result.smart_content == "Updated summary"
        assert result.smart_content_hash == "abc123"
        assert fake_llm.call_count == 1

    def test_truncates_large_content(self):
        """
        Purpose: Proves AC13 token-based truncation
        Quality Contribution: Prevents LLM context overflow
        Acceptance Criteria: Content truncated, marker added, WARNING logged
        """
        large_content = "x" * 100000  # Very large
        node = create_node(content=large_content)

        with capture_logs() as logs:
            result = await service.process_node(node)

        assert "[TRUNCATED]" in result.smart_content or service.last_prompt
        assert any("WARNING" in log and "truncat" in log.lower() for log in logs)
```

### Non-Happy-Path Coverage
- [ ] LLM returns empty response
- [ ] LLM timeout
- [ ] Content filter triggered
- [ ] Rate limit with retry
- [ ] Authentication failure

### Acceptance Criteria
- [ ] AC5: Hash match skips regeneration
- [ ] AC6: Hash mismatch triggers regeneration
- [ ] AC8: Template context variables available
- [ ] AC9: Service uses DI (LLMService injected)
- [ ] AC10: FakeLLMAdapter integration works
- [ ] AC13: Token truncation with WARNING

---

### Phase 4: Batch Processing Engine (Queue + Worker Pool)

**Objective**: Implement high-throughput parallel batch processing using asyncio Queue + Worker Pool pattern with configurable concurrency (default 50 workers).

**Deliverables**:
- asyncio.Queue for work distribution
- Worker pool with synchronized startup (asyncio.Event barrier)
- Sentinel-based worker shutdown
- Thread-safe stats tracking with asyncio.Lock
- Progress logging (every 100 items)
- Configurable worker count via SmartContentConfig

**Dependencies**: Phase 3 (single-node processing)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Event loop blocking | Medium | High | Ensure LLM calls are truly async |
| Race conditions in stats | Low | Medium | Use asyncio.Lock for all stats updates |
| Worker starvation | Low | Low | Synchronized start ensures fair distribution |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         process_batch(nodes: list[CodeNode])                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 1. INITIALIZATION                                                    │    │
│  │    - Create asyncio.Queue()                                          │    │
│  │    - Create asyncio.Lock() for stats                                 │    │
│  │    - Initialize stats dict: {processed, skipped, errors, results}    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 2. PRE-FILTER & ENQUEUE                                              │    │
│  │    for node in nodes:                                                │    │
│  │        if _needs_processing(node):    # Hash check                   │    │
│  │            await queue.put(node)                                     │    │
│  │        else:                                                         │    │
│  │            stats["skipped"] += 1                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 3. SPAWN SYNCHRONIZED WORKERS                                        │    │
│  │    actual_workers = min(max_workers, queue.qsize())                  │    │
│  │    worker_ready_event = asyncio.Event()                              │    │
│  │                                                                      │    │
│  │    for i in range(actual_workers):                                   │    │
│  │        worker = create_task(create_synchronized_worker(i))           │    │
│  │        workers.append(worker)                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 4. WORKER BARRIER (synchronized start)                               │    │
│  │    Each worker:                                                      │    │
│  │        workers_ready += 1                                            │    │
│  │        if workers_ready == actual_workers:                           │    │
│  │            worker_ready_event.set()  # Last worker signals all       │    │
│  │        else:                                                         │    │
│  │            await worker_ready_event.wait()  # Others wait            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 5. WORKER PROCESSING LOOP                                            │    │
│  │    while True:                                                       │    │
│  │        item = await queue.get()                                      │    │
│  │        if item is None: break  # Sentinel                            │    │
│  │        try:                                                          │    │
│  │            updated = await _process_single(item)                     │    │
│  │            async with stats_lock:                                    │    │
│  │                stats["processed"] += 1                               │    │
│  │                stats["results"][item.node_id] = updated              │    │
│  │        except Exception as e:                                        │    │
│  │            async with stats_lock:                                    │    │
│  │                stats["errors"].append((item.node_id, str(e)))        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 6. SENTINEL SHUTDOWN                                                 │    │
│  │    for _ in range(actual_workers):                                   │    │
│  │        await queue.put(None)  # One sentinel per worker              │    │
│  │                                                                      │    │
│  │    await asyncio.gather(*workers)  # Wait for completion             │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │ 7. RETURN RESULTS                                                    │    │
│  │    return {                                                          │    │
│  │        "processed": stats["processed"],                              │    │
│  │        "skipped": stats["skipped"],                                  │    │
│  │        "errors": stats["errors"],                                    │    │
│  │        "results": stats["results"],                                  │    │
│  │        "total": len(nodes)                                           │    │
│  │    }                                                                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 4.1 | [ ] | Write tests for asyncio.Queue initialization | 2 | Tests cover: queue created, items enqueued correctly | - | Foundation |
| 4.2 | [ ] | Write tests for pre-filter hash check before enqueueing | 2 | Tests cover: only nodes needing processing enqueued | - | Efficiency |
| 4.3 | [ ] | Write tests for synchronized worker startup | 3 | Tests cover: all workers start together after barrier | - | Critical for fairness |
| 4.4 | [ ] | Write tests for worker processing loop | 3 | Tests cover: workers pull from queue, process, update stats | - | Core functionality |
| 4.5 | [ ] | Write tests for sentinel shutdown pattern | 2 | Tests cover: workers exit cleanly on None sentinel | - | Graceful shutdown |
| 4.6 | [ ] | Write tests for thread-safe stats tracking | 2 | Tests cover: stats updated correctly under concurrency | - | Uses asyncio.Lock |
| 4.7 | [ ] | Write tests for progress logging | 2 | Tests cover: INFO logged every 100 items | - | Observability |
| 4.8 | [ ] | Write tests for partial failure handling | 2 | Tests cover: worker errors don't stop other workers | - | Per Discovery 07 |
| 4.9 | [ ] | Write tests for configurable worker count | 2 | Tests cover: max_workers from config used | - | Via SmartContentConfig |
| 4.10 | [ ] | Write tests for worker count capping | 2 | Tests cover: actual_workers = min(max_workers, queue.qsize()) | - | Don't spawn idle workers |
| 4.11 | [ ] | Implement process_batch with Queue + Worker Pool | 4 | All tests from 4.1-4.10 pass | - | Main implementation |
| 4.12 | [ ] | Implement create_synchronized_worker | 2 | Barrier tests pass | - | Uses asyncio.Event |
| 4.13 | [ ] | Implement _worker_loop | 3 | Processing and stats tests pass | - | Core worker logic |
| 4.14 | [ ] | Write integration test with 500 nodes | 2 | Batch completes correctly with 50 workers | - | High-throughput validation |

### Test Examples (Write First!)

```python
# tests/test_services/test_smart_content_batch.py
class TestBatchProcessing:
    async def test_workers_start_synchronized(self):
        """
        Purpose: Proves all workers start together after barrier
        Quality Contribution: Ensures fair work distribution
        Acceptance Criteria: All workers start within 10ms of each other
        """
        fake_llm = FakeLLMAdapter()
        fake_llm.set_response("summary")
        service = SmartContentService(config, fake_llm, ...)

        start_times = []
        original_worker_loop = service._worker_loop

        async def tracking_worker_loop(worker_id, stats):
            start_times.append((worker_id, time.time()))
            await original_worker_loop(worker_id, stats)

        service._worker_loop = tracking_worker_loop

        nodes = [create_node(f"content_{i}") for i in range(10)]
        await service.process_batch(nodes)

        # All workers should start within 10ms of each other
        times = [t for _, t in start_times]
        assert max(times) - min(times) < 0.01

    async def test_parallel_processing_with_50_workers(self):
        """
        Purpose: Proves high-throughput parallel processing
        Quality Contribution: Validates performance at scale
        Acceptance Criteria: 100 nodes processed faster than sequential
        """
        fake_llm = FakeLLMAdapter()
        fake_llm.set_delay(0.05)  # 50ms per call
        config = SmartContentConfig(max_workers=50)
        service = SmartContentService(config, fake_llm, ...)

        nodes = [create_node(f"content_{i}") for i in range(100)]

        start = time.time()
        results = await service.process_batch(nodes)
        elapsed = time.time() - start

        # 100 nodes, 50 workers, 0.05s each = ~0.1s (2 batches)
        # Sequential would be: 100 * 0.05 = 5.0s
        assert elapsed < 0.5  # At least 10x faster than sequential
        assert results["processed"] == 100

    async def test_sentinel_shutdown(self):
        """
        Purpose: Proves workers exit cleanly on sentinel
        Quality Contribution: Ensures no hanging workers
        Acceptance Criteria: All workers complete, no pending tasks
        """
        fake_llm = FakeLLMAdapter()
        fake_llm.set_response("summary")
        service = SmartContentService(config, fake_llm, ...)

        nodes = [create_node(f"content_{i}") for i in range(5)]
        results = await service.process_batch(nodes)

        # Verify all workers completed
        assert results["processed"] == 5
        assert len(results["errors"]) == 0

        # Verify queue is empty
        assert service._queue.empty()

    async def test_thread_safe_stats(self):
        """
        Purpose: Proves stats are correctly updated under concurrency
        Quality Contribution: Prevents race conditions in metrics
        Acceptance Criteria: Final stats equal sum of individual operations
        """
        fake_llm = FakeLLMAdapter()
        fake_llm.set_response("summary")
        config = SmartContentConfig(max_workers=50)
        service = SmartContentService(config, fake_llm, ...)

        nodes = [create_node(f"content_{i}") for i in range(1000)]
        results = await service.process_batch(nodes)

        # Stats should be consistent
        assert results["processed"] + results["skipped"] + len(results["errors"]) == len(nodes)
        assert len(results["results"]) == results["processed"]

    async def test_worker_count_capped_to_work_items(self):
        """
        Purpose: Proves we don't spawn more workers than needed
        Quality Contribution: Prevents resource waste
        Acceptance Criteria: actual_workers <= queue size
        """
        fake_llm = FakeLLMAdapter()
        fake_llm.set_response("summary")
        config = SmartContentConfig(max_workers=50)  # High limit
        service = SmartContentService(config, fake_llm, ...)

        # Only 3 nodes, should only spawn 3 workers not 50
        nodes = [create_node(f"content_{i}") for i in range(3)]

        worker_ids_seen = []
        original_worker_loop = service._worker_loop

        async def tracking_worker_loop(worker_id, stats):
            worker_ids_seen.append(worker_id)
            await original_worker_loop(worker_id, stats)

        service._worker_loop = tracking_worker_loop

        await service.process_batch(nodes)

        # Only 3 workers should have been spawned
        assert len(worker_ids_seen) == 3

    async def test_progress_logging(self, caplog):
        """
        Purpose: Proves progress is logged every 100 items
        Quality Contribution: Enables monitoring of long batches
        Acceptance Criteria: INFO log every 100 processed items
        """
        fake_llm = FakeLLMAdapter()
        fake_llm.set_response("summary")
        config = SmartContentConfig(max_workers=50)
        service = SmartContentService(config, fake_llm, ...)

        nodes = [create_node(f"content_{i}") for i in range(250)]

        with caplog.at_level(logging.INFO):
            await service.process_batch(nodes)

        progress_logs = [r for r in caplog.records if "Progress:" in r.message]
        assert len(progress_logs) >= 2  # At 100 and 200

    async def test_partial_failure_continues_processing(self):
        """
        Purpose: Proves worker errors don't stop other workers
        Quality Contribution: Ensures batch resilience
        Acceptance Criteria: Successful nodes processed despite failures
        """
        call_count = [0]

        async def flaky_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] % 3 == 0:
                raise LLMAdapterError("Simulated failure")
            return LLMResponse(content="summary", tokens_used=10, model="test", provider="test")

        fake_llm = FakeLLMAdapter()
        fake_llm.generate = flaky_generate
        service = SmartContentService(config, fake_llm, ...)

        nodes = [create_node(f"content_{i}") for i in range(9)]
        results = await service.process_batch(nodes)

        # 3 should fail, 6 should succeed
        assert results["processed"] == 6
        assert len(results["errors"]) == 3
```

### Implementation Reference

```python
class SmartContentService:
    """Service for generating AI summaries of code nodes."""

    def __init__(self, config: ConfigurationService, llm_service: LLMService, ...):
        self._config = config.require(SmartContentConfig)
        self._llm_service = llm_service
        self._max_workers = self._config.max_workers  # Default: 50
        self._queue: asyncio.Queue | None = None
        self._stats_lock: asyncio.Lock | None = None
        self._logger = logging.getLogger(__name__)

    async def process_batch(self, nodes: list[CodeNode]) -> dict[str, Any]:
        """Process nodes in parallel using Queue + Worker Pool pattern.

        Args:
            nodes: List of CodeNodes to process

        Returns:
            Dict with processed count, skipped count, errors list, and results dict
        """
        self._queue = asyncio.Queue()
        self._stats_lock = asyncio.Lock()
        stats = {
            "processed": 0,
            "skipped": 0,
            "errors": [],
            "results": {},
            "total": len(nodes),
        }

        # Pre-filter and enqueue (check hash before enqueueing)
        work_count = 0
        for node in nodes:
            if self._needs_processing(node):
                await self._queue.put(node)
                work_count += 1
            else:
                stats["skipped"] += 1

        if work_count == 0:
            return stats

        # Cap workers to actual work items
        actual_workers = min(self._max_workers, work_count)
        self._logger.info(f"Starting {actual_workers} workers for {work_count} items")

        # Create synchronized workers
        worker_ready_event = asyncio.Event()
        workers_ready = [0]

        async def create_synchronized_worker(worker_id: int):
            workers_ready[0] += 1
            if workers_ready[0] >= actual_workers:
                worker_ready_event.set()
            else:
                await worker_ready_event.wait()
            await self._worker_loop(worker_id, stats)

        workers = [
            asyncio.create_task(
                create_synchronized_worker(i),
                name=f"smart-content-worker-{i}"
            )
            for i in range(actual_workers)
        ]

        # Add sentinels for shutdown
        for _ in range(actual_workers):
            await self._queue.put(None)

        # Wait for all workers to complete
        await asyncio.gather(*workers)

        self._logger.info(
            f"Batch complete: {stats['processed']} processed, "
            f"{stats['skipped']} skipped, {len(stats['errors'])} errors"
        )

        return stats

    async def _worker_loop(self, worker_id: int, stats: dict) -> None:
        """Worker coroutine that processes items from queue."""
        self._logger.debug(f"Worker {worker_id} started")

        while True:
            item = await self._queue.get()

            if item is None:  # Sentinel
                self._logger.debug(f"Worker {worker_id} received stop signal")
                break

            node = item
            try:
                updated_node = await self._process_single(node)

                async with self._stats_lock:
                    stats["processed"] += 1
                    stats["results"][node.node_id] = updated_node

                    # Progress logging every 100 items
                    if stats["processed"] % 100 == 0:
                        self._logger.info(
                            f"Progress: {stats['processed']}/{stats['total']} nodes processed"
                        )

            except Exception as e:
                self._logger.error(f"Worker {worker_id} error processing {node.node_id}: {e}")
                async with self._stats_lock:
                    stats["errors"].append((node.node_id, str(e)))

        self._logger.debug(f"Worker {worker_id} finished")
```

### Non-Happy-Path Coverage
- [ ] All nodes fail
- [ ] Mixed success/failure
- [ ] Worker count of 1 (sequential fallback)
- [ ] Empty batch (0 nodes)
- [ ] All nodes skipped (hash matches)
- [ ] Worker exception during startup
- [ ] Queue.get() timeout (if bounded queue used)

### Acceptance Criteria
- [ ] AC7: Batch processing with configurable workers (default 50)
- [ ] asyncio.Queue used for work distribution
- [ ] Synchronized worker startup via asyncio.Event barrier
- [ ] Sentinel-based worker shutdown (one None per worker)
- [ ] Thread-safe stats with asyncio.Lock
- [ ] Progress logging every 100 items
- [ ] Worker count capped to min(max_workers, work_items)
- [ ] Partial failures don't stop batch
- [ ] Results include both successes and errors

---

### Phase 5: CLI Integration & Documentation

**Objective**: Enhance get-node CLI command and create documentation.

**Deliverables**:
- `--content` flag for get-node command
- `--smart-content` flag for get-node command
- `docs/how/smart-content.md` documentation

**Dependencies**: Phase 3 (SmartContentService available)

**Risks**:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CLI flag conflicts | Low | Low | Check existing flags |
| Documentation drift | Medium | Low | Include in acceptance criteria |

### Tasks (TDD Approach)

| # | Status | Task | CS | Success Criteria | Log | Notes |
|---|--------|------|----|------------------|-----|-------|
| 5.1 | [ ] | Write tests for get-node --content flag | 2 | Tests cover: outputs raw content for node | - | `tests/test_cli/test_get_node.py` |
| 5.2 | [ ] | Write tests for get-node --smart-content flag | 2 | Tests cover: outputs smart_content for node | - | AC12 |
| 5.3 | [ ] | Write tests for flag mutual exclusivity | 1 | Tests cover: error if both flags used | - | UX decision |
| 5.4 | [ ] | Implement --content flag in get_node.py | 2 | Tests from 5.1 pass | - | Typer option |
| 5.5 | [ ] | Implement --smart-content flag in get_node.py | 2 | Tests from 5.2 pass, AC12 satisfied | - | Typer option |
| 5.6 | [ ] | Survey existing docs/how/ structure | 1 | Document existing directories | - | Discovery step |
| 5.7 | [ ] | Create docs/how/smart-content.md | 2 | Covers: service usage, templates, CLI flags, config | - | Per Documentation Strategy |
| 5.8 | [ ] | Manual testing with real LLM | 2 | End-to-end flow works with Azure/OpenAI | - | Pre-release validation |

### Test Examples (Write First!)

```python
# tests/test_cli/test_get_node.py
class TestGetNodeCLI:
    def test_content_flag_outputs_raw_content(self):
        """
        Purpose: Proves --content flag outputs raw content
        Quality Contribution: Enables script access to node content
        Acceptance Criteria: Outputs node.content to stdout
        """
        result = runner.invoke(app, ["get-node", "callable:lib.py:my_func", "--content"])
        assert result.exit_code == 0
        assert "def my_func():" in result.stdout

    def test_smart_content_flag_outputs_summary(self):
        """
        Purpose: Proves AC12 --smart-content flag
        Quality Contribution: Enables script access to AI summaries
        Acceptance Criteria: Outputs node.smart_content to stdout
        """
        result = runner.invoke(app, ["get-node", "callable:lib.py:my_func", "--smart-content"])
        assert result.exit_code == 0
        # Assumes node has smart_content populated
        assert len(result.stdout) > 0
```

### Documentation Content Outline

**docs/how/smart-content.md**:
1. Overview - What is smart content
2. Configuration - SmartContentConfig options
3. Template Customization - How to modify prompts
4. CLI Usage - `--content` and `--smart-content` flags
5. Batch Processing - Using SmartContentService programmatically
6. Token Limits - Category-specific limits
7. Troubleshooting - Common issues and solutions

### Non-Happy-Path Coverage
- [ ] Node not found
- [ ] Node has no smart_content yet
- [ ] Both flags specified (error)

### Acceptance Criteria
- [ ] AC12: get-node --content outputs raw content
- [ ] AC12: get-node --smart-content outputs AI summary
- [ ] Documentation created at docs/how/smart-content.md
- [ ] Manual testing with real LLM passed

---

## Cross-Cutting Concerns

### Security Considerations

- **API Key Handling**: SmartContentService doesn't handle API keys directly - LLMService handles this
- **Content Filtering**: LLM content filter responses handled gracefully (fallback text)
- **Input Validation**: No user input directly passed to LLM - only CodeNode content from trusted parsing

### Observability

**Logging Strategy**:
- INFO: Batch processing start/complete with node counts
- WARNING: Token truncation, content filter triggers, retries
- ERROR: LLM failures, template errors
- DEBUG: Individual node processing details

**Metrics to Capture**:
- Nodes processed per batch
- Skip rate (hash matches)
- Truncation rate
- Error rate by type
- Average tokens per node category

### Documentation

**Location**: docs/how/ only (per Documentation Strategy)
**Content**: Service usage, template customization, CLI flags, configuration
**Target Audience**: Developers using smart content features
**Maintenance**: Update when adding templates or changing token limits

---

## Complexity Tracking

| Component | CS | Label | Breakdown (S,I,D,N,F,T) | Justification | Mitigation |
|-----------|-----|-------|------------------------|---------------|------------|
| SmartContentService | 3 | Medium | S=1,I=1,D=1,N=1,F=1,T=1 | Multiple deps, async processing | Comprehensive TDD |
| Batch Processing (Queue+Workers) | 4 | High | S=2,I=0,D=0,N=2,F=2,T=1 | Complex concurrency pattern (Queue, Event barrier, Sentinel shutdown) | FlowSpace reference, detailed tests |
| Template System | 2 | Small | S=1,I=0,D=0,N=1,F=0,T=1 | importlib loading | Pre-compile validation |

---

## Progress Tracking

### Phase Completion Checklist

- [x] Phase 1: Foundation & Infrastructure - COMPLETE
- [x] Phase 2: Template System - COMPLETE
- [x] Phase 3: Core Service Implementation - COMPLETE
- [ ] Phase 4: Batch Processing Engine - NOT STARTED
- [ ] Phase 5: CLI Integration & Documentation - NOT STARTED

### STOP Rule

**IMPORTANT**: This plan must be complete before creating tasks. After writing this plan:
1. Run `/plan-4-complete-the-plan` to validate readiness
2. Only proceed to `/plan-5-phase-tasks-and-brief` after validation passes

---

## Change Footnotes Ledger

[^1]: Task 1.1 - SmartContentConfig contract tests
  - `file:tests/unit/config/test_smart_content_config.py`
  - `function:tests/unit/config/test_smart_content_config.py:test_given_no_args_when_constructed_then_has_spec_defaults`
  - `function:tests/unit/config/test_smart_content_config.py:test_given_config_when_checking_path_then_returns_smart_content`
  - `function:tests/unit/config/test_smart_content_config.py:test_given_invalid_max_workers_when_constructed_then_validation_error`
  - `function:tests/unit/config/test_smart_content_config.py:test_given_yaml_when_loaded_then_uses_yaml_values`
  - `function:tests/unit/config/test_smart_content_config.py:test_given_env_var_when_loaded_then_env_overrides_yaml`
[^2]: Task 1.2 - Add SmartContentConfig to config registry
  - `class:src/fs2/config/objects.py:SmartContentConfig`
  - `file:src/fs2/config/objects.py`
[^3]: Task 1.3 - TokenCounterAdapter contract tests
  - `file:tests/unit/adapters/test_token_counter.py`
  - `class:tests/unit/adapters/test_token_counter.py:TestTokenCounterAdapterContract`
  - `class:tests/unit/adapters/test_token_counter.py:TestFakeTokenCounterAdapter`
  - `function:tests/unit/adapters/test_token_counter.py:test_given_token_counter_adapter_when_checked_then_is_abc`
  - `function:tests/unit/adapters/test_token_counter.py:test_given_fake_adapter_when_counting_then_records_call_history`
[^4]: Task 1.11 (partial) - Add TokenCounterError + translation test scaffold
  - `class:src/fs2/core/adapters/exceptions.py:TokenCounterError`
  - `file:src/fs2/core/adapters/exceptions.py`
  - `file:tests/unit/adapters/test_token_counter.py`
[^5]: Tasks 1.4–1.6 - Implement TokenCounterAdapter family + require tiktoken
  - `class:src/fs2/core/adapters/token_counter_adapter.py:TokenCounterAdapter`
  - `class:src/fs2/core/adapters/token_counter_adapter_fake.py:FakeTokenCounterAdapter`
  - `class:src/fs2/core/adapters/token_counter_adapter_tiktoken.py:TiktokenTokenCounterAdapter`
  - `file:src/fs2/core/adapters/token_counter_adapter.py`
  - `file:src/fs2/core/adapters/token_counter_adapter_fake.py`
  - `file:src/fs2/core/adapters/token_counter_adapter_tiktoken.py`
  - `file:src/fs2/core/adapters/__init__.py`
  - `file:pyproject.toml`
  - `file:uv.lock`
[^6]: Task 1.7 - Hash utility contract tests
  - `file:tests/unit/models/test_hash_utils.py`
  - `function:tests/unit/models/test_hash_utils.py:test_given_known_text_when_hashing_then_matches_sha256_hexdigest`
  - `function:tests/unit/models/test_hash_utils.py:test_given_empty_text_when_hashing_then_matches_sha256_empty`
  - `function:tests/unit/models/test_hash_utils.py:test_given_unicode_text_when_hashing_then_uses_utf8`
[^7]: Task 1.8 - Implement hash utility module
  - `function:src/fs2/core/utils/hash.py:compute_content_hash`
  - `file:src/fs2/core/utils/hash.py`
  - `file:src/fs2/core/utils/__init__.py`
[^8]: Task 1.9 - CodeNode content_hash factory test
  - `file:tests/unit/models/test_code_node.py`
  - `function:tests/unit/models/test_code_node.py:test_create_file_when_called_then_populates_content_hash`
[^9]: Task 1.10 - Add CodeNode content_hash field + factory hashing
  - `class:src/fs2/core/models/code_node.py:CodeNode`
  - `file:src/fs2/core/models/code_node.py`
  - `file:src/fs2/core/utils/hash.py`
[^10]: Follow-through - Update remaining CodeNode constructors for required content_hash
  - `file:tests/unit/services/test_get_node_service.py`
  - `file:tests/unit/repos/test_graph_store_impl.py`
[^11]: Task 1.11 - Smart content service-layer exception hierarchy
  - `file:src/fs2/core/services/smart_content/exceptions.py`
  - `file:src/fs2/core/services/smart_content/__init__.py`
  - `file:tests/unit/services/test_smart_content_exceptions.py`
  - `class:src/fs2/core/services/smart_content/exceptions.py:SmartContentError`
  - `class:src/fs2/core/services/smart_content/exceptions.py:TemplateError`
  - `class:src/fs2/core/services/smart_content/exceptions.py:SmartContentProcessingError`

[^12]: Phase 2 (setup) - Add Jinja2 dependency and package-data include rules
  - `file:pyproject.toml`
  - `file:uv.lock`

[^13]: Phase 2 (setup) - Add templates Python packages for importlib.resources
  - `file:src/fs2/core/templates/__init__.py`
  - `file:src/fs2/core/templates/smart_content/__init__.py`

[^14]: Task 2.1 - TemplateService initialization tests (RED)
  - `file:tests/unit/services/test_template_service.py`
  - `function:tests/unit/services/test_template_service.py:test_given_template_service_when_constructed_then_loads_all_required_templates`
  - `function:tests/unit/services/test_template_service.py:test_given_missing_template_when_constructed_then_raises_template_error`
  - `function:tests/unit/services/test_template_service.py:test_given_invalid_template_syntax_when_constructed_then_raises_template_error`

[^15]: Task 2.2 - Category→template mapping tests (RED)
  - `file:tests/unit/services/test_template_service.py`
  - `function:tests/unit/services/test_template_service.py:test_given_category_when_resolving_template_then_matches_ac11_mapping`
  - `function:tests/unit/services/test_template_service.py:test_given_category_when_resolving_max_tokens_then_uses_smart_content_config_defaults`

[^16]: Task 2.3 - Template rendering context tests (RED)
  - `file:tests/unit/services/test_template_service.py`
  - `function:tests/unit/services/test_template_service.py:test_given_required_context_vars_when_rendering_then_all_ac8_vars_are_supported`
  - `function:tests/unit/services/test_template_service.py:test_given_missing_required_context_var_when_rendering_then_raises_template_error`

[^17]: Task 2.5 - Implement TemplateService loader + render API
  - `file:src/fs2/core/services/smart_content/template_service.py`
  - `file:src/fs2/core/services/smart_content/__init__.py`
  - `class:src/fs2/core/services/smart_content/template_service.py:TemplateService`
  - `method:src/fs2/core/services/smart_content/template_service.py:TemplateService.resolve_template_name`
  - `method:src/fs2/core/services/smart_content/template_service.py:TemplateService.resolve_max_tokens`
  - `method:src/fs2/core/services/smart_content/template_service.py:TemplateService.render_for_category`

[^18]: Tasks 2.6–2.11 - Add Smart Content templates (`.j2`)
  - `file:src/fs2/core/templates/smart_content/smart_content_file.j2`
  - `file:src/fs2/core/templates/smart_content/smart_content_type.j2`
  - `file:src/fs2/core/templates/smart_content/smart_content_callable.j2`
  - `file:src/fs2/core/templates/smart_content/smart_content_section.j2`
  - `file:src/fs2/core/templates/smart_content/smart_content_block.j2`
  - `file:src/fs2/core/templates/smart_content/smart_content_base.j2`

[^19]: Task 2.12 - Integration test: all templates load + render
  - `file:tests/unit/services/test_template_service.py`
  - `function:tests/unit/services/test_template_service.py:test_given_all_templates_when_rendering_then_no_template_raises`

### Phase 3: Core Service Implementation

[^20]: Phase 3 T001-T006+T012 - SmartContentService tests (RED phase)
  - `file:tests/unit/services/test_smart_content_service.py`
  - 18 test cases covering: init, hash-based skip/regenerate, truncation, processing, error handling, integration

[^21]: Phase 3 T007 - SmartContentService skeleton
  - `class:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService`
  - `file:src/fs2/core/services/smart_content/__init__.py`

[^22]: Phase 3 T008 - Hash-based skip/regenerate logic
  - `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService._should_skip`
  - `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService.generate_smart_content`

[^23]: Phase 3 T009 - Content truncation implementation
  - `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService._prepare_content`

[^24]: Phase 3 T010 - Single-node processing
  - `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService._build_context`
  - `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService._is_empty_or_trivial`
  - `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService._create_placeholder_node`

[^25]: Phase 3 T011 - Error handling strategies
  - `method:src/fs2/core/services/smart_content/smart_content_service.py:SmartContentService._generate_with_error_handling`

[^26]: Phase 3 T012 - Integration and concurrency tests
  - `function:tests/unit/services/test_smart_content_service.py:test_integration_end_to_end_with_fake_llm`
  - `function:tests/unit/services/test_smart_content_service.py:test_concurrent_processing_does_not_serialize`

[^27]: Phase 3 Prerequisites - CodeNode smart_content_hash field and FakeLLMAdapter set_delay
  - `field:src/fs2/core/models/code_node.py:CodeNode.smart_content_hash`
  - `method:src/fs2/core/adapters/llm_adapter_fake.py:FakeLLMAdapter.set_delay`

---

**Plan Status**: DRAFT
**Next Step**: Run `/plan-4-complete-the-plan` to validate readiness
