"""Local Ollama LLM adapter for on-device inference.

Provides LLM generation via Ollama's OpenAI-compatible API with:
- ConfigurationService DI pattern
- Lazy client initialization (DYK-5: hardcoded api_key="ollama")
- Actionable error messages for common Ollama issues
- No API key required (local service)

Requires Ollama running locally: https://ollama.com
"""

import logging

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI

from fs2.config.objects import LLMConfig
from fs2.core.adapters.exceptions import LLMAdapterError
from fs2.core.adapters.llm_adapter import LLMAdapter
from fs2.core.models.llm_response import LLMResponse

logger = logging.getLogger(__name__)

if __name__ != "__main__":
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from fs2.config.service import ConfigurationService


class LocalOllamaAdapter(LLMAdapter):
    """Ollama local LLM adapter.

    Connects to a locally-running Ollama instance via its OpenAI-compatible
    API endpoint. Uses the openai SDK (already a project dependency) with
    a sentinel api_key since Ollama ignores authentication headers.

    Example:
        >>> config_service = FS2ConfigurationService()
        >>> adapter = LocalOllamaAdapter(config_service)
        >>> response = await adapter.generate("Summarize this code")
        >>> response.content
        'This module implements...'
    """

    def __init__(self, config: "ConfigurationService") -> None:
        """Initialize with ConfigurationService.

        Args:
            config: ConfigurationService to get LLMConfig from.
        """
        self._config_service = config
        self._llm_config = config.require(LLMConfig)
        self._client: AsyncOpenAI | None = None

    @property
    def provider_name(self) -> str:
        """Return 'local' as the provider name."""
        return "local"

    def _get_client(self) -> AsyncOpenAI:
        """Get or create the AsyncOpenAI client for Ollama.

        DYK-5: Uses api_key="ollama" sentinel — Ollama ignores auth headers
        but the OpenAI SDK rejects empty strings/None.
        """
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key="ollama",
                base_url=f"{self._llm_config.base_url}/v1",
                timeout=self._llm_config.timeout,
            )
        return self._client

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a response from local Ollama.

        Args:
            prompt: The input prompt.
            max_tokens: Max tokens (uses config default if not specified).
            temperature: Temperature (uses config default if not specified).

        Returns:
            LLMResponse with generated content.

        Raises:
            LLMAdapterError: For connection, model, or generation errors.
        """
        client = self._get_client()

        effective_max_tokens = max_tokens or self._llm_config.max_tokens
        effective_temperature = (
            temperature if temperature is not None else self._llm_config.temperature
        )
        model = self._llm_config.model or "qwen2.5-coder:7b"

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=effective_max_tokens,
                temperature=effective_temperature,
            )

            choice = response.choices[0]
            content = choice.message.content or ""
            finish_reason = choice.finish_reason or "stop"
            tokens_used = response.usage.total_tokens if response.usage else 0

            return LLMResponse(
                content=content,
                tokens_used=tokens_used,
                model=response.model,
                provider=self.provider_name,
                finish_reason=finish_reason,
                was_filtered=False,
            )

        except APITimeoutError as e:
            raise LLMAdapterError(
                f"Ollama request timed out after {self._llm_config.timeout}s. "
                "Try increasing timeout in config or using a smaller model.\n"
                f"  Current model: {model}\n"
                f"  Current timeout: {self._llm_config.timeout}s"
            ) from e

        except APIConnectionError as e:
            raise LLMAdapterError(
                "Cannot connect to Ollama. Ensure Ollama is installed and running.\n"
                "  Install: https://ollama.com/download\n"
                "  Start:   ollama serve\n"
                f"  Endpoint: {self._llm_config.base_url}\n"
                f"  Error:   {e}"
            ) from e

        except Exception as e:
            status_code = getattr(e, "status_code", None)

            if status_code == 404:
                raise LLMAdapterError(
                    f"Model '{model}' not found in Ollama. "
                    f"Pull it with: ollama pull {model}"
                ) from e

            raise LLMAdapterError(
                f"Ollama error: {e}\n  Check that Ollama is running: ollama serve"
            ) from e
