# External Research: DefaultAzureCredential Async Behavior with OpenAI SDK

**Source**: Perplexity Deep Research + OpenAI SDK source analysis, 2026-02-13

## Key Findings

### How AsyncAzureOpenAI Handles Token Providers

The SDK's internal `_get_azure_ad_token()` method (from `openai/lib/azure.py`):

```python
async def _get_azure_ad_token(self) -> str | None:
    provider = self._azure_ad_token_provider
    if provider is not None:
        token = provider()
        if inspect.isawaitable(token):
            token = await token
        return str(token)
    return None
```

- Called **before every API request** (not cached by the SDK)
- Accepts both sync `str` return and async `Awaitable[str]` return
- All caching is delegated to azure-identity's MSAL layer

### Sync vs Async Credential Decision

| Approach | Event Loop Blocking | Cleanup Needed | Recommended For |
|----------|-------------------|----------------|-----------------|
| Sync `DefaultAzureCredential` + sync `get_bearer_token_provider` | **Yes** on cache miss (~100-500ms every ~30-60 min) | No | Simple scripts, low concurrency |
| Async `DefaultAzureCredential` (from `.aio`) + async `get_bearer_token_provider` | **No** | Yes (`await credential.close()`) | Production async services |

### Recommendation for fs2

**Use sync `DefaultAzureCredential`** with sync `get_bearer_token_provider`. Rationale:

1. fs2 adapters lazily construct the client once and reuse it — the blocking only occurs on first token fetch and periodic refresh (~every 30-60 min)
2. fs2's async operations (scan, embed) are batch-oriented, not high-concurrency HTTP servers
3. Sync credential requires **no lifecycle management** (no `close()` needed)
4. Async credential requires `aiohttp` as additional dependency
5. Microsoft's own examples predominantly use sync credential with `AsyncAzureOpenAI`

If fs2 later becomes a high-concurrency service, switch to async credential.

### Sharing Token Provider Across Clients

**Safe and recommended.** A single `get_bearer_token_provider` callable can be shared across multiple `AsyncAzureOpenAI` clients (LLM + embeddings) because:
- Same Azure AD scope (`https://cognitiveservices.azure.com/.default`) for both
- MSAL token cache is thread-safe
- Token is acquired once and reused by both clients

### Recommended Implementation Pattern

```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

# Create once, share across adapters
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

# LLM client
llm_client = AsyncAzureOpenAI(
    azure_endpoint="https://jordoopenai2.openai.azure.com/",
    api_version="2024-12-01-preview",
    azure_ad_token_provider=token_provider,
)

# Embedding client (same token provider)
embed_client = AsyncAzureOpenAI(
    azure_endpoint="https://oaijodoaustralia.openai.azure.com/",
    api_version="2024-02-01",
    azure_ad_token_provider=token_provider,
)
```

### Python 3.12 vs 3.13
No meaningful differences for this pattern. Both versions work identically.

### Pitfalls
- Do NOT pass `api_key` AND `azure_ad_token_provider` — they are mutually exclusive
- Scope must be exactly `https://cognitiveservices.azure.com/.default`
- User must have `Cognitive Services OpenAI User` RBAC role on the resource
- `AZURE_TOKEN_CREDENTIALS=dev` (azure-identity >= 1.23.0) can speed up local dev by skipping production credentials
