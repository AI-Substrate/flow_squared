"""Tests for SmartContentService (Smart Content Phase 3).

Coverage:
- T001: Initialization with DI pattern (CD01)
- T002: Hash-based skip/regenerate logic (AC5/AC6)
- T003: Token-based content truncation (AC13)
- T004: Single-node processing via TemplateService + LLMService
- T005: Empty/trivial content handling (CD08)
- T006: Error handling strategies (CD07)
- T012: Integration with FakeLLMAdapter (AC10) + Concurrency (CD06b)

19 tests total, all passing.
"""

import pytest

# ===========================================================================
# T001: SmartContentService Initialization Tests
# ===========================================================================


@pytest.mark.unit
def test_given_service_when_constructed_then_extracts_config_internally():
    """SmartContentService extracts config via ConfigurationService.require().

    Purpose: Proves CD01 ConfigurationService registry pattern
    Quality Contribution: Ensures composition root doesn't need to know config types
    Acceptance Criteria: Constructor accepts ConfigurationService, extracts SmartContentConfig internally
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    # Setup config service with SmartContentConfig
    config = FakeConfigurationService(SmartContentConfig(max_input_tokens=10000))

    # Setup dependencies
    llm_adapter = FakeLLMAdapter()
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    # Act: Construct service
    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    # Assert: Service exists and extracted config correctly
    assert service is not None
    assert service._config.max_input_tokens == 10000


@pytest.mark.unit
def test_given_missing_smart_content_config_when_constructed_then_raises_error():
    """SmartContentService fails if SmartContentConfig is not registered.

    Purpose: Proves fail-fast behavior when config is missing
    Quality Contribution: Clear error messages for configuration issues
    Acceptance Criteria: Missing config raises ConfigurationError
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    # Setup config service WITHOUT SmartContentConfig
    config = FakeConfigurationService()
    # Need to add LLMConfig for LLMService
    from fs2.config.objects import LLMConfig
    config.set(LLMConfig(provider="fake"))

    llm_adapter = FakeLLMAdapter()
    llm_service = LLMService(config, llm_adapter)

    # TemplateService needs SmartContentConfig too, so let's add it for template but not expect it in service
    # Actually, we need to test SmartContentService's config extraction specifically
    # Let's add SmartContentConfig for TemplateService but then clear it
    config.set(SmartContentConfig())
    template_service = TemplateService(config)

    # Clear the config to simulate missing for SmartContentService
    config._configs.pop(SmartContentConfig, None)

    # Need to pass a config for token_counter (use the same config)
    config.set(SmartContentConfig())  # Re-add for token_counter
    token_counter = FakeTokenCounterAdapter(config)
    config._configs.pop(SmartContentConfig, None)  # Remove again for test

    # Act & Assert
    with pytest.raises(Exception):  # ConfigurationError or similar
        SmartContentService(
            config=config,
            llm_service=llm_service,
            template_service=template_service,
            token_counter=token_counter,
        )


# ===========================================================================
# T002: Hash-Based Skip Logic Tests (AC5/AC6)
# ===========================================================================


@pytest.mark.unit
async def test_given_matching_hash_when_processing_then_skips_llm_call():
    """SmartContentService skips regeneration when content_hash == smart_content_hash.

    Purpose: Proves AC5 hash-based skip logic
    Quality Contribution: Prevents redundant LLM calls for unchanged nodes
    Acceptance Criteria: No LLM call made, original node returned unchanged
    """
    from dataclasses import replace

    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("New summary - should not be used")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    # Create node with matching hashes (already processed)
    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
        smart_content="Existing summary",
        smart_content_hash="abc123",  # Will be overwritten by factory
    )
    # Since factory computes content_hash, we need to set smart_content_hash to match
    node = replace(node, smart_content_hash=node.content_hash)

    # Act
    result = await service.generate_smart_content(node)

    # Assert: Node unchanged, no LLM call
    assert result is node  # Same object returned
    assert result.smart_content == "Existing summary"
    assert len(llm_adapter.call_history) == 0


