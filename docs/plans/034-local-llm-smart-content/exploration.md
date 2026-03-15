# Exploration: Local LLM Smart Content Generation

> **Plan ID**: 034-local-llm-smart-content
> **Date**: 2026-03-15
> **Branch**: 031-cross-file-rels-take-2
> **Feature**: Replace heuristic smart_content with local LLM-generated summaries via Ollama

---

## Executive Summary

fs2 already has a **fully designed LLM infrastructure** (plan 007) and **smart content pipeline** (plan 008) with adapter ABCs, services, pipeline stages, and config. The SmartContentStage already delegates to SmartContentService which calls LLMAdapter.generate(). Adding local LLM support requires:

1. **One new adapter file** (`llm_adapter_local.py`) — ~150 lines
2. **Config extension** — add `"local"` to LLMConfig.provider + local fields
3. **2-line factory update** — add elif in LLMService.create()
4. **Zero stage changes** — SmartContentStage is provider-agnostic

**Estimated scope**: CS-2 (Low complexity, proven pattern from 032-local-embeddings)

---

## Research Methodology

8 parallel research subagents explored the codebase:

| Agent | Focus | Key Findings |
|-------|-------|-------------|
| Implementation Archaeologist | Existing LLM + smart content code | LLM infra exists (007), SmartContentStage works, just needs local adapter |
| Dependency Cartographer | Dependency graphs | 5 files to touch, zero new external deps needed |
| Pattern Convention Scout | 10 design patterns documented | Adapter ABC, Factory, DI, Hash-skip, Optional-dep probe |
| Quality Testing Investigator | Test patterns | FakeLLMAdapter exists, GIVEN_WHEN_THEN naming, fakes over mocks |
| Interface Contract Analyst | All interface signatures | LLMAdapter has 2 methods, LLMResponse has 6 fields |
| Documentation Evolution Historian | Plans 007, 008, 032 history | 007+008 designed not implemented, 032 is proven template |
| Prior Learnings Scout | 15 institutional learnings | Import probes, model_fields_set, two-factory gotcha, Darwin gotchas |
| Domain Boundary Scout | Architecture fit analysis | Adapter domain, config domain, no new stages needed |

---

## Benchmark Findings (Conducted This Session)

### Model Selection
- **Winner**: Qwen2.5-Coder-7B-Instruct (Q4_K_M, 4.7GB)
  - 88.4% HumanEval, 83.5% MBPP, Apache 2.0
  - No smaller dense Qwen3-Coder exists yet (only large MoE variants)

### Inference Throughput (Apple Silicon Mac)

| Metric | Ollama | llama-cpp-python |
|--------|--------|-----------------|
| Files/sec | 0.58 | 0.51 |
| Gen tok/s | 47 | 44 |
| Avg latency | 1.7s | 2.0s |
| Model load | ~3s (hot) | 11.8s |
| Quality | ✅ Identical | ✅ Identical |

### Parallelism
- Ollama serializes on single GPU (OLLAMA_NUM_PARALLEL=1 default on Mac app)
- NVIDIA with NUM_PARALLEL=4: **3.5-4x aggregate throughput**
- llama-cpp-python: no native batching (serial only)
- MLX-LM: true batching possible but Apple-only

### Scale Estimates (fs2 codebase: 5,270 nodes with content)

| Configuration | Estimated Time |
|--------------|---------------|
| Ollama serial (Mac) | ~2.5 hours |
| Ollama NUM_PARALLEL=4 (NVIDIA) | ~44 min |
| Incremental (changed nodes only) | Seconds-minutes |

**Decision**: Accept first-run penalty. Incremental updates via content_hash skip make subsequent scans fast.

---

## Existing Architecture (What Already Exists)

### LLM Adapter ABC (`src/fs2/core/adapters/llm_adapter.py`)
```python
class LLMAdapter(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    async def generate(
        self, prompt: str, *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse: ...
```

### Existing Implementations
- `llm_adapter_openai.py` — OpenAI provider
- `llm_adapter_azure.py` — Azure OpenAI (with content filter handling)
- `llm_adapter_fake.py` — Test double with set_response()/set_error()/call_history

### LLMResponse Model
```python
@dataclass(frozen=True)
class LLMResponse:
    content: str
    tokens_used: int
    model: str
    provider: str
    finish_reason: str
    was_filtered: bool = False
```

### LLMService Factory (`src/fs2/core/services/llm_service.py`)
```python
@classmethod
def create(cls, config: ConfigurationService) -> "LLMService":
    llm_config = config.require(LLMConfig)
    if llm_config.provider == "azure":
        adapter = AzureOpenAIAdapter(config)
    elif llm_config.provider == "openai":
        adapter = OpenAIAdapter(config)
    elif llm_config.provider == "fake":
        adapter = FakeLLMAdapter()
    # ADD: elif llm_config.provider == "local": ...
```

### SmartContentStage (provider-agnostic, zero changes needed)
- Merges prior smart_content via content_hash match
- Filters nodes needing generation (smart_content is None)
- Calls SmartContentService.process_batch() via asyncio.run()
- Records metrics: enriched, preserved, errors

