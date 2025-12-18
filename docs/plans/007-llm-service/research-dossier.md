# Research Report: LLMService with OpenAI/Azure Adapters

**Generated**: 2025-12-17T12:00:00Z
**Research Query**: "Adding LLMService that wraps adapters (AzureOpenAIAdapter, OpenAIAdapter) with configuration for API keys, endpoints"
**Mode**: Plan-Associated
**Location**: `docs/plans/007-llm-service/research-dossier.md`
**FlowSpace**: Available (flowspace repo indexed with 6,282 nodes)
**Findings**: 60 findings across 6 research dimensions

## Executive Summary

### What We're Building
An LLMService for fs2 that provides provider-agnostic access to large language models (OpenAI, Azure OpenAI) following Clean Architecture principles. The service will wrap provider-specific adapters and handle configuration, secrets, retry logic, and error translation.

### Business Purpose
Enable "smart content" generation (semantic summaries, embeddings) for code units in the fs2 codebase analysis system, supporting the FlowSpace code intelligence features.

### Key Insights
1. **Flowspace uses Repository pattern** for LLM providers—these function as adapters wrapping external SDKs with a consistent `ILlmRepository` interface
2. **fs2 has established adapter patterns** with ABC interfaces, ConfigurationService DI, and "fakes over mocks" testing philosophy
3. **Two-layer security model** required: Pydantic validators reject literal API keys at config time; environment variable expansion happens only at runtime

### Quick Stats
- **Source Components**: 15+ files in flowspace LLM module
- **Target Location**: `src/fs2/core/adapters/llm_adapter*.py`, `src/fs2/core/services/llm_service.py`
- **Dependencies**: `openai` package (AsyncOpenAI, AsyncAzureOpenAI clients)
- **Configuration**: 8-10 new config fields across provider configs
- **Test Coverage**: Fake adapter + unit tests following established patterns

---

## How It Currently Works (in Flowspace)

### Entry Points

| Entry Point | Type | Location | Purpose |
|------------|------|----------|---------|
| `LLMService.create_from_registry()` | Factory | `src/modules/llm/service.py:151` | Create service from ConfigRegistry |
| `LLMService.generate_smart_content_with_relationships()` | API | `src/modules/llm/service.py` | Main public method |
| `ILlmRepository.generate_smart_content()` | Interface | `src/modules/llm/interfaces.py` | Provider contract |

### Core Execution Flow

1. **Service Creation** via factory method
   - `LLMService.create_from_registry()` reads LLM config from ConfigRegistry
   - Calls `expand_env_vars_safely()` to resolve `${VAR}` placeholders
   - Validates provider-specific requirements
   - Creates appropriate repository (adapter) based on `config.provider`

2. **Repository Selection** in `_create_repository()`
   ```python
   if config.provider == "openai":
       return OpenAIRepository(config, templating_service, logger)
   elif config.provider == "azure":
       return AzureOpenAIRepository(config, templating_service, logger)
   elif config.provider == "ollama":
       return OllamaRepository(config, templating_service, logger)
   else:
       return MockLLMRepository(config, templating_service, logger)
   ```

3. **Content Generation** via repository
   - Service calls `repository.generate_smart_content(code_unit, system_prompt, max_tokens)`
   - Repository handles SDK client creation, API calls, retry logic
   - Returns `SmartContentResponse` with content, token count, model, provider

### Data Flow

```
┌─────────────────────┐
│  SmartContentService │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│     LLMService      │ ← Factory creates from ConfigRegistry
│  (Orchestrator)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   ILlmRepository    │ ← ABC Interface
│   (Provider ABC)    │
└──────────┬──────────┘
           │
     ┌─────┴─────┬─────────────┐
     ▼           ▼             ▼
┌─────────┐ ┌─────────┐ ┌───────────┐
│ OpenAI  │ │  Azure  │ │  Ollama   │
│  Repo   │ │  Repo   │ │   Repo    │
└────┬────┘ └────┬────┘ └─────┬─────┘
     │           │             │
     ▼           ▼             ▼
┌─────────┐ ┌─────────┐ ┌───────────┐
│AsyncOpen│ │AsyncAzure│ │  HTTP    │
│   AI    │ │ OpenAI  │ │  Client   │
└─────────┘ └─────────┘ └───────────┘
```

