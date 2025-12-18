"""FakeLLMAdapter implementation.

Test double for LLM adapters with explicit control via set_response().
Per AC4: Tests explicitly configure expected response via set_response().
Per Finding 09: Default returns placeholder; tests control output.

Usage:
    adapter = FakeLLMAdapter()
    adapter.set_response("Expected output")
    response = await adapter.generate("Any prompt")
    assert response.content == "Expected output"

    # Error simulation
    adapter.set_error(LLMRateLimitError("Test error"))
    with pytest.raises(LLMRateLimitError):
        await adapter.generate("prompt")

    # Call verification
    await adapter.generate("First", max_tokens=100)
    await adapter.generate("Second")
    assert len(adapter.call_history) == 2
    assert adapter.call_history[0]["max_tokens"] == 100

    # Async delay simulation (for concurrency testing)
    adapter.set_delay(0.1)  # 100ms delay
    # Multiple concurrent calls will demonstrate true parallelism
"""

import asyncio
from typing import Any

from fs2.core.adapters.llm_adapter import LLMAdapter
from fs2.core.models.llm_response import LLMResponse


class FakeLLMAdapter(LLMAdapter):
    """Fake LLM adapter for testing.

    Provides explicit control over responses via set_response() and
    tracks all calls for assertion in tests.

    Attributes:
        call_history: List of all generate() calls with arguments.

    Example:
        >>> adapter = FakeLLMAdapter()
        >>> adapter.set_response("Hello!")
        >>> response = await adapter.generate("Say hi")
        >>> response.content
        'Hello!'
        >>> adapter.call_history
        [{'prompt': 'Say hi', 'max_tokens': None, 'temperature': None}]
    """

    def __init__(self) -> None:
        """Initialize the fake adapter with empty state."""
        self._response_content: str = "[FakeLLMAdapter placeholder response]"
        self._error: Exception | None = None
        self._delay_seconds: float = 0.0
        self.call_history: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        """Return 'fake' as the provider name."""
        return "fake"

    def set_response(self, content: str) -> None:
        """Set the content that generate() will return.

        Args:
            content: The content to return from generate().
        """
        self._response_content = content
        self._error = None  # Clear any error

    def set_error(self, error: Exception) -> None:
        """Set an exception that generate() will raise.

        Args:
            error: The exception to raise from generate().
        """
        self._error = error

    def set_delay(self, seconds: float) -> None:
        """Set an async delay for generate() calls.

        Use this to simulate network latency and verify concurrent
        execution in worker pools (per CD06b).

        Args:
            seconds: Number of seconds to delay each generate() call.

        Example:
            >>> adapter.set_delay(0.1)  # 100ms delay
            >>> # 5 concurrent calls should complete in ~100ms if parallel
            >>> # Would take ~500ms if serialized
        """
        self._delay_seconds = seconds

    def reset(self) -> None:
        """Reset the adapter to its initial state."""
        self._response_content = "[FakeLLMAdapter placeholder response]"
        self._error = None
        self._delay_seconds = 0.0
        self.call_history = []

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a fake response.

        Records the call in call_history and returns the configured
        response or raises the configured error.

        Args:
            prompt: The input prompt (recorded in call_history).
            max_tokens: Max tokens (recorded in call_history).
            temperature: Temperature (recorded in call_history).

        Returns:
            LLMResponse with configured content.

        Raises:
            Exception configured via set_error().
        """
        # Record the call
        self.call_history.append(
            {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )

        # Apply async delay if configured (for concurrency testing)
        if self._delay_seconds > 0:
            await asyncio.sleep(self._delay_seconds)

        # Raise error if configured
        if self._error is not None:
            raise self._error

        # Return configured response
        return LLMResponse(
            content=self._response_content,
            tokens_used=len(self._response_content.split()),  # Simple token estimate
            model="fake-model",
            provider=self.provider_name,
            finish_reason="stop",
            was_filtered=False,
        )