### Pipeline Stage Order
```
Discovery → Parsing → CrossFileRels → SmartContent → Embedding → Storage
```

### Config System (LLMConfig in objects.py)
- Provider field: `Literal["azure", "openai", "fake"]` — add `"local"`
- Nested config objects for provider-specific settings
- `${ENV_VAR}` placeholder expansion for secrets
- `__config_path__ = "llm"` maps to YAML `llm:` section

---

## What Needs to Be Built

### 1. Local LLM Adapter (`llm_adapter_local.py`)
- Implements LLMAdapter ABC
- HTTP client to Ollama API (`http://localhost:11434/v1/chat/completions`)
- OpenAI-compatible API means minimal code
- Lazy HTTP client initialization (_get_client pattern)
- No API key needed (local service)

### 2. Config Extension
- Add `"local"` to LLMConfig.provider Literal
- Add local-specific fields: endpoint URL, model name
- Validator: require endpoint+model when provider="local"

### 3. Factory Wiring
- Add elif in LLMService.create() for "local" provider
- Import probe pattern (DYK-1): check Ollama reachability before returning adapter

### 4. CLI/Init Updates
- Update DEFAULT_CONFIG template in init.py with local LLM example
- Update docs/how/user/ with setup instructions
- Update MCP server help docs

### 5. Documentation
- User guide: setup Ollama, pull model, configure fs2
- Configuration guide: add local LLM section
- MCP/CLI help: ensure discoverable

---

## Prior Learnings to Apply (from 032-local-embeddings)

| ID | Learning | Application |
|----|----------|-------------|
| PL-01 | Import probe at factory time | Probe Ollama connectivity before returning adapter |
| PL-02 | model_fields_set for defaults | If auto-defaulting model name based on provider |
| PL-03 | Lazy import in adapter only | HTTP client lazy in _get_client(), not at module level |
| PL-06 | Optional dependency group | `pip install fs2[local-llm]` if we add llama-cpp-python |
| PL-07 | Default change breaks tests | Changing provider default will need test updates |
| PL-10 | No literal secrets in config | Local mode needs no API key — simpler |
| PL-11 | Status-code error translation | HTTP errors → LLMAdapterError hierarchy |
| PL-13 | ConfigurationService DI | Adapter receives config service, calls require() |
| PL-14 | Async all the way | generate() is async, SmartContentStage bridges via asyncio.run() |

---

## Design Decisions (Pre-resolved)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary backend | Ollama (OpenAI-compatible API) | Cross-platform, auto-detects GPU, no Python deps |
| Default model | qwen2.5-coder:7b | Best code quality in ≤7B class, Apache 2.0 |
| API endpoint | /v1/chat/completions | OpenAI-compatible, same HTTP pattern as existing adapters |
| First-run penalty | Accepted | ~2.5hr for 5K nodes, then incremental via hash skip |
| Separate stage? | No — reuse SmartContentStage | Stage is already provider-agnostic |
| llama-cpp-python? | Future option, not initial scope | Ollama covers all platforms; llama-cpp adds complexity |

---

## Risk Assessment

| Risk | Mitigation | Impact |
|------|-----------|--------|
| Ollama not installed | Clear error message + setup instructions in docs | Low — graceful skip |
| Model not pulled | Adapter checks model availability, suggests `ollama pull` | Low |
| Ollama service not running | Connection error → actionable error message | Low |
| Summary quality varies | Prompt engineering + temperature=0.1 for consistency | Medium |
| 2.5hr first scan | Progress bar, incremental saves, interruptible | Accepted |
| Node content too large | Existing token truncation in SmartContentService | Already handled |

---

## Recommended Next Steps

1. **plan-1b-v2-specify** — Create feature spec from this research
2. **plan-2-v2-clarify** — Resolve any open questions
3. **plan-3-v2-architect** — Implementation plan (likely 5-8 tasks)
4. **plan-6-v2-implement-phase** — Implementation (estimate: 1 day)

---

## Files Referenced

### Existing (to modify)
- `src/fs2/config/objects.py` — LLMConfig class (~L272-380)
- `src/fs2/core/services/llm_service.py` — Factory create() method
- `src/fs2/core/adapters/__init__.py` — Export new adapter
- `src/fs2/cli/init.py` — DEFAULT_CONFIG template
- `docs/how/user/configuration-guide.md` — Add local LLM section

### New (to create)
- `src/fs2/core/adapters/llm_adapter_local.py` — Ollama adapter
- `tests/unit/adapters/test_llm_adapter_local.py` — Unit tests
- `docs/how/user/local-llm.md` — User guide

### Reference (patterns to follow)
- `src/fs2/core/adapters/embedding_adapter_local.py` — Local adapter template
- `src/fs2/core/adapters/llm_adapter_openai.py` — Existing LLM adapter
- `src/fs2/core/adapters/llm_adapter_fake.py` — Test double pattern
- `tests/unit/adapters/test_embedding_adapter_local.py` — Test template
