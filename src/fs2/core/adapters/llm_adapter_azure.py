"""AzureOpenAIAdapter implementation.

Azure OpenAI API integration with content filter handling.
Per AC6: Content filter returns was_filtered=True instead of raising.
Per AC9: Receives ConfigurationService, not extracted config.
Per Insight 02: Maps base_url to azure_endpoint for SDK.
Per Insight 04: Validates api_key and base_url not empty.
Per Insight 05: Case-insensitive multi-pattern content filter detection.
"""

import asyncio
import logging
import random
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from openai import AsyncAzureOpenAI

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


class AzureOpenAIAdapter(LLMAdapter):
    """Azure OpenAI API adapter.

    Provides LLM generation via Azure OpenAI's API with:
    - ConfigurationService DI pattern
    - Graceful content filter handling (returns was_filtered=True)
    - Exponential backoff retry on transient errors
    - Status-code-based exception translation

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> adapter = AzureOpenAIAdapter(config_service)
        >>> response = await adapter.generate("Hello!")
        >>> if response.was_filtered:
        ...     print("Content was filtered")
        >>> else:
        ...     print(response.content)
    """

    # Status codes that trigger retry with backoff
    RETRYABLE_STATUS_CODES = {429, 502, 503}

    # Content filter detection patterns (case-insensitive)
    CONTENT_FILTER_PATTERNS = ("content_filter", "content filtering")

    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize the adapter with ConfigurationService.

        Args:
            config: ConfigurationService to get LLMConfig from.

        Raises:
            LLMAdapterError: If API key or base_url is empty or contains placeholder.
        """
        self._config_service = config
        self._llm_config = config.require(LLMConfig)
        self._client: AsyncAzureOpenAI | None = None

        # Validate API key at init time per Insight 04
        api_key = self._llm_config.api_key
        if api_key is not None:
            if "${" in api_key:
                raise LLMAdapterError(
                    f"API key contains unexpanded placeholder: {api_key}. "
                    "Ensure the environment variable is set."
                )
            if not api_key:
                raise LLMAdapterError(
                    "API key is empty. Check that the environment variable is set "
                    "and contains a value."
                )

        # Validate base_url (Azure endpoint)
        base_url = self._llm_config.base_url
        if not base_url:
            raise LLMAdapterError(
                "base_url (Azure endpoint) is empty. "
                "Set base_url to your Azure OpenAI endpoint URL."
            )

    @property
    def provider_name(self) -> str:
        """Return 'azure' as the provider name."""
        return "azure"

    def _get_client(self) -> AsyncAzureOpenAI:
        """Get or create the Azure OpenAI client.

        Note: Per Insight 02, base_url is mapped to azure_endpoint.

        Returns:
            AsyncAzureOpenAI client configured for the deployment.
        """
        if self._client is None:
            self._client = AsyncAzureOpenAI(
                api_key=self._llm_config.api_key,
                azure_endpoint=self._llm_config.base_url,  # Maps base_url → azure_endpoint
                api_version=self._llm_config.azure_api_version,
                timeout=self._llm_config.timeout,
            )
        return self._client

    def _is_content_filter_error(self, error: Exception) -> bool:
        """Check if the error is a content filter rejection.

        Per Insight 05: Case-insensitive multi-pattern detection.

        Args:
            error: The exception to check.

        Returns:
            True if this is a content filter error.
        """
        error_str = str(error).lower()
        return any(pattern in error_str for pattern in self.CONTENT_FILTER_PATTERNS)

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a response from Azure OpenAI.

        Args:
            prompt: The input prompt.
            max_tokens: Max tokens (uses config default if not specified).
            temperature: Temperature (uses config default if not specified).

        Returns:
            LLMResponse with generated content. If content was filtered,
            returns was_filtered=True with empty content.

        Raises:
            LLMAuthenticationError: For HTTP 401.
            LLMRateLimitError: After max retries exceeded on HTTP 429.
            LLMAdapterError: For other errors.
        """
        client = self._get_client()

        # Use config defaults if not specified
        effective_max_tokens = max_tokens or self._llm_config.max_tokens
        effective_temperature = temperature if temperature is not None else self._llm_config.temperature
        deployment = self._llm_config.azure_deployment_name

        # Retry loop with exponential backoff
        last_error: Exception | None = None
        for attempt in range(self._llm_config.max_retries + 1):
            try:
                response = await client.chat.completions.create(
                    model=deployment,
                    messages=[{"role": "user", "content": prompt}],
                    max_completion_tokens=effective_max_tokens,
                    temperature=effective_temperature,
                )

                # Extract response data
                choice = response.choices[0]
                content = choice.message.content or ""
                finish_reason = choice.finish_reason or "stop"
                tokens_used = response.usage.total_tokens if response.usage else 0

                # Treat empty response as retryable (API may be overloaded)
                if not content.strip():
                    if attempt < self._llm_config.max_retries:
                        delay = 2 * (2**attempt) + random.uniform(0, 1)
                        logger.warning(
                            "Empty response from Azure OpenAI (attempt %d/%d), retrying in %.1fs",
                            attempt + 1,
                            self._llm_config.max_retries + 1,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise LLMAdapterError(
                            f"LLM returned empty response after {self._llm_config.max_retries + 1} attempts"
                        )

                return LLMResponse(
                    content=content,
                    tokens_used=tokens_used,
                    model=response.model,
                    provider=self.provider_name,
                    finish_reason=finish_reason,
                    was_filtered=False,
                )

            except Exception as e:
                last_error = e
                status_code = getattr(e, "status_code", None)

                # Check for content filter (400 + content_filter pattern)
                if status_code == 400 and self._is_content_filter_error(e):
                    # Return graceful response per AC6
                    return LLMResponse(
                        content="",
                        tokens_used=0,
                        model=self._llm_config.model or deployment or "unknown",
                        provider=self.provider_name,
                        finish_reason="content_filter",
                        was_filtered=True,
                    )

                # Translate status codes to domain exceptions
                if status_code == 401:
                    raise LLMAuthenticationError(
                        "Authentication failed. Check your API key."
                    ) from e

                # Check if retryable
                if status_code in self.RETRYABLE_STATUS_CODES:
                    if attempt < self._llm_config.max_retries:
                        # Calculate backoff: base * 2^attempt + jitter
                        delay = 2 * (2**attempt) + random.uniform(0, 1)
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Max retries exceeded
                        raise LLMRateLimitError(
                            f"Rate limit exceeded after {self._llm_config.max_retries} retries."
                        ) from e

                # Non-retryable error
                raise LLMAdapterError(f"Azure OpenAI API error: {e}") from e

        # Should not reach here, but just in case
        raise LLMAdapterError(f"Unexpected error: {last_error}") from last_error
