"""Tests for LLMResponse frozen dataclass.

TDD Phase: RED - These tests should fail until T006 is implemented.

Tests cover:
- Immutability (frozen=True) per Finding 04
- All required fields present per AC8
- Default value for was_filtered
"""

import pytest


@pytest.mark.unit
def test_llm_response_is_frozen():
    """LLMResponse is immutable (frozen=True).

    Purpose: Proves LLMResponse cannot be modified after creation
    Quality Contribution: Ensures response data integrity
    """
    from dataclasses import FrozenInstanceError

    from fs2.core.models.llm_response import LLMResponse

    response = LLMResponse(
        content="test",
        tokens_used=10,
        model="gpt-4",
        provider="openai",
        finish_reason="stop",
    )

    with pytest.raises(FrozenInstanceError):
        response.content = "modified"


@pytest.mark.unit
def test_llm_response_has_all_fields():
    """LLMResponse has all required fields per AC8.

    Purpose: Proves AC8 compliance - all required fields present
    Quality Contribution: Documents response contract

    Required fields:
    - content: str
    - tokens_used: int
    - model: str
    - provider: str
    - finish_reason: str
    - was_filtered: bool (default False)
    """
    from fs2.core.models.llm_response import LLMResponse

    response = LLMResponse(
        content="Test response content",
        tokens_used=42,
        model="gpt-4",
        provider="azure",
        finish_reason="stop",
    )

    assert response.content == "Test response content"
    assert response.tokens_used == 42
    assert response.model == "gpt-4"
    assert response.provider == "azure"
    assert response.finish_reason == "stop"
    assert hasattr(response, "was_filtered")


@pytest.mark.unit
def test_llm_response_was_filtered_default_false():
    """was_filtered defaults to False.

    Purpose: Proves default not filtered behavior
    Quality Contribution: Documents happy path default
    """
    from fs2.core.models.llm_response import LLMResponse

    response = LLMResponse(
        content="test",
        tokens_used=10,
        model="gpt-4",
        provider="openai",
        finish_reason="stop",
    )

    assert response.was_filtered is False


@pytest.mark.unit
def test_llm_response_was_filtered_can_be_true():
    """was_filtered can be set to True.

    Purpose: Proves content filter response can be flagged
    Quality Contribution: Documents content filter handling
    """
    from fs2.core.models.llm_response import LLMResponse

    response = LLMResponse(
        content="",
        tokens_used=0,
        model="gpt-4",
        provider="azure",
        finish_reason="content_filter",
        was_filtered=True,
    )

    assert response.was_filtered is True
    assert response.finish_reason == "content_filter"
