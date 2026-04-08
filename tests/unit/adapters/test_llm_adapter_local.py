"""Tests for LocalOllamaAdapter — plan 034.

Tests cover:
- Provider name identification (AC02)
- Successful generation via OpenAI SDK (AC02)
- Connection refused error translation (AC04) — uses real APIConnectionError
- Model not found with pull suggestion (AC05)
- HTTP error translation (AC08)
- Timeout error clarity (AC12) — uses real APITimeoutError
- ConfigurationService DI pattern (AC09)
- Config base_url and model usage
- Null usage handling (DYK-3)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIConnectionError, APITimeoutError


def _make_local_config():
    """Create a mock ConfigurationService with local LLM config."""
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="local",
        base_url="http://localhost:11434",
        model="qwen2.5-coder:7b",
    )
    return mock_config


def _mock_client(side_effect=None, return_value=None):
    """Create a mock OpenAI client with given behavior."""
    kwargs = {}
    if side_effect is not None:
        kwargs["side_effect"] = side_effect
    if return_value is not None:
        kwargs["return_value"] = return_value
    return MagicMock(chat=MagicMock(completions=MagicMock(create=AsyncMock(**kwargs))))


def _mock_response(
    content="Summary", tokens=25, model="qwen2.5-coder:7b", usage_none=False
):
    """Create a mock chat completion response."""
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    resp.choices[0].finish_reason = "stop"
    resp.usage = None if usage_none else MagicMock(total_tokens=tokens)
    resp.model = model
    return resp


@pytest.mark.unit
def test_local_adapter_provider_name_is_local():
    """LocalOllamaAdapter provider_name returns 'local'.

    Purpose: Proves provider identification per AC02
    Quality Contribution: Documents expected provider name
    """
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    adapter = LocalOllamaAdapter(_make_local_config())
    assert adapter.provider_name == "local"


@pytest.mark.unit
def test_local_adapter_receives_config_service():
    """LocalOllamaAdapter receives ConfigurationService (DI pattern).

    Purpose: Proves DI pattern per AC09
    Quality Contribution: Ensures clean architecture compliance
    """
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    mock_config = _make_local_config()
    adapter = LocalOllamaAdapter(mock_config)

    assert adapter is not None
    mock_config.require.assert_called()


@pytest.mark.unit
def test_local_adapter_uses_config_base_url_and_model():
    """LocalOllamaAdapter uses base_url and model from config.

    Purpose: Proves config values are respected
    Quality Contribution: Validates config integration
    """
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    adapter = LocalOllamaAdapter(_make_local_config())
    assert adapter._llm_config.base_url == "http://localhost:11434"
    assert adapter._llm_config.model == "qwen2.5-coder:7b"


@pytest.mark.unit
async def test_local_adapter_generate_returns_llm_response():
    """LocalOllamaAdapter.generate() returns valid LLMResponse.

    Purpose: Proves happy path per AC02
    Quality Contribution: Documents expected response structure
    """
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    adapter = LocalOllamaAdapter(_make_local_config())

    with patch.object(
        adapter,
        "_get_client",
        return_value=_mock_client(
            return_value=_mock_response("This is a summary.", 25)
        ),
    ):
        response = await adapter.generate("Summarize this code")

    assert response.content == "This is a summary."
    assert response.tokens_used == 25
    assert response.model == "qwen2.5-coder:7b"
    assert response.provider == "local"
    assert response.finish_reason == "stop"
    assert response.was_filtered is False


@pytest.mark.unit
async def test_local_adapter_generate_handles_null_usage():
    """LocalOllamaAdapter handles response.usage=None gracefully (DYK-3).

    Purpose: Proves null-safety for Ollama usage field
    Quality Contribution: Handles Ollama API quirks
    """
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    adapter = LocalOllamaAdapter(_make_local_config())

    with patch.object(
        adapter,
        "_get_client",
        return_value=_mock_client(return_value=_mock_response(usage_none=True)),
    ):
        response = await adapter.generate("Summarize")

    assert response.tokens_used == 0


@pytest.mark.unit
async def test_local_adapter_connection_refused_raises_adapter_error():
    """APIConnectionError → LLMAdapterError with actionable Ollama message.

    Purpose: Proves error translation per AC04 using real SDK exception
    Quality Contribution: Users get "install Ollama" message, not raw exception
    """
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    adapter = LocalOllamaAdapter(_make_local_config())
    sdk_error = APIConnectionError(request=MagicMock())

    with (
        patch.object(
            adapter, "_get_client", return_value=_mock_client(side_effect=sdk_error)
        ),
        pytest.raises(LLMAdapterError) as exc_info,
    ):
        await adapter.generate("test")

    error_msg = str(exc_info.value).lower()
    assert "ollama" in error_msg
    assert "install" in error_msg or "start" in error_msg or "serve" in error_msg


@pytest.mark.unit
async def test_local_adapter_model_not_found_suggests_pull():
    """Model not found → error suggests 'ollama pull <model>'.

    Purpose: Proves actionable error per AC05
    Quality Contribution: Users know how to fix missing model
    """
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    adapter = LocalOllamaAdapter(_make_local_config())
    mock_error = Exception("model 'qwen2.5-coder:7b' not found")
    mock_error.status_code = 404

    with (
        patch.object(
            adapter, "_get_client", return_value=_mock_client(side_effect=mock_error)
        ),
        pytest.raises(LLMAdapterError) as exc_info,
    ):
        await adapter.generate("test")

    assert "ollama pull" in str(exc_info.value).lower()


@pytest.mark.unit
async def test_local_adapter_timeout_raises_clear_error():
    """APITimeoutError → clear timeout error (not generic connection error).

    Purpose: Proves timeout clarity per AC12 using real SDK exception
    Quality Contribution: Users know to increase timeout, not debug connection
    """
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    adapter = LocalOllamaAdapter(_make_local_config())
    sdk_error = APITimeoutError(request=MagicMock())

    with (
        patch.object(
            adapter, "_get_client", return_value=_mock_client(side_effect=sdk_error)
        ),
        pytest.raises(LLMAdapterError) as exc_info,
    ):
        await adapter.generate("test")

    error_msg = str(exc_info.value).lower()
    assert "timeout" in error_msg


@pytest.mark.unit
async def test_local_adapter_http_error_translates_to_adapter_error():
    """HTTP errors translate to LLMAdapterError (not raw exceptions).

    Purpose: Proves error translation per AC08
    Quality Contribution: Domain-specific errors, no SDK leakage
    """
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

    adapter = LocalOllamaAdapter(_make_local_config())
    mock_error = Exception("Internal server error")
    mock_error.status_code = 500

    with (
        patch.object(
            adapter, "_get_client", return_value=_mock_client(side_effect=mock_error)
        ),
        pytest.raises(LLMAdapterError),
    ):
        await adapter.generate("test")
