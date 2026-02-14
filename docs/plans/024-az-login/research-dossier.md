# Research Report: Azure AD Credential Support for fs2

**Generated**: 2026-02-13T18:15:00Z
**Research Query**: "Replace API key auth with Azure AD credentials (az login) for Azure OpenAI access, keeping key access as fallback"
**Mode**: Plan-Associated (024-az-login)
**Location**: docs/plans/024-az-login/research-dossier.md
**Findings**: 30 consolidated from 4 parallel subagents against actual source

## Executive Summary

### What It Does
fs2 uses `AsyncAzureOpenAI` to call two Azure OpenAI endpoints — one for LLM chat completions (smart content) and one for embeddings. Both authenticate exclusively via API keys loaded from `secrets.env` through `${VAR}` placeholders in config.

### Business Purpose
Azure policy is changing: API keys are being disallowed on certain tenants. Users who `az login` need fs2 to automatically use their Azure AD token, without requiring an API key. Key-based auth must remain for tenants without this restriction.

### Key Insights
1. **Two `_get_client()` methods** are the only code that needs modification — `llm_adapter_azure.py:106-113` and `embedding_adapter_azure.py:82-88`. Both are simple, isolated, lazy-init.
2. **`LLMConfig.api_key` is already `str | None = None`** — the extension point is open. Only `AzureEmbeddingConfig.api_key` needs to become optional.
3. **The LLM adapter init already handles `api_key=None`** — the validation at line 73 is `if api_key is not None:`, so it cleanly skips when no key is provided.
4. **`azure-identity` is NOT a dependency** — must be added. No references to it exist anywhere in the codebase.
5. **Comprehensive test suite exists** — ~2000+ lines of adapter and config tests, all using mocked clients with `api_key="test-key"`. Tests can remain unchanged since they test key-based auth.

### Quick Stats
- **Files to modify**: 4 (2 adapters, 1 config model, 1 pyproject.toml)
- **Dependencies to add**: `azure-identity>=1.18.0,<2`
- **Test coverage**: Extensive for adapters + config validation (see QT findings)
- **Complexity**: Low — surgical changes to well-isolated code

---

## How It Currently Works

### Authentication Flow

```
~/.config/fs2/secrets.env
    │  AZURE_OPENAI_API_KEY=...
    │  AZURE_EMBEDDING_API_KEY=...
    ▼
FS2ConfigurationService.__init__()  [service.py:147-233]
    │  Phase 1: load_secrets_to_env()    → os.environ
    │  Phase 2: load_yaml_config()       → raw dict with ${VAR}
    │  Phase 4: deep_merge()             → user < project < env
    │  Phase 6: expand_placeholders()    → ${VAR} → actual values
    │  Phase 7: _create_config_objects() → LLMConfig / EmbeddingConfig
    ▼
Adapter.__init__(config: ConfigurationService)
    │  config.require(LLMConfig) or config.require(EmbeddingConfig)
    │  Validates: api_key not empty, no unexpanded ${} placeholders
    ▼
_get_client()  [lazy, on first API call]
    │
    ▼
AsyncAzureOpenAI(api_key=..., azure_endpoint=..., api_version=...)
    │
    ▼
client.chat.completions.create(...)  /  client.embeddings.create(...)
```

### Secrets Loading Precedence (lowest → highest)
1. OS environment (base layer)
2. User secrets (`~/.config/fs2/secrets.env`)
3. Project secrets (`./.fs2/secrets.env`)
4. Working dir `.env`

### LLM Client Construction
**File**: `src/fs2/core/adapters/llm_adapter_azure.py:98-113`
```python
def _get_client(self) -> AsyncAzureOpenAI:
    if self._client is None:
        self._client = AsyncAzureOpenAI(
            api_key=self._llm_config.api_key,
            azure_endpoint=self._llm_config.base_url,
            api_version=self._llm_config.azure_api_version,
            timeout=self._llm_config.timeout,
        )
    return self._client
```

### LLM Adapter Init Validation
**File**: `src/fs2/core/adapters/llm_adapter_azure.py:58-91`
```python
def __init__(self, config: "ConfigurationService") -> None:
    self._config_service = config
    self._llm_config = config.require(LLMConfig)
    self._client: AsyncAzureOpenAI | None = None

    # Validate API key at init time
    api_key = self._llm_config.api_key
    if api_key is not None:              # ← ALREADY skips when None
        if "${" in api_key:
            raise LLMAdapterError(...)
        if not api_key:
            raise LLMAdapterError(...)

    # Validate base_url (Azure endpoint) — always required
    base_url = self._llm_config.base_url
    if not base_url:
        raise LLMAdapterError(...)
```

