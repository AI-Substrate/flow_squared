"""LLMService for provider-agnostic LLM access.

Provides a high-level service for LLM operations with:
- Factory method to create service with appropriate adapter
- ConfigurationService DI pattern
- Provider-agnostic interface

Per AC1: Provider switching via config only.
Per AC9: Receives ConfigurationService, not extracted config.
"""

from typing import TYPE_CHECKING

from fs2.config.objects import LLMConfig
from fs2.core.adapters.llm_adapter import LLMAdapter
from fs2.core.adapters.llm_adapter_azure import AzureOpenAIAdapter
from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
from fs2.core.adapters.llm_adapter_openai import OpenAIAdapter
from fs2.core.models.llm_response import LLMResponse

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class LLMService:
    """Service for provider-agnostic LLM access.

    Provides a high-level interface for LLM operations,
    abstracting away provider-specific details.

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> service = LLMService.create(config_service)
        >>> response = await service.generate("Summarize this code...")
        >>> print(response.content)

    Or with explicit adapter:
        >>> adapter = FakeLLMAdapter()
        >>> adapter.set_response("Expected output")
        >>> service = LLMService(config_service, adapter)
        >>> response = await service.generate("Test")
    """

    def __init__(
        self,
        config: "ConfigurationService",
        adapter: LLMAdapter,
    ) -> None:
        """Initialize the service with config and adapter.

        Args:
            config: ConfigurationService for accessing configuration.
            adapter: LLMAdapter implementation to use.
        """
        self._config = config
        self._adapter = adapter

    @classmethod
    def create(cls, config: "ConfigurationService") -> "LLMService":
        """Factory method to create service with appropriate adapter.

        Creates the correct adapter based on the provider setting
        in LLMConfig.

        Args:
            config: ConfigurationService to get configuration from.

        Returns:
            LLMService configured with the appropriate adapter.
        """
        llm_config = config.require(LLMConfig)

        if llm_config.provider == "azure":
            adapter = AzureOpenAIAdapter(config)
        elif llm_config.provider == "openai":
            adapter = OpenAIAdapter(config)
        elif llm_config.provider == "local":
            from fs2.core.adapters.llm_adapter_local import LocalOllamaAdapter

            adapter = LocalOllamaAdapter(config)
        elif llm_config.provider == "fake":
            adapter = FakeLLMAdapter()
        else:
            # Should not happen due to Pydantic validation
            raise ValueError(f"Unknown provider: {llm_config.provider}")

        return cls(config, adapter)

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The input prompt.
            max_tokens: Maximum tokens to generate (optional).
            temperature: Generation temperature (optional).

        Returns:
            LLMResponse with generated content.
        """
        return await self._adapter.generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
