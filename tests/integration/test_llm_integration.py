"""Integration tests for LLM service.

These tests verify the full flow from service to adapter with mocked SDK.
They do NOT call real APIs - SDK is mocked for CI reliability.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.integration
async def test_full_flow_service_to_sdk_mocked():
    """Full flow from LLMService to mocked SDK.

    Purpose: Proves end-to-end flow works with mocked SDK
    Quality Contribution: Validates integration without real API costs
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.services.llm_service import LLMService

    # Setup mock ConfigurationService
    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="test-key",
        model="gpt-4",
        temperature=0.1,
        max_tokens=100,
    )

    # Create service via factory
    service = LLMService.create(mock_config)

    # Mock successful response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Integration test response!"))]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage = MagicMock(total_tokens=25)
    mock_response.model = "gpt-4"

    with patch.object(
        service._adapter, "_get_client", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(create=AsyncMock(return_value=mock_response)))
        )
    ):
        response = await service.generate("Test prompt for integration")

    assert response.content == "Integration test response!"
    assert response.tokens_used == 25
    assert response.model == "gpt-4"
    assert response.provider == "openai"
    assert response.finish_reason == "stop"
    assert response.was_filtered is False


@pytest.mark.integration
async def test_full_flow_azure_content_filter():
    """Full flow for Azure with content filter.

    Purpose: Proves Azure content filter handling through full stack
    Quality Contribution: Validates graceful content filter response
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.services.llm_service import LLMService

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="test-key",
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
    )

    service = LLMService.create(mock_config)

    # Mock content filter error
    mock_error = Exception("content_filter triggered")
    mock_error.status_code = 400

    with patch.object(
        service._adapter, "_get_client", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(create=AsyncMock(side_effect=mock_error)))
        )
    ):
        response = await service.generate("Filtered content")

    assert response.was_filtered is True
    assert response.finish_reason == "content_filter"
    assert response.content == ""


@pytest.mark.integration
async def test_full_flow_with_fake_adapter():
    """Full flow using FakeLLMAdapter.

    Purpose: Proves fake adapter works through service layer
    Quality Contribution: Validates testing infrastructure
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.services.llm_service import LLMService

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(provider="fake")

    service = LLMService.create(mock_config)

    # FakeLLMAdapter's set_response
    service._adapter.set_response("Fake response for testing")

    response = await service.generate("Any prompt")

    assert response.content == "Fake response for testing"
    assert response.provider == "fake"
    assert response.was_filtered is False
