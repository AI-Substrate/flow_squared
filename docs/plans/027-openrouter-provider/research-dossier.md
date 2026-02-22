# Research Report: OpenRouter as Endpoint Provider

**Generated**: 2026-02-22T00:00:00Z
**Research Query**: "Support OpenRouter as an endpoint provider alongside Azure and OpenAI"
**Mode**: Pre-Plan
**Location**: docs/plans/027-openrouter-provider/research-dossier.md
**FlowSpace**: Available
**Findings**: 55+ across 7 subagents

## Executive Summary

### What It Does
fs2 uses LLM and embedding adapters (behind ABC interfaces) to generate smart content summaries and semantic embeddings for code nodes. Currently supports Azure OpenAI, OpenAI direct, and Fake (test) providers. OpenRouter would add a unified gateway to 200+ models via an OpenAI-compatible API.

### Business Purpose
OpenRouter enables access to models from multiple providers (OpenAI, Anthropic, Meta, Google, Mistral, etc.) through a single API key and endpoint, without needing separate accounts per provider. This dramatically lowers the barrier to entry and gives users model flexibility.

### Key Insights
1. **OpenRouter is a drop-in for the OpenAI SDK** — uses `AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)`. The existing `OpenAIAdapter` pattern works almost identically.
2. **OpenRouter does NOT support embeddings** — only chat completions. Embedding must remain on Azure/OpenAI/local.
3. **The codebase already has a documented extension guide** (`docs/how/dev/llm-adapter-extension.md`) with step-by-step instructions for adding new providers.
4. **Model naming is namespaced** — OpenRouter uses `provider/model` format (e.g., `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`), unlike OpenAI's simple `gpt-4`.

### Quick Stats
- **Components to modify**: ~8 files
- **New files**: 2 (adapter + tests)
- **Dependencies**: 0 new (reuses `openai` SDK already in pyproject.toml)
- **Test Coverage**: 86 existing adapter tests provide template
- **Prior Learnings**: 15 relevant discoveries from plans 007, 009, 024, 025
- **Complexity**: Low-Medium (OpenAI-compatible, well-paved path)

---

## How It Currently Works

### Entry Points
| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `fs2 scan --smart-content` | CLI | `src/fs2/cli/scan.py:486-577` | Creates LLM adapter for smart content generation |
| `fs2 scan --embed` | CLI | `src/fs2/cli/scan.py:570` | Creates embedding adapter via `EmbeddingService.create()` |
| `LLMService.create()` | Factory | `src/fs2/core/services/llm_service.py:58-83` | Provider selection and adapter instantiation |
| `create_embedding_adapter_from_config()` | Factory | `src/fs2/core/adapters/embedding_adapter.py:106-147` | Embedding provider selection |

### Core Execution Flow

1. **Config Loading**: `ConfigurationService` merges YAML + env vars + defaults → `LLMConfig`
2. **Provider Selection**: `LLMService.create(config)` reads `llm_config.provider` literal
3. **Adapter Instantiation**: Factory `if/elif` creates the correct adapter class
4. **Client Creation**: Adapter lazily creates `AsyncOpenAI` or `AsyncAzureOpenAI` via `_get_client()`
5. **API Call**: `adapter.generate(prompt)` calls OpenAI SDK's `chat.completions.create()`
6. **Error Translation**: SDK exceptions translated to domain exceptions via HTTP status codes
7. **Response**: Returns frozen `LLMResponse(content, tokens_used, model, provider, finish_reason, was_filtered)`

### Provider Selection Factory (LLM)
```python
# src/fs2/core/services/llm_service.py:58-83
if llm_config.provider == "azure":
    adapter = AzureOpenAIAdapter(config)
elif llm_config.provider == "openai":
    adapter = OpenAIAdapter(config)
elif llm_config.provider == "fake":
    adapter = FakeLLMAdapter()
```

### Provider Selection Factory (Embedding)
```python
# src/fs2/core/adapters/embedding_adapter.py:106-147
if embedding_config.mode == "azure":
    return AzureEmbeddingAdapter(config)
elif embedding_config.mode == "fake":
    return FakeEmbeddingAdapter(dimensions=embedding_config.dimensions)
elif embedding_config.mode == "openai_compatible":
    raise ValueError("openai_compatible embeddings require explicit api_key/base_url/model")
```

