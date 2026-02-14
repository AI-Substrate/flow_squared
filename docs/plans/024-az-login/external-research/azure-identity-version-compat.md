# External Research: azure-identity Version Compatibility

**Source**: Perplexity Deep Research, 2026-02-13

## Key Findings

### Minimum Version for `get_bearer_token_provider()`
- **Introduced in azure-identity 1.15.0** (October 26, 2023)
- Prior to 1.15.0, developers had to manually call `credential.get_token()` and manage refresh

### Version History (Relevant Highlights)

| Version | Date | Key Change |
|---------|------|-----------|
| 1.14.0 | Aug 2023 | Developer credential continuation policy (az login failures don't stop chain) |
| **1.15.0** | **Oct 2023** | **`get_bearer_token_provider()` introduced** |
| 1.18.0 | Sep 2024 | `SupportsTokenInfo` protocol, improved token caching |
| 1.22.0 | May 2025 | Stricter ManagedIdentity validation, IMDS reliability improvements |
| 1.23.0 | May 2025 | `AZURE_TOKEN_CREDENTIALS` env var for fast credential selection |
| 1.25.1 | Latest | Stability improvements |

### Recommended Pin
```
azure-identity>=1.18.0,<2.0.0
```
Rationale: provides `get_bearer_token_provider()`, `SupportsTokenInfo` protocol, improved caching, and the developer credential continuation policy.

### Compatibility with openai==2.20.0
**Fully compatible.** `azure_ad_token_provider` parameter has existed since openai SDK v1.0 (Nov 2023). The SDK's `AsyncAzureOpenAI` accepts `Callable[[], str | Awaitable[str]]` and auto-detects sync vs async via `inspect.isawaitable()`.

### Install Footprint
- azure-identity itself: ~400-600 KB
- All transitive deps (azure-core, msal, msal-extensions, cryptography, etc.): **~8-15 MB total**

### Two `get_bearer_token_provider` Variants

| Module | Returns | Use With |
|--------|---------|----------|
| `azure.identity` (sync) | `Callable[[], str]` | `AzureOpenAI` (sync client) |
| `azure.identity.aio` (async) | `Callable[[], Coroutine[..., str]]` | `AsyncAzureOpenAI` (async client) |

### Optional Dependency Pattern
```python
try:
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    HAS_AZURE_IDENTITY = True
except ImportError:
    HAS_AZURE_IDENTITY = False
```

### Pitfalls
- Sync `DefaultAzureCredential` tries credentials 1-6 sequentially, can take ~10s on first call
- Token lifetime ~1 hour, auto-refreshed at ~80% expiry by MSAL
- Correct scope: `https://cognitiveservices.azure.com/.default` (NOT `openai.azure.com`)
- RBAC required: `Cognitive Services OpenAI User` role on the Azure OpenAI resource