@pytest.mark.unit
async def test_given_mismatched_hash_when_processing_then_regenerates():
    """SmartContentService regenerates when content_hash != smart_content_hash.

    Purpose: Proves AC6 hash-based regeneration
    Quality Contribution: Ensures smart_content stays current with content changes
    Acceptance Criteria: LLM called, new node returned with updated smart_content and smart_content_hash
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Updated summary from LLM")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    # Create node with mismatched hashes (content changed)
    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
        smart_content="Old summary",
        smart_content_hash="old_hash_does_not_match",
    )

    # Act
    result = await service.generate_smart_content(node)

    # Assert: New node returned with updated smart_content and hash
    assert result is not node  # New instance
    assert result.smart_content == "Updated summary from LLM"
    assert result.smart_content_hash == node.content_hash  # Hash now matches
    assert len(llm_adapter.call_history) == 1


@pytest.mark.unit
async def test_given_none_smart_content_hash_when_processing_then_generates():
    """SmartContentService generates when smart_content_hash is None.

    Purpose: Proves new nodes get processed
    Quality Contribution: First-time smart_content generation works
    Acceptance Criteria: LLM called, node returned with smart_content and smart_content_hash set
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Fresh summary")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    # Create node with no smart_content_hash (never processed)
    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
    )
    assert node.smart_content_hash is None  # Verify precondition

    # Act
    result = await service.generate_smart_content(node)

    # Assert: Node has smart_content and smart_content_hash set
    assert result.smart_content == "Fresh summary"
    assert result.smart_content_hash == node.content_hash
    assert len(llm_adapter.call_history) == 1


# ===========================================================================
# T003: Content Truncation Tests (AC13)
# ===========================================================================


@pytest.mark.unit
async def test_given_large_content_when_processing_then_truncates_with_marker(caplog):
    """SmartContentService truncates content exceeding max_input_tokens.

    Purpose: Proves AC13 token-based truncation
    Quality Contribution: Prevents LLM context overflow
    Acceptance Criteria: Content truncated, [TRUNCATED] marker in prompt, WARNING logged
    """
    import logging

    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    # Set a very low max_input_tokens to trigger truncation
    config = FakeConfigurationService(SmartContentConfig(max_input_tokens=10))
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Summary of truncated content")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)

    # Configure FakeTokenCounter to report high token count
    token_counter = FakeTokenCounterAdapter(config)
    token_counter.set_default_count(1000)  # Way over 10 token limit

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    # Create node with large content
    large_content = "x" * 10000
    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="big_func",
        qualified_name="big_func",
        start_line=1,
        end_line=100,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=10000,
        content=large_content,
        signature="def big_func():",
    )

    # Act
    with caplog.at_level(logging.WARNING):
        result = await service.generate_smart_content(node)

    # Assert: Truncation occurred
    assert len(llm_adapter.call_history) == 1
    prompt_sent = llm_adapter.call_history[0]["prompt"]
    assert "[TRUNCATED]" in prompt_sent  # Marker in prompt

    # Assert: smart_content does NOT have truncation marker
    assert "[TRUNCATED]" not in result.smart_content

    # Assert: WARNING logged
    warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_logs) >= 1
    assert any("truncat" in log.message.lower() for log in warning_logs)


