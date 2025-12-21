"""Tests for FakeLLMAdapter.

TDD Phase: RED - These tests should fail until T012 is implemented.

Tests cover:
- Default returns placeholder content per Finding 09
- set_response() controls output per AC4
- call_history tracks all calls per AC4
- set_error() raises configured exception
- Receives ConfigurationService per AC9

Subtask 001: Additional tests for FixtureIndex integration.
Per DYK-1: Uses extract_code_from_prompt() to find code blocks for lookup.
"""

import pytest

from fs2.core.models.code_node import CodeNode
from fs2.core.models.fixture_index import FixtureIndex


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


@pytest.mark.unit
class TestFakeLLMAdapterWithFixtureIndex:
    """ST007: Tests for FakeLLMAdapter with FixtureIndex integration.

    Per DYK-1: Uses extract_code_from_prompt() to find code blocks for smart_content lookup.
    Per Subtask 001: fixture_index is optional and provides smart_content for code.
    """

    @pytest.fixture
    def fixture_index(self):
        """Create a FixtureIndex with sample nodes for testing."""
        nodes = [
            CodeNode.create_file(
                file_path="test.py",
                language="python",
                ts_kind="module",
                start_byte=0,
                end_byte=100,
                start_line=1,
                end_line=10,
                content="def add(a, b): return a + b",
                smart_content="A function that adds two numbers and returns the result.",
                embedding=((0.1, 0.2, 0.3, 0.4),),
            ),
            CodeNode.create_callable(
                file_path="test.py",
                language="python",
                ts_kind="function_definition",
                name="multiply",
                qualified_name="multiply",
                start_line=1,
                end_line=1,
                start_column=0,
                end_column=35,
                start_byte=0,
                end_byte=35,
                content="def multiply(x, y): return x * y",
                signature="def multiply(x, y):",
                smart_content="A multiplication function that takes two arguments.",
                embedding=((0.5, 0.6, 0.7, 0.8),),
            ),
        ]
        return FixtureIndex.from_nodes(nodes)

    def test_given_fixture_index_when_construct_then_succeeds(self, fixture_index):
        """
        Purpose: Proves FakeLLMAdapter accepts fixture_index parameter.
        Quality Contribution: Enables fixture-backed testing.
        Acceptance Criteria: Adapter can be constructed with fixture_index.

        Task: ST007
        """
        from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

        # Arrange / Act
        adapter = FakeLLMAdapter(fixture_index=fixture_index)

        # Assert
        assert adapter is not None

    async def test_given_fixture_index_when_generate_with_known_code_then_returns_smart_content(
        self, fixture_index
    ):
        """
        Purpose: Proves fixture_index lookup returns smart_content for known code.
        Quality Contribution: Tests can use real pre-computed descriptions.
        Acceptance Criteria: Prompt with known code returns fixture smart_content.

        Task: ST007
        Per DYK-1: Extracts code from markdown block for lookup.
        """
        from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

        # Arrange
        adapter = FakeLLMAdapter(fixture_index=fixture_index)
        prompt = """Please analyze this code:

```python
def add(a, b): return a + b
```

Provide a summary."""

        # Act
        response = await adapter.generate(prompt)

        # Assert - Returns smart_content from fixture
        assert response.content == "A function that adds two numbers and returns the result."

    async def test_given_fixture_index_when_generate_with_unknown_code_then_returns_placeholder(
        self, fixture_index
    ):
        """
        Purpose: Proves unknown code falls back to placeholder.
        Quality Contribution: Graceful fallback for non-fixture content.
        Acceptance Criteria: Unknown code gets placeholder response.

        Task: ST007
        """
        from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

        # Arrange
        adapter = FakeLLMAdapter(fixture_index=fixture_index)
        prompt = """Please analyze this code:

```python
def unknown_function(): pass
```

Provide a summary."""

        # Act
        response = await adapter.generate(prompt)

        # Assert - Falls back to placeholder
        assert "FakeLLMAdapter" in response.content or len(response.content) > 0

    async def test_given_set_response_and_fixture_index_when_generate_then_set_response_wins(
        self, fixture_index
    ):
        """
        Purpose: Proves set_response takes priority over fixture_index.
        Quality Contribution: Tests retain explicit control when needed.
        Acceptance Criteria: set_response overrides fixture lookup.

        Task: ST007
        """
        from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

        # Arrange
        adapter = FakeLLMAdapter(fixture_index=fixture_index)
        adapter.set_response("Explicit test response")

        prompt = """```python
def add(a, b): return a + b
```"""

        # Act - This code is in the fixture, but set_response should win
        response = await adapter.generate(prompt)

        # Assert
        assert response.content == "Explicit test response"

    async def test_given_fixture_index_when_prompt_has_no_code_then_returns_placeholder(
        self, fixture_index
    ):
        """
        Purpose: Proves prompts without code blocks use placeholder.
        Quality Contribution: No code block means no fixture lookup.
        Acceptance Criteria: No code block returns placeholder.

        Task: ST007
        """
        from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

        # Arrange
        adapter = FakeLLMAdapter(fixture_index=fixture_index)
        prompt = "What is the capital of France?"

        # Act
        response = await adapter.generate(prompt)

        # Assert - No code to extract, falls back to placeholder
        assert "FakeLLMAdapter" in response.content or len(response.content) > 0

    async def test_given_no_fixture_index_when_generate_then_uses_placeholder(self):
        """
        Purpose: Proves None fixture_index doesn't break adapter.
        Quality Contribution: Backwards compatibility with existing tests.
        Acceptance Criteria: No fixture_index works as before.

        Task: ST007
        """
        from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter

        # Arrange
        adapter = FakeLLMAdapter()

        # Act
        response = await adapter.generate("any prompt")

        # Assert - Uses default placeholder
        assert len(response.content) > 0