### Data Flow
```
User Config (YAML/env) → ConfigurationService → LLMConfig
    → LLMService.create() → OpenAIAdapter/AzureOpenAIAdapter
        → AsyncOpenAI SDK → Provider API
            → LLMResponse (frozen dataclass)
                → SmartContentService → CodeNode.smart_content
```

---

## Architecture & Design

### Component Map

#### LLM Adapter Layer
- **LLMAdapter ABC** (`src/fs2/core/adapters/llm_adapter.py:22-89`): `provider_name` property + `async generate()` method
- **OpenAIAdapter** (`src/fs2/core/adapters/llm_adapter_openai.py:33-201`): Direct OpenAI API
- **AzureOpenAIAdapter** (`src/fs2/core/adapters/llm_adapter_azure.py:33-243`): Azure OpenAI with AD fallback
- **FakeLLMAdapter** (`src/fs2/core/adapters/llm_adapter_fake.py`): Test double with fixture support

#### Embedding Adapter Layer
- **EmbeddingAdapter ABC** (`src/fs2/core/adapters/embedding_adapter.py:20-103`): `embed_text()` + `embed_batch()`
- **AzureEmbeddingAdapter** (`src/fs2/core/adapters/embedding_adapter_azure.py:30-213`)
- **OpenAICompatibleEmbeddingAdapter** (`src/fs2/core/adapters/embedding_adapter_openai.py:28-224`)
- **FakeEmbeddingAdapter** (`src/fs2/core/adapters/embedding_adapter_fake.py`)

#### Configuration
- **LLMConfig** (`src/fs2/config/objects.py:265-382`): `provider: Literal["azure", "openai", "fake"]`
- **EmbeddingConfig** (`src/fs2/config/objects.py:545-675`): `mode: Literal["azure", "openai_compatible", "fake"]`

### Design Patterns Identified

1. **ABC with Abstract Properties**: All adapters define `provider_name` property + async methods
2. **ConfigurationService Injection**: Adapters receive registry, extract own config internally
3. **Lazy Client Initialization**: `_get_client()` creates SDK client on first use
4. **Status-Code Error Translation**: `getattr(e, 'status_code', None)` → domain exceptions
5. **Exponential Backoff with Jitter**: `delay = base * (2^attempt) + random.uniform(0, 1)`
6. **Fakes over Mocks**: Real ABC implementations with `set_response()`/`set_error()`/`call_history`
7. **Frozen Dataclasses**: `LLMResponse` is immutable, updated via `dataclasses.replace()`

### System Boundaries
- **Internal**: Adapters sit between services and external SDKs
- **External**: OpenAI Python SDK (`openai>=1.0.0`) is the only HTTP client
- **Import Boundary**: SDK types NEVER leak into services layer (enforced by `test_import_boundaries.py`)

---

## Dependencies & Integration

### External SDK Dependencies (pyproject.toml)
| Library | Version | Purpose | Used By |
|---------|---------|---------|---------|
| `openai` | `>=1.0.0` | OpenAI + Azure SDK | Both LLM adapters |
| `azure-identity` | `>=1.18.0,<2` | Azure AD auth (optional) | AzureOpenAIAdapter |
| `pydantic` | `>=2.0` | Config validation | All config objects |
| `tiktoken` | `>=0.7.0` | Token counting | LLM/embedding truncation |

### What Depends on LLM Adapters
- `LLMService` → composes adapter via factory
- `SmartContentService` → uses LLMService for code summaries
- `fs2 scan --smart-content` → CLI entry point
- `fs2 doctor` → provider health check

### OpenRouter: No New Dependencies Needed
OpenRouter is OpenAI-compatible. The existing `openai>=1.0.0` SDK works with `base_url="https://openrouter.ai/api/v1"`.

---

## Quality & Testing

### Current Test Coverage
- **86 dedicated adapter tests** across LLM and embedding
- **Unit tests**: ABC enforcement, async signatures, config validation, error translation, retry logic
- **Integration tests**: Full pipeline with FakeAdapters (no real API calls in CI)
- **Import boundary tests**: AST-based static analysis prevents SDK leakage