### Embedding Client Construction
**File**: `src/fs2/core/adapters/embedding_adapter_azure.py:76-88`
```python
def _get_client(self) -> AsyncAzureOpenAI:
    if self._client is None:
        self._client = AsyncAzureOpenAI(
            api_key=self._azure_config.api_key,
            azure_endpoint=self._azure_config.endpoint,
            api_version=self._azure_config.api_version,
        )
    return self._client
```

### Embedding Adapter Init
**File**: `src/fs2/core/adapters/embedding_adapter_azure.py:49-69`
```python
def __init__(self, config: "ConfigurationService") -> None:
    self._config_service = config
    self._embedding_config = config.require(EmbeddingConfig)
    self._client: AsyncAzureOpenAI | None = None

    if self._embedding_config.azure is None:
        raise EmbeddingAdapterError(
            "Azure config is required for mode='azure'. "
            "Set embedding.azure.endpoint and embedding.azure.api_key."
        )
    self._azure_config = self._embedding_config.azure
```
Note: No api_key-specific validation here — that's done by Pydantic in `AzureEmbeddingConfig`.

---

## Config Models

### LLMConfig (`src/fs2/config/objects.py:265-382`)
```python
class LLMConfig(BaseModel):
    __config_path__: ClassVar[str] = "llm"

    provider: Literal["azure", "openai", "fake"]    # REQUIRED
    api_key: str | None = None                       # ALREADY OPTIONAL
    base_url: str | None = None
    azure_deployment_name: str | None = None
    azure_api_version: str | None = None
    model: str | None = None
    temperature: float = 0.1
    max_tokens: int = 1024
    timeout: int = 30
    max_retries: int = 3
```

**Validators**:
- `validate_api_key`: Rejects `sk-` prefix (OpenAI literal key). Allows None.
- `validate_timeout`: Range 1-120 seconds.
- `validate_azure_fields` (model_validator): When `provider=azure`, requires `base_url`, `azure_deployment_name`, `azure_api_version`. Does NOT require `api_key`.

### AzureEmbeddingConfig (`src/fs2/config/objects.py:444-488`)
```python
class AzureEmbeddingConfig(BaseModel):
    endpoint: str                                    # REQUIRED
    api_key: str                                     # REQUIRED ← needs to become optional
    deployment_name: str = "text-embedding-3-small"
    api_version: str = "2024-02-01"
```

**Validators**:
- `validate_endpoint`: Rejects empty string.
- `validate_api_key`: Rejects empty string. **Does NOT allow None — needs change.**

### EmbeddingConfig (`src/fs2/config/objects.py:545-675`)
```python
class EmbeddingConfig(BaseModel):
    __config_path__: ClassVar[str] = "embedding"

    mode: Literal["azure", "openai_compatible", "fake"] = "azure"
    dimensions: int = 1024
    azure: AzureEmbeddingConfig | None = None        # Nested, optional
    # ... chunking, retry config
```

---

## Adapter Factory Pattern

### LLM Service Factory
**File**: `src/fs2/core/services/llm_service.py`
```python
class LLMService:
    @staticmethod
    def create(config: ConfigurationService) -> LLMService:
        llm_config = config.require(LLMConfig)
        if llm_config.provider == "azure":
            adapter = AzureOpenAIAdapter(config)
        elif llm_config.provider == "openai":
            adapter = OpenAIAdapter(config)
        elif llm_config.provider == "fake":
            adapter = FakeLLMAdapter()
        return LLMService(adapter)
```

### Embedding Adapter Factory
**File**: `src/fs2/core/adapters/embedding_adapter.py`
```python
def create_embedding_adapter_from_config(config: ConfigurationService) -> EmbeddingAdapter:
    embedding_config = config.require(EmbeddingConfig)
    if embedding_config.mode == "azure":
        return AzureEmbeddingAdapter(config)
    elif embedding_config.mode == "fake":
        return FakeEmbeddingAdapter()
```

---

## Dependencies

### Current (`pyproject.toml`)
| Package | Version |
|---------|---------|
| `openai` | >=1.0.0 (installed: 2.20.0) |
| `pydantic` | >=2.0 |
| `python-dotenv` | >=1.0 |
| `pyyaml` | >=6.0 |
| **`azure-identity`** | **NOT PRESENT** |

### Optional Dep Groups
- `dev`: pytest, pytest-asyncio, pytest-cov, ruff
- No `azure` or similar group exists yet

---

## Test Coverage

