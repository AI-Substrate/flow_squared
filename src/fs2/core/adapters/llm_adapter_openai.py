"""OpenAIAdapter implementation.

OpenAI API integration with retry logic and status-code-based error translation.
Per AC5: Exponential backoff retry on 429/502/503.
Per AC7: Status-code-based exception translation (no SDK exception imports).
Per AC9: Receives ConfigurationService, not extracted config.
Per Insight 03: getattr(e, 'status_code', None) for defensive error handling.
Per Insight 04: Validate api_key not empty at init.
"""

import asyncio
import logging
import random
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

from openai import AsyncOpenAI

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


class OpenAIAdapter(LLMAdapter):
    """OpenAI API adapter.

    Provides LLM generation via OpenAI's API with:
    - ConfigurationService DI pattern
    - Exponential backoff retry on transient errors (429, 502, 503)
    - Status-code-based exception translation
    - Lazy client initialization

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> adapter = OpenAIAdapter(config_service)
        >>> response = await adapter.generate("Hello!")
        >>> response.content
        'Hi there!'
    """

    # Status codes that trigger retry with backoff
    RETRYABLE_STATUS_CODES = {429, 502, 503}

    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize the adapter with ConfigurationService.

        Args:
            config: ConfigurationService to get LLMConfig from.

        Raises:
            LLMAdapterError: If API key contains unexpanded placeholder or is empty.
        """
        self._config_service = config
        self._llm_config = config.require(LLMConfig)
        self._client: AsyncOpenAI | None = None

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

    @property
    def provider_name(self) -> str:
        """Return 'openai' as the provider name."""
        return "openai"

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the OpenAI client.

        Returns:
            AsyncOpenAI client configured with API key and optional base URL.
        """
        if self._client is None:
            kwargs = {"api_key": self._llm_config.api_key}
            if self._llm_config.base_url:
                kwargs["base_url"] = self._llm_config.base_url
            if self._llm_config.timeout:
                kwargs["timeout"] = self._llm_config.timeout
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a response from OpenAI.

        Args:
            prompt: The input prompt.
            max_tokens: Max tokens (uses config default if not specified).
            temperature: Temperature (uses config default if not specified).

        Returns:
            LLMResponse with generated content.

        Raises:
            LLMAuthenticationError: For HTTP 401.
            LLMRateLimitError: After max retries exceeded on HTTP 429.
            LLMAdapterError: For other errors.
        """
        client = self._get_client()

        # Use config defaults if not specified
        effective_max_tokens = max_tokens or self._llm_config.max_tokens
        effective_temperature = (
            temperature if temperature is not None else self._llm_config.temperature
        )
        model = self._llm_config.model or "gpt-4"

        # Retry loop with exponential backoff
        last_error: Exception | None = None
        for attempt in range(self._llm_config.max_retries + 1):
            try:
                response = await client.chat.completions.create(
                    model=model,
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
                            "Empty response from OpenAI (attempt %d/%d), retrying in %.1fs",
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
                raise LLMAdapterError(f"OpenAI API error: {e}") from e

        # Should not reach here, but just in case
        raise LLMAdapterError(f"Unexpected error: {last_error}") from last_error
