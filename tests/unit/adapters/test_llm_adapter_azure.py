"""Tests for AzureOpenAIAdapter.

TDD Phase: RED - These tests should fail until T017 is implemented.

Tests cover:
- T016: DI pattern with ConfigurationService per AC9
- T016: Rejects empty API key and base_url per Insight 04
- T016: Content filter handling returns was_filtered=True per AC6
- T016: Case-insensitive content filter detection per Insight 05
- T016: Uses azure_deployment_name and azure_api_version
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# T016: DI Pattern and Validation Tests


@pytest.mark.unit
def test_azure_adapter_receives_config_service():
    """AzureOpenAIAdapter receives ConfigurationService.

    Purpose: Proves DI pattern per AC9
    Quality Contribution: Ensures clean architecture compliance
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="test-key",
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
    )

    adapter = AzureOpenAIAdapter(mock_config)
    assert adapter is not None


@pytest.mark.unit
def test_azure_adapter_rejects_empty_api_key():
    """AzureOpenAIAdapter rejects empty API key.

    Purpose: Proves empty key validation per Insight 04
    Quality Contribution: Catches empty env var before cryptic 401
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="",  # Empty!
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
    )

    with pytest.raises(LLMAdapterError) as exc_info:
        AzureOpenAIAdapter(mock_config)

    assert "empty" in str(exc_info.value).lower()


@pytest.mark.unit
def test_azure_adapter_rejects_empty_base_url():
    """AzureOpenAIAdapter rejects empty base_url.

    Purpose: Proves empty endpoint validation per Insight 04
    Quality Contribution: Catches empty endpoint before cryptic error

    Note: LLMConfig's model validator catches empty base_url for azure provider.
    This test verifies the adapter's own validation works if config bypassed.
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.exceptions import LLMAdapterError
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    # Create config with openai provider (bypasses azure validation)
    # then manually set base_url to empty to test adapter validation
    mock_config = MagicMock(spec=ConfigurationService)
    llm_config = LLMConfig(
        provider="openai",  # Use openai to bypass azure field validation
        api_key="test-key",
    )
    # Manually override to simulate misconfiguration
    object.__setattr__(llm_config, "base_url", "")
    mock_config.require.return_value = llm_config

    with pytest.raises(LLMAdapterError) as exc_info:
        AzureOpenAIAdapter(mock_config)

    assert (
        "base_url" in str(exc_info.value).lower()
        or "endpoint" in str(exc_info.value).lower()
    )


@pytest.mark.unit
def test_azure_adapter_provider_name():
    """AzureOpenAIAdapter provider_name returns 'azure'.

    Purpose: Proves provider identification
    Quality Contribution: Documents expected provider name
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="test-key",
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
    )

    adapter = AzureOpenAIAdapter(mock_config)
    assert adapter.provider_name == "azure"


# T016: Content Filter Handling Tests


@pytest.mark.unit
async def test_azure_adapter_content_filter_returns_was_filtered():
    """Azure content filter returns was_filtered=True.

    Purpose: Proves graceful content filter handling per AC6
    Quality Contribution: Enables caller to handle filtered content
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="test-key",
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
    )

    adapter = AzureOpenAIAdapter(mock_config)

    # Create mock error with content_filter
    mock_error = Exception("content_filter triggered")
    mock_error.status_code = 400

    with patch.object(
        adapter,
        "_get_client",
        return_value=MagicMock(
            chat=MagicMock(
                completions=MagicMock(create=AsyncMock(side_effect=mock_error))
            )
        ),
    ):
        response = await adapter.generate("test prompt")

    assert response.was_filtered is True
    assert response.finish_reason == "content_filter"


@pytest.mark.unit
async def test_azure_adapter_content_filter_case_insensitive():
    """Azure content filter detection is case-insensitive.

    Purpose: Proves case-insensitive detection per Insight 05
    Quality Contribution: Handles API response variations
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="test-key",
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
    )

    adapter = AzureOpenAIAdapter(mock_config)

    # Mixed case "Content_Filter"
    mock_error = Exception("Content_Filter policy violation")
    mock_error.status_code = 400

    with patch.object(
        adapter,
        "_get_client",
        return_value=MagicMock(
            chat=MagicMock(
                completions=MagicMock(create=AsyncMock(side_effect=mock_error))
            )
        ),
    ):
        response = await adapter.generate("test prompt")

    assert response.was_filtered is True


@pytest.mark.unit
async def test_azure_adapter_content_filtering_in_message():
    """Azure 'content filtering' (with space) is detected.

    Purpose: Proves multi-pattern detection per Insight 05
    Quality Contribution: Handles different error message formats
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="test-key",
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
    )

    adapter = AzureOpenAIAdapter(mock_config)

    # "content filtering" with space
    mock_error = Exception("Request rejected by content filtering")
    mock_error.status_code = 400

    with patch.object(
        adapter,
        "_get_client",
        return_value=MagicMock(
            chat=MagicMock(
                completions=MagicMock(create=AsyncMock(side_effect=mock_error))
            )
        ),
    ):
        response = await adapter.generate("test prompt")

    assert response.was_filtered is True