---

## Architecture & Design

### Component Map

#### From Flowspace (Source Patterns)

| Component | Location | Purpose |
|-----------|----------|---------|
| `LLMService` | `src/modules/llm/service.py` | Orchestrator/factory |
| `ILlmRepository` | `src/modules/llm/interfaces.py` | Provider ABC |
| `BaseLlmRepository` | `src/modules/llm/repositories/base.py` | Shared retry logic |
| `OpenAIRepository` | `src/modules/llm/repositories/openai_repository.py` | OpenAI adapter |
| `AzureOpenAIRepository` | `src/modules/llm/repositories/azure_repository.py` | Azure adapter |
| `MockLLMRepository` | `src/modules/llm/repositories/mock_repository.py` | Test fake |
| `LlmConfig` | `src/modules/config/models.py` | Configuration model |
| `SmartContentResponse` | `src/modules/llm/models.py` | Response model |

#### Target Structure for fs2

```
src/fs2/
├── config/
│   └── objects.py              # Add: LLMAdapterConfig, AzureOpenAIConfig, OpenAIConfig
├── core/
│   ├── adapters/
│   │   ├── llm_adapter.py          # NEW: LLMAdapter ABC
│   │   ├── llm_adapter_openai.py   # NEW: OpenAI implementation
│   │   ├── llm_adapter_azure.py    # NEW: Azure implementation
│   │   ├── llm_adapter_fake.py     # NEW: Test fake
│   │   └── exceptions.py           # Add: LLMAdapterError subclass
│   ├── models/
│   │   └── llm_response.py         # NEW: LLMResponse dataclass
│   └── services/
│       └── llm_service.py          # NEW: LLMService composition
```

### Design Patterns Identified

#### 1. Repository/Adapter Pattern (from Flowspace)
Flowspace calls these "repositories" but they function as **adapters**:
- Wrap external SDKs (openai, azure-openai)
- Implement consistent interface (`ILlmRepository`)
- Translate SDK exceptions to domain exceptions
- Handle retry logic internally

#### 2. Factory Pattern for Provider Selection
```python
def _create_repository(self) -> ILlmRepository:
    match self.config.provider:
        case "openai": return OpenAIRepository(...)
        case "azure": return AzureOpenAIRepository(...)
        case _: raise NotImplementedError(...)
```

#### 3. Two-Layer Security Model
- **Layer 1 (Config Time)**: Pydantic validators reject literal secrets
- **Layer 2 (Runtime)**: `expand_env_vars_safely()` resolves `${VAR}` placeholders

#### 4. Exponential Backoff Retry
```python
for attempt in range(max_retries):
    try:
        return await api_call()
    except RateLimitError:
        wait = (2 ** attempt) + random.uniform(0, 1)
        await asyncio.sleep(wait)
```

---

## Dependencies & Integration

### What LLMService Will Depend On

#### Internal Dependencies (fs2)

| Dependency | Type | Purpose |
|------------|------|---------|
| `ConfigurationService` | Required | Registry for config injection |
| `LLMAdapter` (ABC) | Required | Provider abstraction |
| `LogAdapter` | Optional | Structured logging |
| `LLMResponse` | Required | Response model |

#### External Dependencies

| Package | Version | Purpose | Installation |
|---------|---------|---------|--------------|
| `openai` | `>=1.0.0` | AsyncOpenAI, AsyncAzureOpenAI clients | `pip install openai` |
| `tenacity` | `>=8.0.0` | Retry logic (optional, can implement manually) | `pip install tenacity` |

