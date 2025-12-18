"""TiktokenTokenCounterAdapter - production TokenCounterAdapter implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fs2.core.adapters.exceptions import TokenCounterError
from fs2.core.adapters.token_counter_adapter import TokenCounterAdapter

if TYPE_CHECKING:
    from fs2.config.service import ConfigurationService


class TiktokenTokenCounterAdapter(TokenCounterAdapter):
    """TokenCounterAdapter backed by `tiktoken`.

    Notes:
    - Caches encoder instance at initialization (per Critical Discovery 05).
    - Translates ALL tokenizer failures to TokenCounterError (adapter boundary).
    """

    def __init__(self, config: ConfigurationService) -> None:
        from fs2.config.objects import LLMConfig

        self._llm_config = config.require(LLMConfig)

        try:
            import tiktoken  # type: ignore[import-not-found]
        except Exception as e:  # pragma: no cover
            raise TokenCounterError(
                "tiktoken is required for token counting but could not be imported. "
                "Install dependencies via `uv sync`."
            ) from e

        model = self._llm_config.model or "gpt-4o-mini"
        self._model = model

        try:
            self._encoder = tiktoken.encoding_for_model(model)
        except Exception:
            try:
                self._encoder = tiktoken.get_encoding("o200k_base")
            except Exception as e:
                raise TokenCounterError(
                    f"Token counter initialization failed for model={model!r}. "
                    "Verify LLMConfig.model is set to a supported OpenAI model name."
                ) from e

    def count_tokens(self, text: str) -> int:
        try:
            return len(self._encoder.encode(text))
        except Exception as e:
            raise TokenCounterError(f"Token counting failed: {e}") from e