@pytest.mark.unit
async def test_given_small_content_when_processing_then_no_truncation():
    """SmartContentService does not truncate content under max_input_tokens.

    Purpose: Proves truncation is conditional
    Quality Contribution: Full content preserved when within limits
    Acceptance Criteria: No [TRUNCATED] marker in prompt
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig(max_input_tokens=50000))
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Summary")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)

    # FakeTokenCounter returns small count by default
    token_counter = FakeTokenCounterAdapter(config)
    token_counter.set_default_count(100)  # Under 50000 limit

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="small_func",
        qualified_name="small_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def small_func():\n    \"\"\"A small test function.\"\"\"\n    return 42",
        signature="def small_func():",
    )

    # Act
    result = await service.generate_smart_content(node)

    # Assert: No truncation marker
    prompt_sent = llm_adapter.call_history[0]["prompt"]
    assert "[TRUNCATED]" not in prompt_sent


# ===========================================================================
# T004: Single-Node Processing Tests
# ===========================================================================


@pytest.mark.unit
async def test_given_node_when_processing_then_renders_correct_context():
    """SmartContentService passes correct context to TemplateService.

    Purpose: Proves AC8 context variables are passed correctly
    Quality Contribution: Templates receive all required data
    Acceptance Criteria: Context includes name, qualified_name, category, ts_kind, language, content, signature
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Generated summary")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="MyClass.my_func",
        start_line=1,
        end_line=5,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=100,
        content="def my_func(x, y):\n    \"\"\"Add two numbers together.\"\"\"\n    return x + y  # Sum",
        signature="def my_func(x, y):",
    )

    # Act
    result = await service.generate_smart_content(node)

    # Assert: Prompt was generated and sent
    assert len(llm_adapter.call_history) == 1
    prompt = llm_adapter.call_history[0]["prompt"]

    # Check that key context variables appear in prompt (from template)
    assert "my_func" in prompt
    assert "python" in prompt.lower() or "Python" in prompt


@pytest.mark.unit
async def test_given_node_when_processing_then_returns_new_instance():
    """SmartContentService returns new CodeNode instance (frozen immutability).

    Purpose: Proves CD03 frozen dataclass immutability via dataclasses.replace()
    Quality Contribution: Prevents mutation bugs with frozen objects
    Acceptance Criteria: Returned node is a new instance, not the original
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("New summary")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
    )

    # Act
    result = await service.generate_smart_content(node)

    # Assert: New instance returned
    assert result is not node
    assert result.smart_content == "New summary"
    # Original unchanged
    assert node.smart_content is None


@pytest.mark.unit
async def test_given_empty_llm_response_when_processing_then_raises_error():
    """SmartContentService raises error for empty LLM response.

    Purpose: Proves empty response handling (per /didyouknow insight)
    Quality Contribution: Prevents nodes with empty smart_content masquerading as processed
    Acceptance Criteria: SmartContentProcessingError raised, hash not set (retry-friendly)
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.exceptions import SmartContentProcessingError
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("")  # Empty response
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
    )

    # Act & Assert
    with pytest.raises(SmartContentProcessingError, match=r"empty|blank"):
        await service.generate_smart_content(node)


@pytest.mark.unit
async def test_given_whitespace_llm_response_when_processing_then_raises_error():
    """SmartContentService raises error for whitespace-only LLM response.

    Purpose: Proves whitespace response also treated as empty
    Quality Contribution: "   " is not valid smart_content
    Acceptance Criteria: SmartContentProcessingError raised
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.exceptions import SmartContentProcessingError
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("   \n\t  ")  # Whitespace only
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
    )

    # Act & Assert
    with pytest.raises(SmartContentProcessingError, match=r"empty|blank"):
        await service.generate_smart_content(node)


# ===========================================================================
# T005: Empty/Trivial Content Tests (CD08)
# ===========================================================================


@pytest.mark.unit
async def test_given_empty_content_when_processing_then_skips_with_placeholder():
    """SmartContentService skips LLM call for empty content nodes.

    Purpose: Proves CD08 empty content handling
    Quality Contribution: Prevents wasting LLM tokens on empty nodes
    Acceptance Criteria: No LLM call, placeholder smart_content set
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Should not be used")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    # Create node with empty content
    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="empty_func",
        qualified_name="empty_func",
        start_line=1,
        end_line=1,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=0,
        content="",  # Empty content
        signature="",
    )

    # Act
    result = await service.generate_smart_content(node)

    # Assert: No LLM call, placeholder set
    assert len(llm_adapter.call_history) == 0
    assert "[Empty content" in result.smart_content