### What Will Depend on LLMService

| Consumer | Purpose |
|----------|---------|
| SmartContentService (future) | Generate semantic summaries |
| EmbeddingService (future) | Generate vector embeddings |
| CLI commands (future) | Direct LLM interaction |

---

## Configuration Requirements

### Environment Variables

| Variable | Provider | Purpose | Example |
|----------|----------|---------|---------|
| `FS2_LLM__PROVIDER` | All | Provider selection | `openai`, `azure`, `mock` |
| `OPENAI_API_KEY` | OpenAI | API authentication | `sk-...` |
| `AZURE_OPENAI_API_KEY` | Azure | API authentication | `abc123...` |
| `AZURE_OPENAI_ENDPOINT` | Azure | Service endpoint | `https://myinstance.openai.azure.com` |
| `AZURE_OPENAI_DEPLOYMENT` | Azure | Deployment name | `gpt-4-deployment` |

### Configuration Classes (to create in `objects.py`)

```python
class LLMAdapterConfig(BaseModel):
    """Base LLM adapter configuration."""
    __config_path__: ClassVar[str] = "llm.adapter"

    provider: Literal["openai", "azure", "mock"] = "mock"
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 800
    timeout: int = 30
    max_retries: int = 3


class OpenAIConfig(BaseModel):
    """OpenAI-specific configuration."""
    __config_path__: ClassVar[str] = "llm.openai"

    api_key: str | None = None  # Must use ${OPENAI_API_KEY}

    @field_validator("api_key")
    @classmethod
    def validate_no_literal_secret(cls, v: str | None) -> str | None:
        if v and not v.startswith("${") and len(v) > 10:
            raise ValueError("API key must use ${ENV_VAR} syntax")
        return v


class AzureOpenAIConfig(BaseModel):
    """Azure OpenAI-specific configuration."""
    __config_path__: ClassVar[str] = "llm.azure"

    api_key: str | None = None  # Must use ${AZURE_OPENAI_API_KEY}
    endpoint: str | None = None
    deployment_name: str | None = None
    api_version: str = "2024-02-01"

    @field_validator("api_key")
    @classmethod
    def validate_no_literal_secret(cls, v: str | None) -> str | None:
        if v and not v.startswith("${") and len(v) > 10:
            raise ValueError("API key must use ${ENV_VAR} syntax")
        return v
```

### YAML Configuration Example

```yaml
# .fs2/config.yaml
llm:
  adapter:
    provider: azure  # or "openai", "mock"
    model: gpt-4
    temperature: 0.7
    max_tokens: 800
    timeout: 30
    max_retries: 3

  openai:
    api_key: ${OPENAI_API_KEY}

  azure:
    api_key: ${AZURE_OPENAI_API_KEY}
    endpoint: ${AZURE_OPENAI_ENDPOINT}
    deployment_name: ${AZURE_OPENAI_DEPLOYMENT}
    api_version: "2024-02-01"
```

### Secrets File Example

```bash
# .fs2/secrets.env (gitignored)
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx
AZURE_OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
AZURE_OPENAI_ENDPOINT=https://myinstance.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4-deployment
```

---

## Interface Contracts

### LLMAdapter ABC (to create)

```python
from abc import ABC, abstractmethod
from fs2.core.models.llm_response import LLMResponse

class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Generate completion from the LLM provider.

        Args:
            prompt: User prompt/content to send
            system_prompt: Optional system instructions
            max_tokens: Optional token limit override

        Returns:
            LLMResponse with content, token count, model info

        Raises:
            LLMAdapterError: On provider errors (auth, rate limit, etc.)
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier (e.g., 'openai', 'azure')."""
        ...
```

### LLMResponse Model (to create)

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class LLMResponse:
    """Response from LLM provider."""
    content: str
    tokens_used: int
    model: str
    provider: str
    finish_reason: str = "stop"
    was_filtered: bool = False
