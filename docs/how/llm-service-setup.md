# LLM Service Setup Guide

This guide explains how to configure and use the LLMService for smart content generation.

## Quick Start

1. **Copy the example config**:
   ```bash
   cp .fs2/config.yaml.example .fs2/config.yaml
   ```

2. **Set your API key** (choose one):

   **For Azure OpenAI**:
   ```bash
   # Create secrets file
   cp .fs2/secrets.env.example .fs2/secrets.env

   # Edit and add your key
   echo "AZURE_OPENAI_API_KEY=your-key-here" >> .fs2/secrets.env

   # Update config.yaml
   # llm:
   #   provider: azure
   #   api_key: ${AZURE_OPENAI_API_KEY}
   #   base_url: https://your-resource.openai.azure.com/
   #   azure_deployment_name: gpt-4
   #   azure_api_version: 2024-12-01-preview
   ```

   **For OpenAI**:
   ```bash
   echo "OPENAI_API_KEY=sk-your-key-here" >> .fs2/secrets.env

   # Update config.yaml
   # llm:
   #   provider: openai
   #   api_key: ${OPENAI_API_KEY}
   ```

   **For Testing (no API)**:
   ```yaml
   # In config.yaml
   llm:
     provider: fake
   ```

3. **Use the service**:
   ```python
   from fs2.config import FS2ConfigurationService
   from fs2.core.services.llm_service import LLMService

   config = FS2ConfigurationService()
   service = LLMService.create(config)

   response = await service.generate("Summarize this code...")
   print(response.content)
   ```

## Configuration Reference

### Provider Selection

| Provider | Use Case |
|----------|----------|
| `azure` | Production with Azure OpenAI |
| `openai` | Production with OpenAI API |
| `fake` | Testing without API calls |

### LLM Config Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `provider` | Yes | - | `azure`, `openai`, or `fake` |
| `api_key` | Azure/OpenAI | `null` | Use `${ENV_VAR}` placeholder |
| `base_url` | Azure | `null` | Azure endpoint URL |
| `azure_deployment_name` | Azure | `null` | Deployment name |
| `azure_api_version` | Azure | `null` | API version |
| `model` | No | `null` | Model name for logging |
| `temperature` | No | `0.1` | Generation temperature |
| `max_tokens` | No | `1024` | Maximum tokens |
| `timeout` | No | `120` | Request timeout (seconds) |
| `max_retries` | No | `3` | Retry count for 429/502/503 |

## Security

### API Key Handling

- **Never** commit literal API keys to config files
- Use `${ENV_VAR}` placeholder syntax
- Keys with `sk-` prefix or >64 chars are rejected

### Example Secure Setup

```yaml
# .fs2/config.yaml (committed)
llm:
  provider: azure
  api_key: ${AZURE_OPENAI_API_KEY}  # Placeholder, not the actual key
  base_url: https://myinstance.openai.azure.com/
```

```bash
# .fs2/secrets.env (gitignored)
AZURE_OPENAI_API_KEY=your-actual-key-here
```

## Error Handling

The service provides domain-specific exceptions:

```python
from fs2.core.adapters import (
    LLMAdapterError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMContentFilterError,
)

try:
    response = await service.generate(prompt)
except LLMAuthenticationError:
    print("Check your API key")
except LLMRateLimitError:
    print("Rate limited, try again later")
except LLMContentFilterError:
    print("Content was filtered")
except LLMAdapterError as e:
    print(f"LLM error: {e}")
```

### Content Filter Handling

Azure may filter content. Instead of raising, the adapter returns a graceful response:

```python
response = await service.generate(prompt)
if response.was_filtered:
    print("Content was filtered by safety systems")
else:
    print(response.content)
```

## Testing

Use `FakeLLMAdapter` for deterministic tests:

```python
from fs2.core.adapters import FakeLLMAdapter
from fs2.core.services.llm_service import LLMService

adapter = FakeLLMAdapter()
adapter.set_response("Expected response")

service = LLMService(mock_config, adapter)
response = await service.generate("Any prompt")

assert response.content == "Expected response"
assert adapter.call_history[0]["prompt"] == "Any prompt"
```

## Troubleshooting

### "API key contains unexpanded placeholder"

The `${VAR}` wasn't expanded. Check:
1. Environment variable is set: `echo $AZURE_OPENAI_API_KEY`
2. secrets.env file exists and is loaded
3. Variable name matches exactly

### "API key is empty"

The environment variable exists but is empty. Set a value:
```bash
export AZURE_OPENAI_API_KEY="your-key-here"
```

### "base_url is required when provider=azure"

For Azure, you must specify the endpoint:
```yaml
llm:
  provider: azure
  base_url: https://your-resource.openai.azure.com/
```

### Rate Limit Errors

The adapter retries automatically with exponential backoff. If you still get rate limit errors:
1. Increase `max_retries` in config
2. Reduce request frequency
3. Check your Azure/OpenAI quota