@pytest.mark.unit
async def test_given_trivial_content_when_processing_then_skips_with_placeholder():
    """SmartContentService skips LLM call for trivial content (<10 chars).

    Purpose: Proves CD08 trivial content handling
    Quality Contribution: Prevents summarizing "pass" or "x = 1"
    Acceptance Criteria: No LLM call for content <10 characters
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Should not be used")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    # Create node with trivial content (< 10 chars)
    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="tiny",
        qualified_name="tiny",
        start_line=1,
        end_line=1,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=4,
        content="pass",  # Only 4 characters
        signature="",
    )

    # Act
    result = await service.generate_smart_content(node)

    # Assert: No LLM call, placeholder set
    assert len(llm_adapter.call_history) == 0
    assert "[Empty content" in result.smart_content or "no summary" in result.smart_content.lower()


# ===========================================================================
# T006: Error Handling Tests (CD07)
# ===========================================================================


@pytest.mark.unit
async def test_given_auth_error_when_processing_then_raises():
    """SmartContentService re-raises auth errors (batch should fail).

    Purpose: Proves CD07 auth error handling
    Quality Contribution: Auth errors are config issues, must be surfaced
    Acceptance Criteria: LLMAuthenticationError propagates up
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.exceptions import LLMAuthenticationError
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_error(LLMAuthenticationError("Invalid API key"))
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
    )

    # Act & Assert
    with pytest.raises(LLMAuthenticationError):
        await service.generate_smart_content(node)


@pytest.mark.unit
async def test_given_content_filter_when_processing_then_returns_fallback():
    """SmartContentService returns fallback text for filtered content.

    Purpose: Proves CD07 content filter handling
    Quality Contribution: Graceful degradation for filtered content
    Acceptance Criteria: Node returned with "[Content filtered]" placeholder
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.exceptions import LLMContentFilterError
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_error(LLMContentFilterError("Content filtered"))
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
    )

    # Act
    result = await service.generate_smart_content(node)

    # Assert: Fallback text set
    assert "[Content filtered]" in result.smart_content


@pytest.mark.unit
async def test_given_rate_limit_when_processing_then_logs_warning(caplog):
    """SmartContentService logs warning for rate limit errors.

    Purpose: Proves CD07 rate limit handling (Phase 3 simple version)
    Quality Contribution: Rate limit errors are logged for visibility
    Acceptance Criteria: WARNING logged, SmartContentProcessingError raised
    """
    import logging

    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.exceptions import LLMRateLimitError
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.exceptions import SmartContentProcessingError
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_error(LLMRateLimitError("Rate limit exceeded"))
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
    )

    # Act & Assert
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SmartContentProcessingError, match=r"[Rr]ate.?[Ll]imit"):
            await service.generate_smart_content(node)

    # Assert: WARNING logged
    warning_logs = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_logs) >= 1


@pytest.mark.unit
async def test_given_token_counter_error_when_processing_then_raises_smart_content_error():
    """SmartContentService translates TokenCounterError to SmartContentProcessingError.

    Purpose: Proves exception layering is preserved (FT-005 code review finding)
    Quality Contribution: Adapter exceptions don't leak to callers
    Acceptance Criteria: TokenCounterError → SmartContentProcessingError with node context
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.exceptions import TokenCounterError
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.exceptions import SmartContentProcessingError
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Summary")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)
    token_counter.set_error(TokenCounterError("Tokenizer failed"))

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="test.py",
        language="python",
        ts_kind="function_definition",
        name="my_func",
        qualified_name="my_func",
        start_line=1,
        end_line=3,
        start_column=0,
        end_column=0,
        start_byte=0,
        end_byte=50,
        content="def my_func():\n    \"\"\"A test function.\"\"\"\n    return 42  # Implementation",
        signature="def my_func():",
    )

    # Act & Assert
    with pytest.raises(SmartContentProcessingError, match=r"Token counting failed"):
        await service.generate_smart_content(node)