@pytest.mark.unit
async def test_azure_adapter_content_filter_no_exception():
    """Azure content filter does NOT raise exception.

    Purpose: Proves graceful handling (no crash) per AC6
    Quality Contribution: Caller can handle filtered content
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="test-key",
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
    )

    adapter = AzureOpenAIAdapter(mock_config)

    mock_error = Exception("content_filter triggered")
    mock_error.status_code = 400

    with patch.object(
        adapter,
        "_get_client",
        return_value=MagicMock(
            chat=MagicMock(
                completions=MagicMock(create=AsyncMock(side_effect=mock_error))
            )
        ),
    ):
        # Should NOT raise - returns response instead
        response = await adapter.generate("test prompt")
        assert response is not None


@pytest.mark.unit
async def test_azure_adapter_successful_generate():
    """AzureOpenAIAdapter successfully generates response.

    Purpose: Proves happy path works
    Quality Contribution: Documents expected behavior
    """
    from fs2.config.objects import LLMConfig
    from fs2.config.service import ConfigurationService
    from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

    mock_config = MagicMock(spec=ConfigurationService)
    mock_config.require.return_value = LLMConfig(
        provider="azure",
        api_key="test-key",
        base_url="https://test.openai.azure.com/",
        azure_deployment_name="gpt-4",
        azure_api_version="2024-12-01-preview",
        temperature=0.1,
        max_tokens=100,
    )

    adapter = AzureOpenAIAdapter(mock_config)

    # Mock successful response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="Hello from Azure!"))]
    mock_response.choices[0].finish_reason = "stop"
    mock_response.usage = MagicMock(total_tokens=20)
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

    assert response.content == "Hello from Azure!"
    assert response.tokens_used == 20
    assert response.model == "gpt-4"
    assert response.provider == "azure"
    assert response.finish_reason == "stop"
    assert response.was_filtered is False


# Azure AD Authentication Tests (AC2, AC3, AC7)


@pytest.mark.unit
class TestAzureAdapterAzureADAuth:
    """Tests for Azure AD credential support in _get_client()."""

    def test_given_no_api_key_and_azure_identity_when_get_client_then_uses_token_provider(
        self,
    ):
        """
        Purpose: Proves Azure AD auth path when api_key absent.
        Quality Contribution: Core AC2 — DefaultAzureCredential flow.
        Acceptance Criteria: AsyncAzureOpenAI called with azure_ad_token_provider, NOT api_key.
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = LLMConfig(
            provider="azure",
            api_key=None,
            base_url="https://test.openai.azure.com/",
            azure_deployment_name="gpt-4",
            azure_api_version="2024-12-01-preview",
        )

        adapter = AzureOpenAIAdapter(mock_config)

        mock_credential = MagicMock()
        mock_token_provider = MagicMock()

        with patch.dict(
            "sys.modules",
            {
                "azure": MagicMock(),
                "azure.identity": MagicMock(
                    DefaultAzureCredential=MagicMock(
                        return_value=mock_credential
                    ),
                    get_bearer_token_provider=MagicMock(
                        return_value=mock_token_provider
                    ),
                ),
            },
        ):
            with patch(
                "fs2.core.adapters.llm_adapter_azure.AsyncAzureOpenAI"
            ) as mock_client_cls:
                adapter._client = None  # force re-creation
                adapter._get_client()

                mock_client_cls.assert_called_once()
                call_kwargs = mock_client_cls.call_args[1]
                assert "api_key" not in call_kwargs
                assert call_kwargs["azure_ad_token_provider"] is mock_token_provider

                # Verify correct scope (per didyouknow #1)
                import sys

                azure_identity = sys.modules["azure.identity"]
                azure_identity.get_bearer_token_provider.assert_called_once_with(
                    mock_credential,
                    "https://cognitiveservices.azure.com/.default",
                )

    def test_given_no_api_key_and_no_azure_identity_when_get_client_then_raises_error(
        self,
    ):
        """
        Purpose: Proves actionable error when azure-identity not installed.
        Quality Contribution: Core AC3 — clear install instructions.
        Acceptance Criteria: LLMAdapterError with 'pip install fs2[azure-ad]' message.
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.exceptions import LLMAdapterError
        from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = LLMConfig(
            provider="azure",
            api_key=None,
            base_url="https://test.openai.azure.com/",
            azure_deployment_name="gpt-4",
            azure_api_version="2024-12-01-preview",
        )

        adapter = AzureOpenAIAdapter(mock_config)

        # Simulate azure-identity not installed
        with patch.dict("sys.modules", {"azure.identity": None}):
            with pytest.raises(LLMAdapterError, match="azure-identity"):
                adapter._client = None
                adapter._get_client()

    def test_given_api_key_when_get_client_then_uses_key_not_token_provider(self):
        """
        Purpose: Proves mutual exclusivity (AC7) — key present means no token provider.
        Quality Contribution: Prevents undefined AsyncAzureOpenAI behavior.
        Acceptance Criteria: api_key passed, azure_ad_token_provider NOT passed.
        """
        from fs2.config.objects import LLMConfig
        from fs2.config.service import ConfigurationService
        from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter

        mock_config = MagicMock(spec=ConfigurationService)
        mock_config.require.return_value = LLMConfig(
            provider="azure",
            api_key="test-key",
            base_url="https://test.openai.azure.com/",
            azure_deployment_name="gpt-4",
            azure_api_version="2024-12-01-preview",
        )

        adapter = AzureOpenAIAdapter(mock_config)

        with patch(
            "fs2.core.adapters.llm_adapter_azure.AsyncAzureOpenAI"
        ) as mock_client_cls:
            adapter._client = None
            adapter._get_client()

            mock_client_cls.assert_called_once()
            call_kwargs = mock_client_cls.call_args[1]
            assert call_kwargs["api_key"] == "test-key"
            assert "azure_ad_token_provider" not in call_kwargs
