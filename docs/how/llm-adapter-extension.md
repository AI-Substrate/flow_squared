# LLM Adapter Extension Guide

This guide explains how to add new LLM providers by implementing the `LLMAdapter` interface.

## Architecture Overview

```
LLMAdapter (ABC)
├── FakeLLMAdapter      # Testing
├── OpenAIAdapter       # OpenAI API
├── AzureOpenAIAdapter  # Azure OpenAI
└── YourNewAdapter      # Your extension
```

## Step 1: Create the Adapter File

Create `src/fs2/core/adapters/llm_adapter_yourprovider.py`:

```python
"""YourProviderAdapter implementation."""

from typing import TYPE_CHECKING

from fs2.config.objects import LLMConfig
from fs2.core.adapters.exceptions import (
    LLMAdapterError,
    LLMAuthenticationError,
    LLMRateLimitError,
)
from fs2.core.adapters.llm_adapter import LLMAdapter
from fs2.core.models.llm_response import LLMResponse

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class YourProviderAdapter(LLMAdapter):
    """Your LLM provider adapter."""

    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize with ConfigurationService."""
        self._config_service = config
        self._llm_config = config.require(LLMConfig)

        # Validate at init time
        if not self._llm_config.api_key:
            raise LLMAdapterError("API key is required")

    @property
    def provider_name(self) -> str:
        """Return your provider name."""
        return "yourprovider"

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a response."""
        try:
            # Call your provider's API
            result = await self._call_api(prompt, max_tokens, temperature)

            return LLMResponse(
                content=result.text,
                tokens_used=result.tokens,
                model=result.model,
                provider=self.provider_name,
                finish_reason=result.reason,
                was_filtered=False,
            )

        except YourProviderAuthError as e:
            raise LLMAuthenticationError(str(e)) from e
        except YourProviderRateLimitError as e:
            raise LLMRateLimitError(str(e)) from e
        except Exception as e:
            raise LLMAdapterError(f"API error: {e}") from e
```

## Step 2: Add to Factory

Update `LLMService.create()` in `src/fs2/core/services/llm_service.py`:

```python
from fs2.core.adapters.llm_adapter_yourprovider import YourProviderAdapter

@classmethod
def create(cls, config: "ConfigurationService") -> "LLMService":
    llm_config = config.require(LLMConfig)

    if llm_config.provider == "yourprovider":
        adapter = YourProviderAdapter(config)
    elif llm_config.provider == "azure":
        adapter = AzureOpenAIAdapter(config)
    # ... etc

    return cls(config, adapter)
```

## Step 3: Update LLMConfig Provider Type

Add your provider to the `Literal` type in `src/fs2/config/objects.py`:

```python
class LLMConfig(BaseModel):
    provider: Literal["azure", "openai", "fake", "yourprovider"]
```

## Step 4: Export from Package

Add to `src/fs2/core/adapters/__init__.py`:

```python
from fs2.core.adapters.llm_adapter_yourprovider import YourProviderAdapter

__all__ = [
    # ... existing exports
    "YourProviderAdapter",
]
```

## Step 5: Write Tests

Create `tests/unit/adapters/test_llm_adapter_yourprovider.py`:

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.unit
def test_yourprovider_adapter_receives_config_service():
    """Adapter receives ConfigurationService."""
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_yourprovider import YourProviderAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="yourprovider",
        api_key="test-key",
    )

    adapter = YourProviderAdapter(mock_config)
    assert adapter.provider_name == "yourprovider"


@pytest.mark.unit
async def test_yourprovider_adapter_successful_generate():
    """Adapter generates response successfully."""
    # Mock your provider's SDK
    with patch("your_sdk.call") as mock_call:
        mock_call.return_value = MockResponse(...)

        response = await adapter.generate("Test prompt")

        assert response.content == "Expected content"
        assert response.provider == "yourprovider"
```

## Key Implementation Notes

### 1. ConfigurationService DI Pattern

Always receive `ConfigurationService`, not extracted config:

```python
# CORRECT
def __init__(self, config: "ConfigurationService") -> None:
    self._llm_config = config.require(LLMConfig)

# WRONG
def __init__(self, llm_config: LLMConfig) -> None:
    self._llm_config = llm_config
```

### 2. Status-Code Based Exception Translation

Use status codes, not SDK exception types:

```python
# CORRECT
status_code = getattr(e, "status_code", None)
if status_code == 401:
    raise LLMAuthenticationError(...) from e

# WRONG - couples to SDK exception types
except openai.AuthenticationError as e:
    raise LLMAuthenticationError(...) from e
```

### 3. Async All The Way

All adapter methods must be `async def`:

```python
# CORRECT
async def generate(self, prompt: str, ...) -> LLMResponse:
    result = await self._api_client.call(...)
    return LLMResponse(...)

# WRONG
def generate(self, prompt: str, ...) -> LLMResponse:
    result = self._api_client.call(...)
```

### 4. Retry Logic

Implement exponential backoff for transient errors (429, 502, 503):

```python
RETRYABLE_STATUS_CODES = {429, 502, 503}

for attempt in range(max_retries + 1):
    try:
        return await self._call_api(...)
    except Exception as e:
        status = getattr(e, "status_code", None)
        if status in RETRYABLE_STATUS_CODES and attempt < max_retries:
            delay = 2 * (2 ** attempt) + random.uniform(0, 1)
            await asyncio.sleep(delay)
            continue
        raise
```

### 5. Logging Security

Never log prompt or response content:

```python
# CORRECT
logger.info(f"Generated response: tokens={response.tokens_used}, model={response.model}")

# WRONG - logs potentially sensitive content
logger.info(f"Response: {response.content}")
```

## Provider-Specific Considerations

### Claude/Anthropic

- Uses different message format
- May need to handle system prompts differently
- Consider adding `stop_sequences` support

### Google (Gemini/Vertex AI)

- Different authentication (service accounts vs API keys)
- Add support for `google_project_id`, `google_location`
- Handle safety ratings similar to Azure content filter

### Local Models (Ollama, vLLM)

- No authentication required
- Add support for `model_path` or `model_name`
- Different base URL patterns
