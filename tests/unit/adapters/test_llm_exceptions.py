"""Tests for LLM exception hierarchy.

TDD Phase: RED - These tests should fail until T008 is implemented.

Tests cover:
- LLMAdapterError inherits from AdapterError per Finding 04
- LLMAuthenticationError inherits from LLMAdapterError
- LLMRateLimitError inherits from LLMAdapterError
- LLMContentFilterError inherits from LLMAdapterError
"""

import pytest


@pytest.mark.unit
def test_llm_adapter_error_inherits_adapter_error():
    """LLMAdapterError inherits from AdapterError.

    Purpose: Proves LLM errors can be caught as AdapterError
    Quality Contribution: Enables catch-all at service boundary
    """
    from fs2.core.adapters.exceptions import AdapterError, LLMAdapterError

    error = LLMAdapterError("Test error")
    assert isinstance(error, AdapterError)
    assert isinstance(error, Exception)


@pytest.mark.unit
def test_llm_authentication_error_inherits_llm_error():
    """LLMAuthenticationError inherits from LLMAdapterError.

    Purpose: Proves auth errors can be caught specifically or as LLM errors
    Quality Contribution: Enables granular error handling
    """
    from fs2.core.adapters.exceptions import (
        AdapterError,
        LLMAdapterError,
        LLMAuthenticationError,
    )

    error = LLMAuthenticationError("Invalid API key")
    assert isinstance(error, LLMAdapterError)
    assert isinstance(error, AdapterError)


@pytest.mark.unit
def test_llm_rate_limit_error_inherits_llm_error():
    """LLMRateLimitError inherits from LLMAdapterError.

    Purpose: Proves rate limit errors can be caught specifically
    Quality Contribution: Enables retry logic at service layer
    """
    from fs2.core.adapters.exceptions import (
        AdapterError,
        LLMAdapterError,
        LLMRateLimitError,
    )

    error = LLMRateLimitError("Too many requests")
    assert isinstance(error, LLMAdapterError)
    assert isinstance(error, AdapterError)


@pytest.mark.unit
def test_llm_content_filter_error_inherits_llm_error():
    """LLMContentFilterError inherits from LLMAdapterError.

    Purpose: Proves content filter errors can be caught specifically
    Quality Contribution: Enables graceful content filter handling
    """
    from fs2.core.adapters.exceptions import (
        AdapterError,
        LLMAdapterError,
        LLMContentFilterError,
    )

    error = LLMContentFilterError("Content filtered")
    assert isinstance(error, LLMAdapterError)
    assert isinstance(error, AdapterError)