```

### Exception Hierarchy (add to `exceptions.py`)

```python
class LLMAdapterError(AdapterError):
    """Base error for LLM adapter failures."""
    pass

class LLMAuthenticationError(LLMAdapterError):
    """Invalid or expired API credentials."""
    pass

class LLMRateLimitError(LLMAdapterError):
    """Rate limit exceeded - retry with backoff."""
    pass

class LLMContentFilterError(LLMAdapterError):
    """Content blocked by provider safety filters."""
    pass
```

---

## Quality & Testing

### Testing Strategy

Following fs2's "fakes over mocks" philosophy:

1. **FakeLLMAdapter** - Real implementation of ABC for testing
   - Configurable responses via `set_response()` method
   - Call history tracking for assertions
   - Error simulation via config

2. **Unit Tests** - Test adapter and service in isolation
   - Use `FakeConfigurationService` for config injection
   - Use `FakeLLMAdapter` for service tests
   - No external API calls in unit tests

3. **Integration Tests** (optional) - Real API calls
   - Marked with `@pytest.mark.integration`
   - Skipped in CI without API keys
   - Manual verification only

### Test File Structure

```
tests/
├── unit/
│   ├── adapters/
│   │   ├── test_llm_adapter_fake.py      # Test fake behavior
│   │   ├── test_llm_adapter_openai.py    # Test with mocked SDK
│   │   └── test_llm_adapter_azure.py     # Test with mocked SDK
│   └── services/
│       └── test_llm_service.py           # Test with fake adapter
└── integration/
    └── test_llm_real_api.py              # Real API tests (manual)
```

### FakeLLMAdapter Pattern

```python
class FakeLLMAdapter(LLMAdapter):
    """Test fake for LLM adapter."""

    def __init__(self, config: "ConfigurationService"):
        self._config = config.require(LLMAdapterConfig)
        self._call_history: list[dict] = []
        self._response: LLMResponse | None = None
        self._error: Exception | None = None

    def set_response(self, response: LLMResponse) -> None:
        """Configure the response to return."""
        self._response = response

    def set_error(self, error: Exception) -> None:
        """Configure an error to raise."""
        self._error = error

    @property
    def call_history(self) -> list[dict]:
        """Get recorded calls for assertions."""
        return self._call_history

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self._call_history.append({
            "method": "generate",
            "prompt": prompt,
            "system_prompt": system_prompt,
            "max_tokens": max_tokens,
        })

        if self._error:
            raise self._error

        if self._response:
            return self._response

        # Default response
        return LLMResponse(
            content=f"Mock response for: {prompt[:50]}...",
            tokens_used=42,
            model=self._config.model,
            provider="mock",
        )

    @property
    def provider_name(self) -> str:
        return "mock"