### Test Patterns for New Provider
- Copy `test_llm_adapter_openai.py` structure (12 tests)
- Use `unittest.mock.AsyncMock` + `patch` for SDK calls
- Reuse `FakeLLMAdapter` for integration tests (provider-agnostic)
- Add OpenRouter to import boundary checks

### Key Test Files
| File | Tests | Purpose |
|------|-------|---------|
| `tests/unit/adapters/test_llm_adapter_openai.py` | 12 | Template for OpenRouter tests |
| `tests/unit/adapters/test_llm_adapter_azure.py` | 12+ | Azure-specific patterns |
| `tests/unit/adapters/test_llm_adapter_fake.py` | 12 | Fake double tests |
| `tests/unit/adapters/test_import_boundaries.py` | 7+ | SDK isolation enforcement |
| `tests/unit/config/test_embedding_config.py` | 44 | Config validation patterns |

---

## Modification Considerations

### Safe to Modify
1. **`LLMConfig.provider` Literal type** — Add `"openrouter"` to the union
2. **`LLMService.create()` factory** — Add `elif` branch for OpenRouter
3. **`adapters/__init__.py`** — Export new adapter class
4. **Config examples** — Add OpenRouter YAML section

### Modify with Caution
1. **`LLMConfig` validators** — API key validation rules differ per provider
2. **`scan.py` CLI integration** — SmartContent setup has its own provider switch

### Extension Points (Designed for This)
1. **`docs/how/dev/llm-adapter-extension.md`** — 260-line guide for adding providers
2. **ABC interface** — Implement `provider_name` + `generate()`, done
3. **Factory pattern** — Single `elif` addition

---

## Prior Learnings (From Previous Implementations)

### PL-01: Two-Layer API Key Security
**Source**: Plan 007 (LLMService)
**Learning**: Pydantic validators reject literal `sk-` keys; adapters reject empty/unexpanded placeholders at init.
**Action**: OpenRouter keys may use `sk-or-...` prefix. Update validator to handle OpenRouter format while still enforcing `${ENV_VAR}` placeholders.

### PL-02: ConfigurationService Injection is Mandatory
**Source**: Plan 007
**Learning**: Adapters receive `ConfigurationService`, NOT extracted config. Call `config.require(LLMConfig)` internally.
**Action**: Follow exact pattern from `OpenAIAdapter.__init__()`.

### PL-03: Status-Code Error Translation (No SDK Imports)
**Source**: Plan 007
**Learning**: Use `getattr(e, 'status_code', None)` — never import SDK exception types.
**Action**: Same pattern works for OpenRouter since it uses the OpenAI SDK.

### PL-04: Exponential Backoff Formula
**Source**: Plans 007 + 009
**Learning**: `delay = base * (2^attempt) + jitter`, cap at 60s.
**Action**: Implement identical retry logic to OpenAIAdapter.

### PL-05: Empty Secrets Create Silent Auth Failures
**Source**: Plan 007
**Learning**: Empty string API keys pass Pydantic but fail at runtime with cryptic 401.
**Action**: Validate `if not api_key.strip()` at adapter init, raise clear error.

### PL-08: Provider-Specific Config Fields Need Cross-Validation
**Source**: Plan 007
**Learning**: Azure needs `base_url`, `deployment_name`, `api_version` validated together.
**Action**: OpenRouter needs `api_key` and `model` (with namespaced format). Add validator: if `provider="openrouter"`, require `api_key` and `model`.

### PL-12: Optional Dependencies Must Be Lazy-Imported
**Source**: Plan 024
**Learning**: `azure-identity` is optional, lazy-imported with clear error on missing.
**Action**: OpenRouter needs NO extra dependencies (uses `openai` SDK). No action needed.

### PL-13: OpenAI-Compatible Reuse vs. Separate Adapter
**Source**: Plan 009
**Learning**: OpenAI-compatible providers can reuse `OpenAIAdapter` pattern.
**Action**: **Decide**: Extend `OpenAIAdapter` with different `provider_name` and `base_url`, OR create separate `OpenRouterAdapter` for clarity. Separate adapter recommended for:
  - Clear provider identification in logs/responses
  - OpenRouter-specific header support (`HTTP-Referer`, `X-Title`)
  - Future OpenRouter-specific features (cost tracking, model routing)

