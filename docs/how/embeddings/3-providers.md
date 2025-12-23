# Embedding Providers

Setup guides for each embedding provider.

## Azure OpenAI

The recommended provider for production use.

### Prerequisites

1. Azure OpenAI resource created
2. `text-embedding-3-small` model deployed
3. Endpoint URL and API key available

### Configuration

```yaml
# .fs2/config.yaml
embedding:
  mode: azure
  dimensions: 1024
  azure:
    endpoint: "${FS2_AZURE__EMBEDDING__ENDPOINT}"
    api_key: "${FS2_AZURE__EMBEDDING__API_KEY}"
    deployment_name: "text-embedding-3-small"
    api_version: "2024-02-01"
```

### Environment Variables

```bash
# .fs2/secrets.env (gitignored)
FS2_AZURE__EMBEDDING__ENDPOINT=https://your-resource.openai.azure.com/
FS2_AZURE__EMBEDDING__API_KEY=your-api-key-here
```

### Deployment Name

Use your Azure deployment name, not the model name:

```yaml
# Correct - use deployment name
deployment_name: "my-embedding-deployment"

# Wrong - this is the model name, not deployment
deployment_name: "text-embedding-3-small"
```

Check your deployment name in Azure Portal > Azure OpenAI > Deployments.

### API Version

Quote the API version in YAML to prevent date parsing:

```yaml
# Correct - quoted string
api_version: "2024-06-01"

# Wrong - parsed as date
api_version: 2024-06-01
```

### Rate Limiting

Azure has rate limits (tokens per minute). The adapter handles this automatically:

1. Detects 429 responses
2. Respects `Retry-After` header if present
3. Falls back to exponential backoff (2s, 4s, 8s... up to 60s)

Configure retry behavior:

```yaml
embedding:
  max_retries: 3     # Attempts before failing
  base_delay: 2.0    # Initial backoff
  max_delay: 60.0    # Maximum backoff
```

---

## OpenAI Compatible

For OpenAI API or compatible providers (LocalAI, Ollama, etc.).

### Configuration

The `openai_compatible` mode requires explicit constructor parameters (not YAML config):

```python
from fs2.core.adapters.embedding_adapter_openai import OpenAICompatibleEmbeddingAdapter

adapter = OpenAICompatibleEmbeddingAdapter(
    config=config_service,
    api_key="sk-your-openai-key",
    base_url="https://api.openai.com/v1",
    model="text-embedding-3-small",
)
```

### YAML (Partial)

```yaml
# .fs2/config.yaml
embedding:
  mode: openai_compatible  # Signals to use OpenAI adapter
  dimensions: 1024
```

**Note**: Connection parameters (api_key, base_url, model) must be provided programmatically. The factory method `EmbeddingService.create()` does not support automatic wiring for `openai_compatible` mode.

### Local Providers

For local embedding servers (Ollama, LocalAI):

```python
adapter = OpenAICompatibleEmbeddingAdapter(
    config=config_service,
    api_key="not-needed",  # Some local providers don't require keys
    base_url="http://localhost:11434/v1",  # Ollama
    model="nomic-embed-text",
)
```

---

## Fake (Testing)

For testing without API calls.

### Configuration

```yaml
# .fs2/config.yaml
embedding:
  mode: fake
  dimensions: 1024
```

### Behavior

The `FakeEmbeddingAdapter` returns deterministic embeddings:

1. **Fixture lookup**: If content matches `fixture_graph.pkl`, returns real embeddings
2. **Hash fallback**: For unknown content, generates deterministic vectors from content hash

This enables:
- CI/CD testing without API credentials
- Reproducible test results
- Fast local development

### Regenerating Fixtures

To update fixture embeddings with real API responses:

```bash
# Set Azure credentials
export FS2_AZURE__EMBEDDING__ENDPOINT=...
export FS2_AZURE__EMBEDDING__API_KEY=...

# Regenerate
just generate-fixtures
```

The fixture graph is committed to the repo (4MB).

---

## Error Handling

All adapters raise domain-specific exceptions:

```python
from fs2.core.adapters import (
    EmbeddingAdapterError,
    EmbeddingAuthenticationError,
    EmbeddingRateLimitError,
)

try:
    embedding = await adapter.embed_text(content)
except EmbeddingAuthenticationError:
    # Invalid API key or endpoint
    print("Check your API credentials")
except EmbeddingRateLimitError as e:
    # Rate limited - includes retry metadata
    print(f"Rate limited. Retry after: {e.retry_after}s")
except EmbeddingAdapterError as e:
    # Generic embedding error
    print(f"Embedding failed: {e}")
```

---

## Troubleshooting

### "API key contains unexpanded placeholder"

The `${VAR}` wasn't expanded. Check:
1. Environment variable is set: `echo $FS2_AZURE__EMBEDDING__API_KEY`
2. secrets.env file exists and is sourced
3. Variable name matches exactly

### "endpoint required when mode=azure"

Azure mode requires the endpoint URL:
```yaml
azure:
  endpoint: "https://your-resource.openai.azure.com/"
```

### "Embedding dimension mismatch"

The model returned different dimensions than configured. Either:
1. Pass `dimensions` parameter to API (text-embedding-3-* only)
2. Update config to match model's native dimensions

### Rate Limit Errors After Retries

The adapter retries automatically. If still failing:
1. Increase `max_retries` in config
2. Reduce `batch_size` to lower tokens per call
3. Check your Azure/OpenAI quota

---

## Next Steps

- [Configuration](2-configuration.md) - Full config options
- [Overview](1-overview.md) - Architecture and concepts
