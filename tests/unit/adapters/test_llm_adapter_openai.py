"""Tests for OpenAIAdapter.

TDD Phase: RED - These tests should fail until T015 is implemented.

Tests cover:
- T013: DI pattern with ConfigurationService per AC9
- T013: Rejects unexpanded placeholders
- T013: Rejects empty API key per Insight 04
- T014: Retry on 429 with exponential backoff per AC5
- T014: Status-code-based exception translation per AC7
- T014: No SDK exception imports per AC7
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# T013: DI Pattern Tests


@pytest.mark.unit
def test_openai_adapter_receives_config_service():
    """OpenAIAdapter receives ConfigurationService (not extracted config).

    Purpose: Proves DI pattern per AC9
    Quality Contribution: Ensures clean architecture compliance
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    # Create mock ConfigurationService
    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="test-key",
    )

    # Should not raise
    adapter = OpenAIAdapter(mock_config)

    assert adapter is not None


@pytest.mark.unit
def test_openai_adapter_rejects_unexpanded_placeholder():
    """OpenAIAdapter rejects unexpanded ${VAR} placeholders.

    Purpose: Proves runtime validation of placeholders
    Quality Contribution: Catches misconfiguration before API call
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="${OPENAI_API_KEY}",  # Unexpanded!
    )

    with pytest.raises(LLMAdapterError) as exc_info:
        OpenAIAdapter(mock_config)

    assert "unexpanded" in str(exc_info.value).lower() or "${" in str(exc_info.value)


@pytest.mark.unit
def test_openai_adapter_rejects_empty_api_key():
    """OpenAIAdapter rejects empty API key.

    Purpose: Proves empty key validation per Insight 04
    Quality Contribution: Catches empty env var before cryptic 401
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="",  # Empty!
    )

    with pytest.raises(LLMAdapterError) as exc_info:
        OpenAIAdapter(mock_config)

    assert "empty" in str(exc_info.value).lower()


@pytest.mark.unit
def test_openai_adapter_provider_name():
    """OpenAIAdapter provider_name returns 'openai'.

    Purpose: Proves provider identification
    Quality Contribution: Documents expected provider name
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="test-key",
    )

    adapter = OpenAIAdapter(mock_config)
    assert adapter.provider_name == "openai"


# T014: Retry and Error Translation Tests


@pytest.mark.unit
async def test_openai_adapter_retries_on_429():
    """OpenAIAdapter retries on HTTP 429 (rate limit).

    Purpose: Proves retry logic per AC5
    Quality Contribution: Validates resilience to rate limits
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="test-key",
        max_retries=3,
    )

    adapter = OpenAIAdapter(mock_config)

    # Create mock error with status_code=429
    mock_error = Exception("Rate limited")
    mock_error.status_code = 429

    # Mock the client to fail twice then succeed
    call_count = 0

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise mock_error
        # Success on third try
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Success"))]
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock(total_tokens=10)
        mock_response.model = "gpt-4"
        return mock_response

    with patch.object(
        adapter,
        "_get_client",
        return_value=MagicMock(
            chat=MagicMock(
                completions=MagicMock(create=AsyncMock(side_effect=mock_create))
            )
        ),
    ):
        response = await adapter.generate("test prompt")

    assert call_count == 3
    assert response.content == "Success"


@pytest.mark.unit
async def test_openai_adapter_translates_401_to_auth_error():
    """OpenAIAdapter translates HTTP 401 to LLMAuthenticationError.

    Purpose: Proves status-code-based exception translation per AC7
    Quality Contribution: Provides domain-specific errors
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.exceptions import LLMAuthenticationError
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="invalid-key",
    )

    adapter = OpenAIAdapter(mock_config)

    # Create mock error with status_code=401
    mock_error = Exception("Unauthorized")
    mock_error.status_code = 401

    with (
        patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                chat=MagicMock(
                    completions=MagicMock(create=AsyncMock(side_effect=mock_error))
                )
            ),
        ),
        pytest.raises(LLMAuthenticationError),
    ):
        await adapter.generate("test prompt")


@pytest.mark.unit
async def test_openai_adapter_translates_429_to_rate_limit_error_after_max_retries():
    """OpenAIAdapter raises LLMRateLimitError after max retries.

    Purpose: Proves error escalation after retries
    Quality Contribution: Prevents infinite retry loops
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.exceptions import LLMRateLimitError
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="test-key",
        max_retries=2,  # Only 2 retries
    )

    adapter = OpenAIAdapter(mock_config)

    # Create mock error with status_code=429
    mock_error = Exception("Rate limited")
    mock_error.status_code = 429

    with (
        patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                chat=MagicMock(
                    completions=MagicMock(create=AsyncMock(side_effect=mock_error))
                )
            ),
        ),
        pytest.raises(LLMRateLimitError),
    ):
        await adapter.generate("test prompt")


@pytest.mark.unit
async def test_openai_adapter_handles_missing_status_code():
    """OpenAIAdapter handles exceptions without status_code attribute.

    Purpose: Proves defensive handling per Insight 03
    Quality Contribution: Handles connection errors gracefully
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="test-key",
    )

    adapter = OpenAIAdapter(mock_config)

    # Error without status_code (e.g., connection error)
    mock_error = Exception("Connection failed")

    with (
        patch.object(
            adapter,
            "_get_client",
            return_value=MagicMock(
                chat=MagicMock(
                    completions=MagicMock(create=AsyncMock(side_effect=mock_error))
                )
            ),
        ),
        pytest.raises(LLMAdapterError),
    ):
        await adapter.generate("test prompt")


@pytest.mark.unit
async def test_openai_adapter_successful_generate():
    """OpenAIAdapter successfully generates response.

    Purpose: Proves happy path works
    Quality Contribution: Documents expected behavior
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="test-key",
        model="gpt-4",
        temperature=0.1,
        max_tokens=100,
    )

    adapter = OpenAIAdapter(mock_config)

    # Mock successful response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Hello, world!"))]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage = MagicMock(total_tokens=15)
    mock_response.model = "gpt-4"

    with patch.object(
        adapter,
        "_get_client",
        return_value=MagicMock(
            chat=MagicMock(
                completions=MagicMock(create=AsyncMock(return_value=mock_response))
            )
        ),
    ):
        response = await adapter.generate("Say hello")

    assert response.content == "Hello, world!"
    assert response.tokens_used == 15
    assert response.model == "gpt-4"
    assert response.provider == "openai"
    assert response.finish_reason == "stop"
    assert response.was_filtered is False
