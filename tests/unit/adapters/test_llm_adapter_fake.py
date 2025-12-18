"""Tests for FakeLLMAdapter.

TDD Phase: RED - These tests should fail until T012 is implemented.

Tests cover:
- Default returns placeholder content per Finding 09
- set_response() controls output per AC4
- call_history tracks all calls per AC4
- set_error() raises configured exception
- Receives ConfigurationService per AC9
"""

import pytest


@pytest.mark.unit
async def test_fake_adapter_default_returns_placeholder():
    """Default behavior returns placeholder content.

    Purpose: Proves default behavior without set_response()
    Quality Contribution: Documents expected default behavior
    """
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

    adapter = FakeLLMAdapter()
    response = await adapter.generate("Test prompt")

    assert response.content is not None
    assert len(response.content) > 0
    assert response.provider == "fake"


@pytest.mark.unit
async def test_fake_adapter_set_response_controls_output():
    """set_response() controls what generate() returns.

    Purpose: Proves explicit test control per AC4
    Quality Contribution: Enables deterministic testing
    """
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

    adapter = FakeLLMAdapter()
    adapter.set_response("Custom response content")

    response = await adapter.generate("Any prompt")

    assert response.content == "Custom response content"


@pytest.mark.unit
async def test_fake_adapter_tracks_call_history():
    """call_history records all generate() calls.

    Purpose: Proves call tracking per AC4
    Quality Contribution: Enables assertion on call patterns
    """
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

    adapter = FakeLLMAdapter()

    await adapter.generate("First prompt")
    await adapter.generate("Second prompt", max_tokens=100)
    await adapter.generate("Third prompt", temperature=0.5)

    assert len(adapter.call_history) == 3
    assert adapter.call_history[0]["prompt"] == "First prompt"
    assert adapter.call_history[1]["prompt"] == "Second prompt"
    assert adapter.call_history[1]["max_tokens"] == 100
    assert adapter.call_history[2]["temperature"] == 0.5


@pytest.mark.unit
async def test_fake_adapter_set_error_raises_exception():
    """set_error() configures generate() to raise an exception.

    Purpose: Proves error simulation capability
    Quality Contribution: Enables testing error handling paths
    """
    from fs2.core.adapters.exceptions import LLMRateLimitError
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

    adapter = FakeLLMAdapter()
    adapter.set_error(LLMRateLimitError("Rate limit exceeded"))

    with pytest.raises(LLMRateLimitError) as exc_info:
        await adapter.generate("Any prompt")

    assert "Rate limit" in str(exc_info.value)


@pytest.mark.unit
def test_fake_adapter_provider_name():
    """provider_name returns 'fake'.

    Purpose: Proves provider identification
    Quality Contribution: Documents expected provider name
    """
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

    adapter = FakeLLMAdapter()
    assert adapter.provider_name == "fake"


@pytest.mark.unit
async def test_fake_adapter_response_has_correct_metadata():
    """Response includes correct metadata fields.

    Purpose: Proves LLMResponse fields are populated
    Quality Contribution: Validates AC8 compliance
    """
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

    adapter = FakeLLMAdapter()
    adapter.set_response("Test content")

    response = await adapter.generate("prompt", max_tokens=50)

    assert response.model is not None
    assert response.provider == "fake"
    assert response.tokens_used >= 0
    assert response.finish_reason is not None
    assert response.was_filtered is False
