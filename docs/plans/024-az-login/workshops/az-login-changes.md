# Workshop: Azure AD Credential Changes

**Type**: Integration Pattern
**Plan**: 024-az-login
**Created**: 2026-02-13
**Status**: Draft

**Related Documents**:
- [Research Dossier](../research-dossier.md)
- [azure-identity version compat](../external-research/azure-identity-version-compat.md)
- [async credential behavior](../external-research/async-credential-behavior.md)

---

## Purpose

Exact before/after for every change needed to support Azure AD credentials alongside API keys.

## Design Rule

**Have a key? Use it. No key? Use `az login` credentials.**

That's it. No config flags, no auth mode enum, no provider abstraction. Just detect what's available.

---

## Change 1: Make embedding api_key optional

**File**: `src/fs2/config/objects.py` (lines 469-488)

### Before

```python
class AzureEmbeddingConfig(BaseModel):
    endpoint: str
    api_key: str                                    # REQUIRED
    deployment_name: str = "text-embedding-3-small"
    api_version: str = "2024-02-01"

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        """Validate api_key is not empty."""
        if not v or not v.strip():
            raise ValueError("api_key must not be empty")
        return v
```

### After

```python
class AzureEmbeddingConfig(BaseModel):
    endpoint: str
    api_key: str | None = None                      # NOW OPTIONAL
    deployment_name: str = "text-embedding-3-small"
    api_version: str = "2024-02-01"

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """Validate api_key is not empty when provided."""
        if v is not None and not v.strip():
            raise ValueError("api_key must not be empty when provided")
        return v
```

**Why**: `LLMConfig.api_key` is already `str | None = None`. This makes embedding match.

---

## Change 2: LLM adapter — use token provider when no key

**File**: `src/fs2/core/adapters/llm_adapter_azure.py` (lines 98-113)

### Before

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

### After

```python
def _get_client(self) -> AsyncAzureOpenAI:
    if self._client is None:
        if self._llm_config.api_key:
            # Key-based auth
            self._client = AsyncAzureOpenAI(
                api_key=self._llm_config.api_key,
                azure_endpoint=self._llm_config.base_url,
                api_version=self._llm_config.azure_api_version,
                timeout=self._llm_config.timeout,
            )
        else:
            # Azure AD auth (az login / DefaultAzureCredential)
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            self._client = AsyncAzureOpenAI(
                azure_ad_token_provider=token_provider,
                azure_endpoint=self._llm_config.base_url,
                api_version=self._llm_config.azure_api_version,
                timeout=self._llm_config.timeout,
            )
    return self._client
```

**Why**:
- Lazy import — `azure-identity` only loaded when actually needed
- `api_key` and `azure_ad_token_provider` are mutually exclusive in the SDK
- Sync `DefaultAzureCredential` works fine with `AsyncAzureOpenAI` (SDK auto-detects)
- No cleanup/close needed for sync credential

---

## Change 3: Embedding adapter — same pattern

**File**: `src/fs2/core/adapters/embedding_adapter_azure.py` (lines 76-88)

### Before

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

### After

```python
def _get_client(self) -> AsyncAzureOpenAI:
    if self._client is None:
        if self._azure_config.api_key:
            # Key-based auth
            self._client = AsyncAzureOpenAI(
                api_key=self._azure_config.api_key,
                azure_endpoint=self._azure_config.endpoint,
                api_version=self._azure_config.api_version,
            )
        else:
            # Azure AD auth (az login / DefaultAzureCredential)
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            self._client = AsyncAzureOpenAI(
                azure_ad_token_provider=token_provider,
                azure_endpoint=self._azure_config.endpoint,
                api_version=self._azure_config.api_version,
            )
    return self._client
```

**Why**: Identical pattern to LLM adapter. Both adapters construct their client once (lazy init), so the credential + token provider are created once too.

---

## Change 4: Add azure-identity dependency

**File**: `pyproject.toml`

### Before

```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.8",
]
```

### After

```toml
[project.optional-dependencies]
azure-ad = [
    "azure-identity>=1.18.0,<2",
]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
    "ruff>=0.8",
]
```

**Why**:
- Optional dep — users who only use API keys don't need it
- `>=1.18.0` gives us `get_bearer_token_provider()` + improved token caching
- Install: `pip install fs2[azure-ad]` or `uv pip install fs2[azure-ad]`

---

## Change 5: Better error when azure-identity missing

Both `_get_client()` methods should handle the import failure gracefully.

### Pattern

```python
else:
    # Azure AD auth
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    except ImportError:
        raise LLMAdapterError(  # or EmbeddingAdapterError
            "azure-identity package is required for Azure AD authentication. "
            "Install it with: pip install fs2[azure-ad]"
        )
    # ... rest of credential setup
```

---

## What does NOT change

- **Config loading pipeline** (`service.py`, `loaders.py`) — untouched
- **Existing tests** — all use `api_key="test-key"`, continue to pass
- **User configs with keys** — still work exactly the same
- **Validators on LLMConfig** — already handle `api_key=None`
- **Factory patterns** — `LLMService.create()` and `EmbeddingService.create()` untouched
- **No new config fields** — no `auth_mode`, no `use_azure_ad`, nothing

---

## User experience

### With API key (unchanged)

```yaml
# config.yaml
llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}
  base_url: https://myresource.openai.azure.com/
  azure_deployment_name: gpt-5-mini
  azure_api_version: 2024-12-01-preview
```

### With Azure AD (just remove the api_key line)

```yaml
# config.yaml
llm:
  provider: azure
  # no api_key → uses az login
  base_url: https://myresource.openai.azure.com/
  azure_deployment_name: gpt-5-mini
  azure_api_version: 2024-12-01-preview
```

### Prerequisites for Azure AD

1. `az login` (have a valid session)
2. `pip install fs2[azure-ad]`
3. RBAC role: `Cognitive Services OpenAI User` on the Azure OpenAI resource

---

## Summary

| # | File | What | Lines changed |
|---|------|------|:---:|
| 1 | `config/objects.py` | `api_key: str` → `str \| None = None` + fix validator | ~5 |
| 2 | `adapters/llm_adapter_azure.py` | Branch `_get_client()` on key presence | ~15 |
| 3 | `adapters/embedding_adapter_azure.py` | Same branch pattern | ~15 |
| 4 | `pyproject.toml` | Add `azure-ad` optional dep group | ~3 |
| 5 | Both adapters | ImportError → actionable message | (included above) |
| **Total** | | | **~38** |

No new files. No new abstractions. No new config fields.