### PL-14: Model Names Must Be Configurable
**Source**: Plans 007 + 025
**Learning**: `model` field is used differently per provider (Azure=deployment, OpenAI=model name).
**Action**: OpenRouter uses `model` parameter directly in API calls with namespaced format `provider/model-name`.

### Prior Learnings Summary

| ID | Type | Source Plan | Key Insight | Action |
|----|------|-------------|-------------|--------|
| PL-01 | security | 007 | Two-layer API key validation | Adapt validator for OpenRouter format |
| PL-02 | pattern | 007 | ConfigurationService injection | Use exact same pattern |
| PL-03 | pattern | 007 | Status-code error translation | Same pattern works |
| PL-04 | resilience | 007+009 | Exponential backoff formula | Implement identically |
| PL-05 | gotcha | 007 | Empty secrets = silent 401 | Validate at init |
| PL-08 | config | 007 | Cross-field validation | Validate api_key + model for OpenRouter |
| PL-12 | dependency | 024 | Lazy imports for optional deps | Not needed (uses openai SDK) |
| PL-13 | decision | 009 | Reuse vs. separate adapter | Separate adapter recommended |
| PL-14 | config | 007+025 | Model name configurability | Use namespaced model format |

---

## Critical Discoveries

### Discovery 01: OpenRouter is Fully OpenAI SDK Compatible
**Impact**: Critical (simplifies implementation)
**Source**: IA-08, DC-05, External Research
**What**: OpenRouter works as a drop-in with `AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)`. Same request/response schema as OpenAI.
**Why It Matters**: No new SDK dependency. No protocol translation. Minimal adapter code.

### Discovery 02: OpenRouter Does NOT Support Embeddings
**Impact**: Critical (scoping)
**Source**: External Research (OpenRouter docs)
**What**: OpenRouter only provides chat completions, NOT `/embeddings` endpoint. Users must use Azure/OpenAI/local for embeddings.
**Why It Matters**: OpenRouter integration is **LLM-only**. No `EmbeddingAdapter` needed. Configuration must make this clear.

### Discovery 03: Model Naming is Namespaced
**Impact**: High (config validation)
**Source**: External Research
**What**: OpenRouter models use `provider/model-name` format (e.g., `openai/gpt-4o`, `anthropic/claude-3.5-sonnet`). Not just `gpt-4`.
**Why It Matters**: The `model` field in `LLMConfig` must accept slash-separated names. Current validation may not expect this format. Consider adding a validator hint or documentation.

### Discovery 04: Optional OpenRouter-Specific Headers
**Impact**: Medium (nice-to-have)
**Source**: External Research
**What**: OpenRouter accepts optional headers: `HTTP-Referer` (your site URL) and `X-Title` (your app name) for ranking on openrouter.ai/rankings.
**Why It Matters**: Could be useful for tracking/attribution but not required. Can be added later.

### Discovery 05: Existing Extension Guide Documents the Exact Steps
**Impact**: High (implementation clarity)
**Source**: DE-08
**What**: `docs/how/dev/llm-adapter-extension.md` (260 lines) provides step-by-step instructions for adding a new LLM provider.
**Why It Matters**: The path is well-documented. Follow the guide exactly.

---

## OpenRouter Integration Plan (High-Level)

### New Files
1. `src/fs2/core/adapters/llm_adapter_openrouter.py` — OpenRouter LLM adapter
2. `tests/unit/adapters/test_llm_adapter_openrouter.py` — Unit tests

### Modified Files
3. `src/fs2/config/objects.py` — Add `"openrouter"` to `LLMConfig.provider` Literal + validation
4. `src/fs2/core/services/llm_service.py` — Add `elif "openrouter"` in factory
5. `src/fs2/core/adapters/__init__.py` — Export `OpenRouterAdapter`
6. `src/fs2/cli/scan.py` — Add OpenRouter to SmartContent setup (if separate from LLMService factory)
7. `src/fs2/docs/config.yaml.example` — Add OpenRouter config section
8. `docs/how/user/configuration-guide.md` — Document OpenRouter setup

