"""LLM response domain model.

Provides immutable result type for LLM adapter operations.
Per AC8: Contains content, tokens_used, model, provider, finish_reason.
Per AC6: Includes was_filtered for Azure content filter handling.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResponse:
    """Immutable response from an LLM adapter.

    This model represents the result of an LLM generation call,
    abstracting away provider-specific details.

    Attributes:
        content: The generated text content.
        tokens_used: Total tokens consumed (prompt + completion).
        model: The model used for generation (e.g., "gpt-4").
        provider: The provider that generated this response (e.g., "azure").
        finish_reason: Why generation stopped (e.g., "stop", "length", "content_filter").
        was_filtered: True if content was filtered by provider safety systems.

    Example:
        >>> response = LLMResponse(
        ...     content="Hello, world!",
        ...     tokens_used=15,
        ...     model="gpt-4",
        ...     provider="openai",
        ...     finish_reason="stop",
        ... )
        >>> response.content
        'Hello, world!'
        >>> response.was_filtered
        False
    """

    content: str
    tokens_used: int
    model: str
    provider: str
    finish_reason: str
    was_filtered: bool = False
