"""FakeLLMAdapter implementation.

Test double for LLM adapters with explicit control via set_response().
Per AC4: Tests explicitly configure expected response via set_response().
Per Finding 09: Default returns placeholder; tests control output.
Per DYK-1: Uses extract_code_from_prompt() to find code blocks for smart_content lookup.

Usage:
    adapter = FakeLLMAdapter()
    adapter.set_response("Expected output")
    response = await adapter.generate("Any prompt")
    assert response.content == "Expected output"

    # Fixture-backed lookup (Subtask 001)
    index = FixtureIndex.from_nodes(nodes)
    adapter = FakeLLMAdapter(fixture_index=index)
    prompt = '''```python
    def add(a, b): return a + b
    ```'''
    response = await adapter.generate(prompt)
    # Returns pre-computed smart_content from fixture graph

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

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fs2.core.adapters.llm_adapter import LLMAdapter
from fs2.core.models.llm_response import LLMResponse

if TYPE_CHECKING:
    from fs2.core.models.fixture_index import FixtureIndex


class FakeLLMAdapter(LLMAdapter):
    """Fake LLM adapter for testing.

    Provides explicit control over responses via set_response() and
    tracks all calls for assertion in tests.

    Features:
    - set_response(): Configure a fixed response (highest priority)
    - fixture_index: Optional FixtureIndex for smart_content lookup via code extraction
    - set_error(): Configure an exception to raise
    - call_history: Track all generate() calls for assertions
    - set_delay(): Simulate network latency for concurrency testing

    Priority order (Subtask 001):
    1. set_response() - explicit test control always wins
    2. fixture_index lookup - returns pre-computed smart_content for code
    3. Placeholder fallback - default response

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

        >>> # With fixture_index
        >>> index = FixtureIndex.from_nodes(nodes)
        >>> adapter = FakeLLMAdapter(fixture_index=index)
        >>> prompt = "```python\\ndef add(a, b): return a + b\\n```"
        >>> response = await adapter.generate(prompt)
        >>> # Returns smart_content from fixture for the extracted code
    """

    def __init__(self, fixture_index: "FixtureIndex | None" = None) -> None:
        """Initialize the fake adapter with optional fixture index.

        Args:
            fixture_index: Optional FixtureIndex for smart_content lookup.
                          When provided, generate() will extract code blocks
                          from prompts and look up smart_content before
                          falling back to placeholder.
        """
        self._fixture_index = fixture_index
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

    def _lookup_fixture_smart_content(self, prompt: str) -> str | None:
        """Look up smart_content from fixture_index by extracting code from prompt.

        Per DYK-1: Prompts contain templates/instructions with code blocks.
        We extract the code from markdown fences and look up smart_content.

        Args:
            prompt: The input prompt potentially containing code blocks.

        Returns:
            Smart content string if found, None otherwise.
        """
        if self._fixture_index is None:
            return None

        # Import here to avoid circular import
        from fs2.core.models.fixture_index import FixtureIndex

        # Extract code from markdown code block
        code = FixtureIndex.extract_code_from_prompt(prompt)
        if code is None:
            return None

        # Strip whitespace to match stored content exactly
        code = code.strip()
        if not code:
            return None

        # Look up smart_content by the extracted code content
        return self._fixture_index.lookup_smart_content(code)

    async def generate(
        self,
        prompt: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate a fake response.

        Records the call in call_history and returns the configured
        response, fixture lookup, placeholder, or raises error.

        Priority order:
        1. set_response() - explicit test control
        2. fixture_index lookup - smart_content for extracted code
        3. Placeholder fallback - default response

        Args:
            prompt: The input prompt (recorded in call_history).
            max_tokens: Max tokens (recorded in call_history).
            temperature: Temperature (recorded in call_history).

        Returns:
            LLMResponse with content.

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

        # Determine response content with priority order
        content = self._response_content  # Default/set_response

        # Only look up fixture if set_response hasn't been explicitly called
        # (i.e., still using placeholder)
        if self._response_content == "[FakeLLMAdapter placeholder response]":
            fixture_smart_content = self._lookup_fixture_smart_content(prompt)
            if fixture_smart_content is not None:
                content = fixture_smart_content

        # Return response
        return LLMResponse(
            content=content,
            tokens_used=len(content.split()),  # Simple token estimate
            model="fake-model",
            provider=self.provider_name,
            finish_reason="stop",
            was_filtered=False,
        )
