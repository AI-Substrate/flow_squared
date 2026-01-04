"""Tests for LLMAdapter ABC interface.

TDD Phase: RED - These tests should fail until T010 is implemented.

Tests cover:
- ABC cannot be instantiated directly
- generate() is async (coroutine function) per AC10
- provider_name property exists
"""

import asyncio
import inspect

import pytest


@pytest.mark.unit
def test_llm_adapter_cannot_instantiate():
    """LLMAdapter ABC cannot be instantiated directly.

    Purpose: Proves ABC enforcement works
    Quality Contribution: Ensures adapters implement required methods
    """
    from fs2.core.adapters.llm_adapter import LLMAdapter

    with pytest.raises(TypeError) as exc_info:
        LLMAdapter()

    assert "abstract" in str(exc_info.value).lower()


@pytest.mark.unit
def test_llm_adapter_generate_is_async():
    """generate() method is async (coroutine function).

    Purpose: Proves async interface per AC10
    Quality Contribution: Enforces async-all-the-way architecture
    """
    from fs2.core.adapters.llm_adapter import LLMAdapter

    # Check that generate is defined as a coroutine function
    assert hasattr(LLMAdapter, "generate")
    # For ABCs, check if it's marked as abstract and would be async
    generate_method = LLMAdapter.generate
    # The method should be a coroutine function (async def)
    assert asyncio.iscoroutinefunction(generate_method)


@pytest.mark.unit
def test_llm_adapter_has_provider_name_property():
    """LLMAdapter has provider_name abstract property.

    Purpose: Proves provider_name is part of interface
    Quality Contribution: Enables provider identification in responses
    """
    from fs2.core.adapters.llm_adapter import LLMAdapter

    # Check that provider_name is defined
    assert hasattr(LLMAdapter, "provider_name")
    # It should be an abstract property
    assert isinstance(inspect.getattr_static(LLMAdapter, "provider_name"), property)