### NOT Needed
- No new embedding adapter (OpenRouter doesn't support embeddings)
- No new SDK dependency (reuses `openai>=1.0.0`)
- No new exception types (reuses existing LLM error hierarchy)
- No new fake adapter (reuses `FakeLLMAdapter`)

### Provider Support Matrix (After Implementation)

| Feature | Azure | OpenAI | OpenRouter | Fake |
|---------|-------|--------|------------|------|
| LLM (chat completions) | Yes | Yes | **Yes** | Yes |
| Embeddings | Yes | Yes (openai_compatible) | **No** | Yes |
| Auth Method | API key + Azure AD | API key | API key | None |
| Model Format | Deployment name | `gpt-4` | `provider/model` | N/A |
| Content Filter | Yes (graceful) | No | No | No |
| SDK | `openai` | `openai` | `openai` | None |

---

## External Research Opportunities

### Research Opportunity 1: OpenRouter Rate Limits and Pricing API

**Why Needed**: OpenRouter aggregates many providers with different rate limits per model. Understanding their rate limit headers (`x-ratelimit-*`) could enable smarter backoff.
**Impact on Plan**: Low — current exponential backoff works fine, but could be optimized.
**Source Findings**: IA-07, PL-04

**Ready-to-use prompt:**
```
/deepresearch "OpenRouter API rate limiting: What rate limit headers does OpenRouter return? How do rate limits vary per model? Is there a /api/v1/models endpoint that includes rate limit info? How should a client implement intelligent rate limiting when using OpenRouter as a proxy to multiple providers?"
```

**Results location**: Save to `docs/plans/027-openrouter-provider/external-research/openrouter-rate-limits.md`

### Research Opportunity 2: OpenRouter Cost Tracking and Response Metadata

**Why Needed**: OpenRouter returns cost info in responses. Current `LLMResponse` doesn't track cost. Could be valuable for users.
**Impact on Plan**: Low — nice-to-have, not blocking.
**Source Findings**: IA-10

**Ready-to-use prompt:**
```
/deepresearch "OpenRouter response metadata: What additional fields does OpenRouter include in chat completion responses beyond standard OpenAI format? Specifically: cost tracking (x-total-tokens header, usage.cost field), model routing metadata, and any provider-specific response extensions."
```

**Results location**: Save to `docs/plans/027-openrouter-provider/external-research/openrouter-response-metadata.md`

---

## Appendix: File Inventory

### Core Files to Modify/Create
| File | Purpose | Action |
|------|---------|--------|
| `src/fs2/core/adapters/llm_adapter_openrouter.py` | OpenRouter adapter | **CREATE** |
| `src/fs2/config/objects.py` | LLMConfig provider literal | MODIFY |
| `src/fs2/core/services/llm_service.py` | Factory pattern | MODIFY |
| `src/fs2/core/adapters/__init__.py` | Export | MODIFY |
| `src/fs2/cli/scan.py` | CLI integration | MODIFY |
| `src/fs2/docs/config.yaml.example` | Config example | MODIFY |
| `docs/how/user/configuration-guide.md` | User docs | MODIFY |
| `tests/unit/adapters/test_llm_adapter_openrouter.py` | Tests | **CREATE** |

### Reference Files (Read-Only)
| File | Purpose |
|------|---------|
| `src/fs2/core/adapters/llm_adapter.py` | ABC interface to implement |
| `src/fs2/core/adapters/llm_adapter_openai.py` | Template to follow |
| `src/fs2/core/adapters/exceptions.py` | Error hierarchy to reuse |
| `src/fs2/core/models/llm_response.py` | Response model |
| `docs/how/dev/llm-adapter-extension.md` | Extension guide |
| `tests/unit/adapters/test_llm_adapter_openai.py` | Test template |

---

## Next Steps

**Recommended path:**
1. Run `/plan-1b-specify "Add OpenRouter as LLM endpoint provider"` to create the specification
2. Skip external research (rate limits/cost tracking are nice-to-have, not blocking)
3. Implementation is straightforward — ~Low-Medium complexity

**Key design decision to resolve in spec:**
- **Separate `OpenRouterAdapter` vs. reusing `OpenAIAdapter` with different config** — Recommend separate adapter for clarity and future extensibility (OpenRouter-specific headers, cost tracking).

---

**Research Complete**: 2026-02-22
**Report Location**: docs/plans/027-openrouter-provider/research-dossier.md