```

---

## Modification Considerations

### Safe to Modify
- `src/fs2/config/objects.py` - Add new config classes
- `src/fs2/core/adapters/exceptions.py` - Add LLM exception subclasses
- `src/fs2/core/adapters/__init__.py` - Export new adapters

### Modify with Caution
- `ConfigurationService` - If adding new loading logic
- `YAML_CONFIG_TYPES` registry - Order matters for loading

### Danger Zones
- Existing adapter patterns - Must follow established conventions exactly
- Environment variable expansion - Security-critical code path

### Extension Points
1. **New providers** - Add new `llm_adapter_{provider}.py` files
2. **New response fields** - Extend `LLMResponse` dataclass
3. **New config options** - Add to config classes with validators

---

## Critical Discoveries

### Critical Finding 01: Two-Layer Security Model Required
**Impact**: Critical
**Source**: PS-05, QT-05, IA-03
**What**: API keys must NEVER be stored as literals in config files. Use `${ENV_VAR}` placeholders that are expanded at runtime only.
**Why It Matters**: Prevents accidental secret exposure in git commits
**Required Action**: Implement field validators that reject literal secrets + runtime expansion

### Critical Finding 02: ConfigurationService DI Pattern
**Impact**: Critical
**Source**: DC-05, DC-06, DE-05
**What**: Adapters receive `ConfigurationService` (the registry), NOT extracted config objects. Adapters call `config.require(ConfigType)` internally.
**Why It Matters**: Violating this causes "concept leakage" from composition root to adapters
**Required Action**: Follow exact DI pattern from existing fs2 adapters

### Critical Finding 03: Async-First Design
**Impact**: High
**Source**: IA-04, IA-05, IC-02
**What**: Flowspace uses `AsyncOpenAI` and `AsyncAzureOpenAI` clients with async/await throughout
**Why It Matters**: LLM calls are I/O bound; blocking would hurt performance
**Required Action**: Design adapter interface with async methods

### Critical Finding 04: Azure Content Filter Handling
**Impact**: High
**Source**: IA-05, IC-07
**What**: Azure OpenAI may reject requests due to content filters, returning specific error codes
**Why It Matters**: Must handle gracefully without crashing
**Required Action**: Catch `BadRequestError` with content filter indicators, return fallback response with `was_filtered=True`

### Critical Finding 05: Exponential Backoff Required
**Impact**: High
**Source**: IA-06, IC-07
**What**: Rate limit (429) and server errors (502, 503) need exponential backoff with jitter
**Why It Matters**: Prevents thundering herd; respects API limits
**Required Action**: Implement retry logic with `delay = base * (2^attempt) + random()`

---

## Implementation Checklist

### Phase 1: Configuration
- [ ] Add `LLMAdapterConfig` to `objects.py`
- [ ] Add `OpenAIConfig` to `objects.py`
- [ ] Add `AzureOpenAIConfig` to `objects.py`
- [ ] Add configs to `YAML_CONFIG_TYPES` registry
- [ ] Create `.fs2/secrets.env.example` with placeholder variables
- [ ] Update `.fs2/config.yaml.example` with LLM section

### Phase 2: Models & Exceptions
- [ ] Create `src/fs2/core/models/llm_response.py` with `LLMResponse` dataclass
- [ ] Add `LLMAdapterError` hierarchy to `exceptions.py`

### Phase 3: Adapter ABC
- [ ] Create `src/fs2/core/adapters/llm_adapter.py` with ABC
- [ ] Define `generate()` async method signature
- [ ] Define `provider_name` property

### Phase 4: Fake Adapter
- [ ] Create `src/fs2/core/adapters/llm_adapter_fake.py`
- [ ] Implement call history tracking
- [ ] Implement configurable responses
- [ ] Implement error simulation

### Phase 5: OpenAI Adapter
- [ ] Create `src/fs2/core/adapters/llm_adapter_openai.py`
- [ ] Implement `AsyncOpenAI` client initialization
- [ ] Implement retry logic with exponential backoff
- [ ] Implement exception translation

### Phase 6: Azure Adapter
- [ ] Create `src/fs2/core/adapters/llm_adapter_azure.py`
- [ ] Implement `AsyncAzureOpenAI` client initialization
- [ ] Implement content filter handling
- [ ] Implement retry logic

### Phase 7: LLMService
- [ ] Create `src/fs2/core/services/llm_service.py`
- [ ] Implement factory method with provider selection
- [ ] Implement environment variable expansion
- [ ] Wire up adapter injection

### Phase 8: Testing
- [ ] Create `tests/unit/adapters/test_llm_adapter_fake.py`
- [ ] Create `tests/unit/services/test_llm_service.py`
- [ ] Create `tests/docs/test_llm_adapter_pattern.py` (canonical examples)

---

## External Research Opportunities

### Research Opportunity 1: OpenAI SDK Best Practices 2024+

**Why Needed**: The flowspace code uses openai SDK v1.x patterns. Need to verify current best practices for async client usage, error handling, and retry configuration.

**Impact on Plan**: May affect client initialization and error handling code.

**Source Findings**: IA-04, IC-08

**Ready-to-use prompt:**
```
/deepresearch "OpenAI Python SDK v1.x async best practices 2024:
- AsyncOpenAI client initialization patterns
- Recommended retry configuration (max_retries parameter vs manual)
- Error handling hierarchy (APIError, RateLimitError, AuthenticationError)
- Token counting and usage tracking
- Connection pooling and timeout configuration
Context: Building an LLM adapter for a Clean Architecture Python project using openai>=1.0.0"
```

**Results location**: Save results to `docs/plans/007-llm-service/external-research/openai-sdk-best-practices.md`

### Research Opportunity 2: Azure OpenAI Content Safety Policies

**Why Needed**: Need to understand current Azure content filter behavior, error codes, and recommended handling strategies.

**Impact on Plan**: Affects error handling and fallback response logic for Azure adapter.

**Source Findings**: IA-05, IC-07

**Ready-to-use prompt:**
```
/deepresearch "Azure OpenAI content filtering and safety 2024:
- Content filter categories and severity levels
- Error response format when content is filtered
- Best practices for handling filtered content gracefully
- Differences from OpenAI API error handling
- Configuration options for content filtering
Context: Implementing Azure OpenAI adapter that needs to handle content filter rejections without crashing"
```

**Results location**: Save results to `docs/plans/007-llm-service/external-research/azure-content-filtering.md`

---

## Appendix: File Inventory

### Files to Create

| File | Purpose | Priority |
|------|---------|----------|
| `src/fs2/core/adapters/llm_adapter.py` | ABC interface | P0 |
| `src/fs2/core/adapters/llm_adapter_fake.py` | Test fake | P0 |
| `src/fs2/core/adapters/llm_adapter_openai.py` | OpenAI impl | P1 |
| `src/fs2/core/adapters/llm_adapter_azure.py` | Azure impl | P1 |
| `src/fs2/core/models/llm_response.py` | Response model | P0 |
| `src/fs2/core/services/llm_service.py` | Service layer | P1 |
| `tests/unit/adapters/test_llm_adapter_fake.py` | Fake tests | P0 |
| `tests/unit/services/test_llm_service.py` | Service tests | P1 |

### Files to Modify

| File | Changes | Priority |
|------|---------|----------|
| `src/fs2/config/objects.py` | Add LLM config classes | P0 |
| `src/fs2/core/adapters/exceptions.py` | Add LLM exceptions | P0 |
| `src/fs2/core/adapters/__init__.py` | Export new adapters | P1 |
| `.fs2/secrets.env.example` | Add LLM env vars | P0 |
| `.fs2/config.yaml.example` | Add LLM section | P0 |
| `pyproject.toml` | Add openai dependency | P0 |

### Reference Files (from Flowspace)

| File | What to Reference |
|------|-------------------|
| `src/modules/llm/service.py` | Factory pattern, provider selection |
| `src/modules/llm/interfaces.py` | ILlmRepository ABC |
| `src/modules/llm/repositories/openai_repository.py` | OpenAI client usage |
| `src/modules/llm/repositories/azure_repository.py` | Azure client + content filter |
| `src/modules/config/models.py:LlmConfig` | Configuration structure |

---

## Next Steps

**External Research Opportunities identified: 2**

1. Run `/deepresearch` prompts above for OpenAI SDK and Azure content filtering
2. Save results to `external-research/` folder
3. Then proceed to specification with `/plan-1b-specify`

**Or skip external research:**
- Run `/plan-1b-specify "LLMService with OpenAI and Azure adapters"` to create specification

Note: Unresolved research opportunities will be flagged in `/plan-1b-specify` output.

---

**Research Complete**: 2025-12-17T12:00:00Z
**Report Location**: `docs/plans/007-llm-service/research-dossier.md`
