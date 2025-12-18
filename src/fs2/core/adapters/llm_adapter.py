"""LLMAdapter ABC interface.

Provides the abstract interface for LLM provider adapters.
Per AC10: All methods are async def.
Per AC9: Implementations receive ConfigurationService.

Architecture:
- This file: ABC definition only
- Implementations: llm_adapter_fake.py, llm_adapter_openai.py, llm_adapter_azure.py

Pattern demonstrates:
- Async-first design for I/O-bound LLM operations
- Provider abstraction for swappable implementations
- ConfigurationService DI pattern
"""

from abc import ABC, abstractmethod

from fs2.core.models.llm_response import LLMResponse


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters.

    This interface defines the contract for all LLM adapters,
    enabling provider-agnostic LLM operations.

    All methods are async to support efficient I/O handling
    for LLM API calls.

    Implementations:
    - FakeLLMAdapter: Test double with set_response() pattern
    - OpenAIAdapter: OpenAI API integration
    - AzureOpenAIAdapter: Azure OpenAI API integration

    Example:
        >>> class MyAdapter(LLMAdapter):
        ...     @property
        ...     def provider_name(self) -> str:
        ...         return "my-provider"
        ...
        ...     async def generate(self, prompt: str, **kwargs) -> LLMResponse:
        ...         return LLMResponse(
        ...             content="response",
        ...             tokens_used=10,
        ...             model="my-model",
        ...             provider=self.provider_name,
        ...             finish_reason="stop",
        ...         )
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for this adapter.

        Used to identify the provider in LLMResponse and logging.

        Returns:
            Provider name string (e.g., "openai", "azure", "fake").
        """
        ...

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            prompt: The input prompt to send to the LLM.
            max_tokens: Maximum tokens to generate (optional, uses config default).
            temperature: Generation temperature (optional, uses config default).

        Returns:
            LLMResponse with generated content and metadata.

        Raises:
            LLMAdapterError: For generic LLM failures.
            LLMAuthenticationError: For authentication failures (HTTP 401).
            LLMRateLimitError: After max retries exceeded (HTTP 429).
            LLMContentFilterError: If content filter triggered and not gracefully handled.
        """
        ...