### Adapter Tests
| File | Lines | What It Tests |
|------|-------|---------------|
| `tests/unit/adapters/test_llm_adapter_azure.py` | 341 | Init validation, content filter handling, generate flow |
| `tests/unit/adapters/test_embedding_adapter_azure.py` | 601 | Init validation, embed_text, embed_batch, retry/backoff |

### Config Tests
| File | Lines | What It Tests |
|------|-------|---------------|
| `tests/unit/config/test_llm_config.py` | 407 | Provider validation, api_key security, Azure field cross-validation |
| `tests/unit/config/test_embedding_config.py` | 744 | AzureEmbeddingConfig validation, nested config loading |
| `tests/unit/config/test_configuration_service.py` | 330 | YAML loading, env var precedence, placeholder expansion |
| `tests/unit/config/test_secrets_loading.py` | 187 | Secrets file precedence |

### Test Patterns
- All tests use `api_key="test-key"` (mock strings, never real keys)
- Client always mocked via `patch.object(adapter, "_get_client")`
- `FakeConfigurationService` for DI in tests
- No real API calls in CI

### Existing Tests That Verify api_key=None Works
- `test_llm_config_accepts_none_api_key()` in `test_llm_config.py:174`

---

## Modification Plan

### Config: Before & After

**Key-based (current config — unchanged)**:
```yaml
llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  base_url: https://jordoopenai2.openai.azure.com/
  azure_deployment_name: gpt-5-mini
  azure_api_version: 2024-12-01-preview

embedding:
  mode: azure
  azure:
    endpoint: https://oaijodoaustralia.openai.azure.com/
    api_key: ${AZURE_EMBEDDING_API_KEY}
    deployment_name: text-embedding-3-small-no-rate
```

**Azure AD (new — just remove api_key lines)**:
```yaml
llm:
  provider: azure
  # no api_key → uses az login / DefaultAzureCredential
  base_url: https://jordoopenai2.openai.azure.com/
  azure_deployment_name: gpt-5-mini
  azure_api_version: 2024-12-01-preview

embedding:
  mode: azure
  azure:
    endpoint: https://oaijodoaustralia.openai.azure.com/
    # no api_key → uses az login / DefaultAzureCredential
    deployment_name: text-embedding-3-small-no-rate
```

### Files to Modify

| # | File | Change | Lines |
|---|------|--------|-------|
| 1 | `src/fs2/config/objects.py:469-488` | `AzureEmbeddingConfig.api_key`: `str` → `str \| None = None`, update validator | ~5 |
| 2 | `src/fs2/core/adapters/llm_adapter_azure.py:106-113` | `_get_client()`: branch on api_key presence | ~12 |
| 3 | `src/fs2/core/adapters/embedding_adapter_azure.py:82-88` | `_get_client()`: branch on api_key presence | ~12 |
| 4 | `pyproject.toml` | Add `azure-ad` optional dependency | ~2 |
| **Total** | | | **~31** |

### Safe to Modify
1. **`_get_client()` methods** — isolated, lazy-init, no side effects, well-tested
2. **`AzureEmbeddingConfig.api_key` type** — making optional is additive, backward-compatible
3. **`pyproject.toml` optional deps** — additive change

### Modify with Caution
1. **Embedding adapter init error message** (line 64-67) — currently says "Set embedding.azure.api_key". Should mention Azure AD alternative.

### Danger Zones
1. **Breaking existing configs** — any user with `api_key: ${SOME_VAR}` must continue to work. The implicit detection approach (key present → use it, absent → use Azure AD) ensures this.

---

## External Research (Completed)

Results saved in `external-research/`:

### azure-identity-version-compat.md
- `get_bearer_token_provider()` introduced in v1.15.0
- Recommended pin: `>=1.18.0,<2.0.0`
- Fully compatible with `openai==2.20.0`
- Install footprint: ~8-15MB with transitive deps

### async-credential-behavior.md
- Sync `DefaultAzureCredential` works with `AsyncAzureOpenAI` — SDK auto-detects via `inspect.isawaitable()`
- Blocking only on cache miss (~100-500ms every 30-60 min)
- **Sync credential recommended** for fs2's batch-oriented use case
- No cleanup needed (no `close()` required)
- Token provider can be shared across clients (same MSAL cache)

---

## Prior Learnings

> No prior learnings found. Only one plan (`001-universal-ast-parser`) exists, with no Discoveries & Learnings sections.

---

## Next Steps

1. `/plan-2c-workshop` — Create implementation workshop (KISS/YAGNI)
2. `/plan-3-architect` — Design phased implementation
3. Or proceed directly to implementation — the change is small and well-understood

---

**Research Complete**: 2026-02-13T18:15:00Z
**Report Location**: docs/plans/024-az-login/research-dossier.md