# ===========================================================================
# T012: Integration and Concurrency Tests (AC10, CD06b)
# ===========================================================================


@pytest.mark.unit
async def test_integration_end_to_end_with_fake_llm():
    """SmartContentService works end-to-end with FakeLLMAdapter.

    Purpose: Proves AC10 FakeLLMAdapter integration
    Quality Contribution: Full flow validation with test double
    Acceptance Criteria: Complete flow from CodeNode to updated smart_content
    """
    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("A function that performs important business logic")
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    node = CodeNode.create_callable(
        file_path="business/logic.py",
        language="python",
        ts_kind="function_definition",
        name="process_order",
        qualified_name="OrderService.process_order",
        start_line=10,
        end_line=25,
        start_column=4,
        end_column=0,
        start_byte=200,
        end_byte=500,
        content="def process_order(self, order): # complex logic here\n    pass",
        signature="def process_order(self, order):",
    )

    # Act
    result = await service.generate_smart_content(node)

    # Assert: Full integration works
    assert result.smart_content == "A function that performs important business logic"
    assert result.smart_content_hash == node.content_hash
    assert len(llm_adapter.call_history) == 1

    # Verify prompt contains node info
    prompt = llm_adapter.call_history[0]["prompt"]
    assert "process_order" in prompt


@pytest.mark.unit
async def test_concurrent_processing_does_not_serialize():
    """SmartContentService LLM calls run concurrently, not serially.

    Purpose: Proves CD06b event loop blocking prevention
    Quality Contribution: Catches insidious serialization bugs early
    Acceptance Criteria: 5 calls with 0.1s delay complete in <0.25s (not ~0.5s)
    """
    import asyncio
    import time

    from fs2.config.objects import SmartContentConfig
    from fs2.config.service import FakeConfigurationService
    from fs2.core.adapters.llm_adapter_fake import FakeLLMAdapter
    from fs2.core.adapters.token_counter_adapter_fake import FakeTokenCounterAdapter
    from fs2.core.models.code_node import CodeNode
    from fs2.core.services.llm_service import LLMService
    from fs2.core.services.smart_content.smart_content_service import (
        SmartContentService,
    )
    from fs2.core.services.smart_content.template_service import TemplateService

    config = FakeConfigurationService(SmartContentConfig())
    llm_adapter = FakeLLMAdapter()
    llm_adapter.set_response("Summary")
    llm_adapter.set_delay(0.1)  # 100ms delay per call
    llm_service = LLMService(config, llm_adapter)
    template_service = TemplateService(config)
    token_counter = FakeTokenCounterAdapter(config)

    service = SmartContentService(
        config=config,
        llm_service=llm_service,
        template_service=template_service,
        token_counter=token_counter,
    )

    # Create 5 nodes to process
    nodes = []
    for i in range(5):
        node = CodeNode.create_callable(
            file_path=f"test{i}.py",
            language="python",
            ts_kind="function_definition",
            name=f"func_{i}",
            qualified_name=f"func_{i}",
            start_line=1,
            end_line=3,
            start_column=0,
            end_column=0,
            start_byte=0,
            end_byte=50,
            content=f"def func_{i}():\n    \"\"\"Test function {i}.\"\"\"\n    return {i}  # Implementation",
            signature=f"def func_{i}():",
        )
        nodes.append(node)

    # Act: Process concurrently
    start = time.time()
    results = await asyncio.gather(
        *[service.generate_smart_content(node) for node in nodes]
    )
    elapsed = time.time() - start

    # Assert: 5 calls completed
    assert len(results) == 5
    assert len(llm_adapter.call_history) == 5

    # Assert: Concurrent execution (5 * 0.1s = 0.5s if serial, ~0.1s if parallel)
    # Allow some margin for overhead
    assert elapsed < 0.3, f"Calls appear to be serialized! Took {elapsed:.2f}s (expected <0.3s for parallel)"
