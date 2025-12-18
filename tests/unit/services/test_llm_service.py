"""Tests for LLMService.

TDD Phase: RED - These tests should fail until T019 is implemented.

Tests cover:
- T018: DI pattern with ConfigurationService and adapter per AC9
- T018: Factory creates correct adapter based on provider per AC1
- T018: Delegates to adapter for generate calls
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.unit
def test_llm_service_receives_config_and_adapter():
    """LLMService receives ConfigurationService and adapter.

    Purpose: Proves DI pattern per AC9
    Quality Contribution: Ensures clean architecture compliance
    """
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.services.llm_service import LLMService

    mock_config = MagicMock(spec=ConfigurationService)
    adapter = FakeLLMAdapter()

    service = LLMService(mock_config, adapter)

    assert service is not None


@pytest.mark.unit
async def test_llm_service_delegates_to_adapter():
    """LLMService delegates generate() to adapter.

    Purpose: Proves composition pattern
    Quality Contribution: Validates service/adapter separation
    """
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.services.llm_service import LLMService

    mock_config = MagicMock(spec=ConfigurationService)
    adapter = FakeLLMAdapter()
    adapter.set_response("Expected response")

    service = LLMService(mock_config, adapter)
    response = await service.generate("Test prompt")

    assert response.content == "Expected response"
    assert len(adapter.call_history) == 1
    assert adapter.call_history[0]["prompt"] == "Test prompt"


@pytest.mark.unit
def test_llm_service_factory_creates_openai():
    """Factory creates OpenAIAdapter for provider=openai.

    Purpose: Proves factory method per AC1
    Quality Contribution: Validates provider switching
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter
    from fs2.core.services.llm_service import LLMService

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="openai",
        api_key="test-key",
    )

    service = LLMService.create(mock_config)

    assert isinstance(service._adapter, OpenAIAdapter)


@pytest.mark.unit
def test_llm_service_factory_creates_azure():
    """Factory creates AzureOpenAIAdapter for provider=azure.

    Purpose: Proves factory method per AC1
    Quality Contribution: Validates provider switching
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter
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

    assert isinstance(service._adapter, AzureOpenAIAdapter)


@pytest.mark.unit
def test_llm_service_factory_creates_fake():
    """Factory creates FakeLLMAdapter for provider=fake.

    Purpose: Proves factory method supports test double
    Quality Contribution: Enables testing without real API
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.services.llm_service import LLMService

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="fake",
    )

    service = LLMService.create(mock_config)

    assert isinstance(service._adapter, FakeLLMAdapter)
